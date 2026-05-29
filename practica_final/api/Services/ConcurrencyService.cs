using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

public sealed class ConcurrencyService
{
    private readonly ControlDb _db;

    public ConcurrencyService(ControlDb db) => _db = db;

    public async Task<ConcurrencySummaryDto> GetSummaryAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            "SELECT ops_24h, deadlocks_24h, timeouts_24h, avg_wait_ms_24h FROM v_concurrency_summary", conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct))
            return new ConcurrencySummaryDto(0, 0, 0, 0);
        return new ConcurrencySummaryDto(
            r.GetInt64(0), r.GetInt64(1), r.GetInt64(2), r.GetInt32(3));
    }

    public async Task<IReadOnlyList<TxLogDto>> ListTxLogAsync(int limit, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, db_id, session, operacion::text, inicio, fin, wait_time, lock_type::text
            FROM tx_log ORDER BY fin DESC LIMIT @lim
            """, conn);
        cmd.Parameters.AddWithValue("lim", limit);
        var list = new List<TxLogDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new TxLogDto(
                r.GetInt64(0), r.GetInt32(1), r.GetString(2), r.GetString(3),
                r.GetDateTime(4), r.GetDateTime(5), r.GetInt32(6), r.GetString(7)));
        }
        return list;
    }

    public async Task<IReadOnlyList<DeadlockEventDto>> ListDeadlockEventsAsync(int limit, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT d.id, d.db_id, d.session_id, d.detected_at, d.resolution_action,
                   d.resolved_at, d.detail, t.wait_time
            FROM deadlock_events d
            LEFT JOIN tx_log t ON t.id = d.tx_log_id
            ORDER BY d.detected_at DESC LIMIT @lim
            """, conn);
        cmd.Parameters.AddWithValue("lim", limit);
        var list = new List<DeadlockEventDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new DeadlockEventDto(
                r.GetInt64(0),
                r.IsDBNull(1) ? null : r.GetInt32(1),
                r.IsDBNull(2) ? null : r.GetString(2),
                r.GetDateTime(3),
                r.GetString(4),
                r.IsDBNull(5) ? null : r.GetDateTime(5),
                r.IsDBNull(6) ? null : r.GetString(6),
                r.IsDBNull(7) ? null : r.GetInt32(7)));
        }
        return list;
    }
}
