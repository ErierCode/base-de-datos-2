using System.Diagnostics;
using System.Text.Json;
using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

/// <summary>Módulo 3 — laboratorio de consulta lenta, EXPLAIN ANALYZE y optimización indexada con evidencia.</summary>
public sealed class QueryOptimizationService
{
    private const string LabSql =
        """
        SELECT count(*), coalesce(sum(o.amount), 0)
        FROM query_lab.orders o
        WHERE o.customer_id = @cid AND o.status = @st
          AND o.amount > (SELECT avg(amount) FROM query_lab.orders)
          AND o.created_at <= (SELECT max(created_at) FROM query_lab.orders)
        """;

    private const string IndexName = "idx_query_lab_orders_customer_status";
    private readonly ControlDb _db;

    public QueryOptimizationService(ControlDb db) => _db = db;

    public async Task<QueryLogDto> SetupLabAndBaselineAsync(int dbId, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await ReseedLabAsync(conn, force: true, ct);
        await DropLabIndexAsync(conn, ct);

        var (ms, plan, rows) = await BenchmarkLabQueryAsync(conn, allowIndex: false, ct);
        var logId = await InsertQueryLogAsync(conn, dbId, LabSql, ms, rows, null, plan, ct);

        return await FetchQueryLogAsync(conn, logId, ct)
            ?? throw new InvalidOperationException("No se pudo leer query_log insertado.");
    }

    public async Task<OptimizationResultDto> OptimizeQueryLogAsync(long queryLogId, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        var row = await FetchQueryLogAsync(conn, queryLogId, ct)
            ?? throw new KeyNotFoundException("query_log no encontrado.");

        if (row.IsOptimized)
            throw new InvalidOperationException("Esta consulta ya fue optimizada.");

        await ReseedLabAsync(conn, force: false, ct);
        await DropLabIndexAsync(conn, ct);

        var (beforeMs, planBefore, rowsBefore) = await BenchmarkLabQueryAsync(conn, allowIndex: false, ct);
        var ddl = $"CREATE INDEX IF NOT EXISTS {IndexName} ON query_lab.orders (customer_id, status)";
        await using (var ddlCmd = new NpgsqlCommand(ddl, conn))
            await ddlCmd.ExecuteNonQueryAsync(ct);

        var (afterMs, planAfter, rowsAfter) = await BenchmarkLabQueryAsync(conn, allowIndex: true, ct);

        long optId;
        await using (var ins = new NpgsqlCommand(
            """
            INSERT INTO query_optimizations (
              query_log_id, duration_before_ms, duration_after_ms,
              index_applied, ddl_applied, execution_plan_before, execution_plan_after
            ) VALUES (@qid,@b,@a,@idx,@ddl,@pb,@pa) RETURNING id
            """, conn))
        {
            ins.Parameters.AddWithValue("qid", queryLogId);
            ins.Parameters.AddWithValue("b", beforeMs);
            ins.Parameters.AddWithValue("a", afterMs);
            ins.Parameters.AddWithValue("idx", IndexName);
            ins.Parameters.AddWithValue("ddl", ddl);
            ins.Parameters.AddWithValue("pb", (object?)planBefore ?? DBNull.Value);
            ins.Parameters.AddWithValue("pa", (object?)planAfter ?? DBNull.Value);
            optId = Convert.ToInt64(await ins.ExecuteScalarAsync(ct));
        }

        var optimizedSql = LabSql + " /* index: " + IndexName + " */";
        await using (var upd = new NpgsqlCommand(
            """
            UPDATE query_log SET is_optimized = TRUE, optimized_query_text = @oq,
              duration_ms = @after, index_used = @idx, execution_plan = @plan
            WHERE id = @id
            """, conn))
        {
            upd.Parameters.AddWithValue("oq", optimizedSql);
            upd.Parameters.AddWithValue("after", afterMs);
            upd.Parameters.AddWithValue("idx", IndexName);
            upd.Parameters.AddWithValue("plan", (object?)planAfter ?? DBNull.Value);
            upd.Parameters.AddWithValue("id", queryLogId);
            await upd.ExecuteNonQueryAsync(ct);
        }

        var updated = await FetchQueryLogAsync(conn, queryLogId, ct);
        return new OptimizationResultDto(
            optId,
            beforeMs,
            afterMs,
            Math.Round(100.0 * (beforeMs - afterMs) / Math.Max(beforeMs, 0.001), 2),
            IndexName,
            ddl,
            rowsBefore,
            rowsAfter,
            updated!);
    }

    public async Task<IReadOnlyList<QueryLogDto>> ListSlowQueriesAsync(int limit, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT q.id, q.db_id, q.speed_class::text, q.duration_ms, q.rows_returned,
                   q.index_used, q.is_optimized, left(q.query_text, 500),
                   q.created_at, q.optimized_query_text,
                   o.duration_before_ms, o.duration_after_ms, o.improvement_pct, o.index_applied
            FROM query_log q
            LEFT JOIN LATERAL (
                SELECT duration_before_ms, duration_after_ms, improvement_pct, index_applied
                FROM query_optimizations WHERE query_log_id = q.id ORDER BY id DESC LIMIT 1
            ) o ON TRUE
            ORDER BY q.duration_ms DESC, q.created_at DESC
            LIMIT @lim
            """, conn);
        cmd.Parameters.AddWithValue("lim", limit);
        var list = new List<QueryLogDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            list.Add(ReadQueryLogRow(r));
        return list;
    }

    private const int LabRowTarget = 2_000_000;
    private const int LabHotCustomerId = 4242;

    /// <summary>Datos sesgados (~40% filas OPEN del cliente demo) para seq scan lento sin índice.</summary>
    private static async Task ReseedLabAsync(NpgsqlConnection conn, bool force, CancellationToken ct)
    {
        await using var chk = new NpgsqlCommand("SELECT count(*) FROM query_lab.orders", conn);
        var cnt = Convert.ToInt64(await chk.ExecuteScalarAsync(ct));
        if (!force && cnt >= LabRowTarget) return;

        await using var trunc = new NpgsqlCommand("TRUNCATE query_lab.orders", conn) { CommandTimeout = 600 };
        await trunc.ExecuteNonQueryAsync(ct);

        var hotRows = (int)(LabRowTarget * 0.05);
        await using var ins = new NpgsqlCommand(
            """
            INSERT INTO query_lab.orders (customer_id, amount, status)
            SELECT
                CASE WHEN gs <= @hotRows THEN @hot ELSE (random() * 8000)::int END,
                (random() * 1000)::numeric(12, 2),
                CASE
                    WHEN gs <= @hotRows THEN 'OPEN'
                    WHEN random() < 0.72 THEN 'OPEN'
                    ELSE 'CLOSED'
                END
            FROM generate_series(1, @rows) AS gs
            """, conn);
        ins.Parameters.AddWithValue("hotRows", hotRows);
        ins.Parameters.AddWithValue("hot", LabHotCustomerId);
        ins.Parameters.AddWithValue("rows", LabRowTarget);
        ins.CommandTimeout = 600;
        await ins.ExecuteNonQueryAsync(ct);

        await using var vac = new NpgsqlCommand("ANALYZE query_lab.orders", conn) { CommandTimeout = 600 };
        await vac.ExecuteNonQueryAsync(ct);
    }

    private static async Task DropLabIndexAsync(NpgsqlConnection conn, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand($"DROP INDEX IF EXISTS query_lab.{IndexName}", conn);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static async Task<(double Ms, string? Plan, long Rows)> BenchmarkLabQueryAsync(
        NpgsqlConnection conn, bool allowIndex, CancellationToken ct)
    {
        await using (var prep = new NpgsqlCommand(
            allowIndex
                ? "SET LOCAL max_parallel_workers_per_gather = 0"
                : """
                  SET LOCAL max_parallel_workers_per_gather = 0;
                  SET LOCAL enable_indexscan = off;
                  SET LOCAL enable_bitmapscan = off
                  """, conn))
            await prep.ExecuteNonQueryAsync(ct);

        var sw = Stopwatch.StartNew();
        string? planJson = null;
        long rows = 0;

        await using (var cmd = new NpgsqlCommand(LabSql, conn))
        {
            cmd.Parameters.AddWithValue("cid", LabHotCustomerId);
            cmd.Parameters.AddWithValue("st", "OPEN");
            await using var r = await cmd.ExecuteReaderAsync(ct);
            if (await r.ReadAsync(ct))
                rows = r.GetInt64(0);
        }
        sw.Stop();

        try
        {
            await using var explain = new NpgsqlCommand(
                "EXPLAIN (ANALYZE, FORMAT JSON) " + LabSql, conn);
            explain.Parameters.AddWithValue("cid", LabHotCustomerId);
            explain.Parameters.AddWithValue("st", "OPEN");
            var raw = await explain.ExecuteScalarAsync(ct);
            planJson = raw?.ToString();
            var msFromPlan = TryExtractPlanMs(planJson);
            if (msFromPlan > 0)
                return (Math.Max(sw.Elapsed.TotalMilliseconds, msFromPlan), planJson, rows);
        }
        catch
        {
            // fallback al cronómetro
        }

        return (sw.Elapsed.TotalMilliseconds, planJson, rows);
    }

    private static double TryExtractPlanMs(string? planJson)
    {
        if (string.IsNullOrWhiteSpace(planJson)) return 0;
        try
        {
            using var doc = JsonDocument.Parse(planJson);
            if (doc.RootElement.ValueKind == JsonValueKind.Array && doc.RootElement.GetArrayLength() > 0)
            {
                var plan = doc.RootElement[0];
                if (plan.TryGetProperty("Plan", out var p) && p.TryGetProperty("Actual Total Time", out var t))
                    return t.GetDouble();
            }
        }
        catch { /* ignore */ }
        return 0;
    }

    private static async Task<long> InsertQueryLogAsync(
        NpgsqlConnection conn, int dbId, string sql, double ms, long rows,
        string? indexUsed, string? plan, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            INSERT INTO query_log (db_id, query_text, duration_ms, rows_returned, index_used, execution_plan)
            VALUES (@db,@q,@ms,@rows,@idx,@plan) RETURNING id
            """, conn);
        cmd.Parameters.AddWithValue("db", dbId);
        cmd.Parameters.AddWithValue("q", sql);
        cmd.Parameters.AddWithValue("ms", Math.Round(ms, 3));
        cmd.Parameters.AddWithValue("rows", rows);
        cmd.Parameters.AddWithValue("idx", (object?)indexUsed ?? DBNull.Value);
        cmd.Parameters.AddWithValue("plan", (object?)plan ?? DBNull.Value);
        return Convert.ToInt64(await cmd.ExecuteScalarAsync(ct));
    }

    private static QueryLogDto ReadQueryLogRow(NpgsqlDataReader r) => new(
        r.GetInt64(0), r.GetInt32(1), r.GetString(2), r.GetDecimal(3),
        r.IsDBNull(4) ? null : r.GetInt64(4),
        r.IsDBNull(5) ? null : r.GetString(5),
        r.GetBoolean(6), r.GetString(7), r.GetDateTime(8),
        r.IsDBNull(9) ? null : r.GetString(9),
        r.IsDBNull(10) ? null : r.GetDecimal(10),
        r.IsDBNull(11) ? null : r.GetDecimal(11),
        r.IsDBNull(12) ? null : r.GetDecimal(12),
        r.IsDBNull(13) ? null : r.GetString(13));

    private static async Task<QueryLogDto?> FetchQueryLogAsync(NpgsqlConnection conn, long id, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            SELECT q.id, q.db_id, q.speed_class::text, q.duration_ms, q.rows_returned,
                   q.index_used, q.is_optimized, left(q.query_text, 500),
                   q.created_at, q.optimized_query_text,
                   o.duration_before_ms, o.duration_after_ms, o.improvement_pct, o.index_applied
            FROM query_log q
            LEFT JOIN LATERAL (
                SELECT duration_before_ms, duration_after_ms, improvement_pct, index_applied
                FROM query_optimizations WHERE query_log_id = q.id ORDER BY id DESC LIMIT 1
            ) o ON TRUE
            WHERE q.id = @id
            """, conn);
        cmd.Parameters.AddWithValue("id", id);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? ReadQueryLogRow(r) : null;
    }
}
