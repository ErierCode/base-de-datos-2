using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

public sealed class ControlDb
{
    private readonly string _cs;

    public ControlDb(IConfiguration config)
    {
        _cs = config.GetConnectionString("ControlDb")
            ?? throw new InvalidOperationException("ConnectionStrings:ControlDb requerido.");
    }

    public async Task<NpgsqlConnection> OpenAsync(CancellationToken ct = default)
    {
        var conn = new NpgsqlConnection(_cs);
        await conn.OpenAsync(ct);
        return conn;
    }

    public async Task<IReadOnlyList<ConnectionResponse>> ListConnectionsAsync(CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, nombre, motor::text, host, port, database_name, user_name, status::text, created_at
            FROM connections ORDER BY id
            """, conn);
        var list = new List<ConnectionResponse>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new ConnectionResponse(
                r.GetInt32(0), r.GetString(1), r.GetString(2), r.GetString(3), r.GetInt32(4),
                r.GetString(5), r.GetString(6), r.GetString(7), r.GetDateTime(8)));
        }
        return list;
    }

    public async Task<ConnectionResponse?> GetConnectionAsync(int id, CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, nombre, motor::text, host, port, database_name, user_name, status::text, created_at
            FROM connections WHERE id = @id
            """, conn);
        cmd.Parameters.AddWithValue("id", id);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct)) return null;
        return new ConnectionResponse(
            r.GetInt32(0), r.GetString(1), r.GetString(2), r.GetString(3), r.GetInt32(4),
            r.GetString(5), r.GetString(6), r.GetString(7), r.GetDateTime(8));
    }

    public async Task<int> UpsertConnectionAsync(
        ConnectionCreateRequest req,
        byte[] cipher,
        string algo,
        string status,
        CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            INSERT INTO connections (
              nombre, motor, host, port, database_name, user_name,
              password_ciphertext, password_algo, status
            ) VALUES (
              @n, @m::motor_t, @h, @p, @db, @u, @pw, @algo, @st::connection_status_t
            )
            ON CONFLICT (nombre) DO UPDATE SET
              motor = EXCLUDED.motor,
              host = EXCLUDED.host,
              port = EXCLUDED.port,
              database_name = EXCLUDED.database_name,
              user_name = EXCLUDED.user_name,
              password_ciphertext = EXCLUDED.password_ciphertext,
              password_algo = EXCLUDED.password_algo,
              status = EXCLUDED.status,
              password_updated_at = NOW()
            RETURNING id
            """, conn);
        cmd.Parameters.AddWithValue("n", req.Nombre);
        cmd.Parameters.AddWithValue("m", req.Motor.ToUpperInvariant());
        cmd.Parameters.AddWithValue("h", req.Host);
        cmd.Parameters.AddWithValue("p", req.Port);
        cmd.Parameters.AddWithValue("db", req.DatabaseName);
        cmd.Parameters.AddWithValue("u", req.UserName);
        cmd.Parameters.AddWithValue("pw", cipher);
        cmd.Parameters.AddWithValue("algo", algo);
        cmd.Parameters.AddWithValue("st", status);
        return Convert.ToInt32(await cmd.ExecuteScalarAsync(ct));
    }

    public async Task<int> InsertConnectionAsync(
        ConnectionCreateRequest req,
        byte[] cipher,
        string algo,
        string status,
        CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            INSERT INTO connections (
              nombre, motor, host, port, database_name, user_name,
              password_ciphertext, password_algo, status
            ) VALUES (
              @n, @m::motor_t, @h, @p, @db, @u, @pw, @algo, @st::connection_status_t
            ) RETURNING id
            """, conn);
        cmd.Parameters.AddWithValue("n", req.Nombre);
        cmd.Parameters.AddWithValue("m", req.Motor.ToUpperInvariant());
        cmd.Parameters.AddWithValue("h", req.Host);
        cmd.Parameters.AddWithValue("p", req.Port);
        cmd.Parameters.AddWithValue("db", req.DatabaseName);
        cmd.Parameters.AddWithValue("u", req.UserName);
        cmd.Parameters.AddWithValue("pw", cipher);
        cmd.Parameters.AddWithValue("algo", algo);
        cmd.Parameters.AddWithValue("st", status);
        return Convert.ToInt32(await cmd.ExecuteScalarAsync(ct));
    }

    public async Task DeleteConnectionAsync(int id, CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand("DELETE FROM connections WHERE id = @id", conn);
        cmd.Parameters.AddWithValue("id", id);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<HealthSnapshotResponse>> LatestHealthAsync(CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT db_id, nombre, motor::text, health_grade::text,
                   cpu_pct, memory_pct, connections, locks, deadlocks,
                   disk_usage_mb, capture_time, collect_error
            FROM v_connection_latest_health
            ORDER BY nombre
            """, conn);
        var list = new List<HealthSnapshotResponse>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new HealthSnapshotResponse(
                r.GetInt32(0), r.GetString(1), r.GetString(2), r.GetString(3),
                r.GetDecimal(4), r.GetDecimal(5), r.GetInt32(6), r.GetInt32(7), r.GetInt32(8),
                r.GetDecimal(9), r.GetDateTime(10), r.IsDBNull(11) ? null : r.GetString(11)));
        }
        return list;
    }

    public async Task<IReadOnlyList<MetricPointDto>> MetricsHistoryAsync(int dbId, int limit, CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT capture_time, cpu_pct, memory_pct, connections, health_grade::text
            FROM db_metrics WHERE db_id = @id ORDER BY capture_time DESC LIMIT @lim
            """, conn);
        cmd.Parameters.AddWithValue("id", dbId);
        cmd.Parameters.AddWithValue("lim", limit);
        var list = new List<MetricPointDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new MetricPointDto(
                r.GetDateTime(0), r.GetDecimal(1), r.GetDecimal(2), r.GetInt32(3), r.GetString(4)));
        }
        list.Reverse();
        return list;
    }

    public async Task<ThresholdsDto> GetThresholdsAsync(CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT cpu_warning_pct, cpu_critical_pct, memory_warning_pct, memory_critical_pct,
                   conn_warning_pct, conn_critical_pct, locks_warning, locks_critical,
                   deadlocks_warning, deadlocks_critical
            FROM health_thresholds WHERE nombre = 'global' LIMIT 1
            """, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct)) throw new InvalidOperationException("Umbrales no configurados.");
        return new ThresholdsDto(
            r.GetDecimal(0), r.GetDecimal(1), r.GetDecimal(2), r.GetDecimal(3),
            r.GetDecimal(4), r.GetDecimal(5), r.GetInt32(6), r.GetInt32(7),
            r.GetInt32(8), r.GetInt32(9));
    }

    public async Task UpdateThresholdsAsync(ThresholdsDto t, CancellationToken ct)
    {
        await using var conn = await OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            UPDATE health_thresholds SET
              cpu_warning_pct=@a, cpu_critical_pct=@b,
              memory_warning_pct=@c, memory_critical_pct=@d,
              conn_warning_pct=@e, conn_critical_pct=@f,
              locks_warning=@g, locks_critical=@h,
              deadlocks_warning=@i, deadlocks_critical=@j
            WHERE nombre='global'
            """, conn);
        cmd.Parameters.AddWithValue("a", t.CpuWarningPct);
        cmd.Parameters.AddWithValue("b", t.CpuCriticalPct);
        cmd.Parameters.AddWithValue("c", t.MemoryWarningPct);
        cmd.Parameters.AddWithValue("d", t.MemoryCriticalPct);
        cmd.Parameters.AddWithValue("e", t.ConnWarningPct);
        cmd.Parameters.AddWithValue("f", t.ConnCriticalPct);
        cmd.Parameters.AddWithValue("g", t.LocksWarning);
        cmd.Parameters.AddWithValue("h", t.LocksCritical);
        cmd.Parameters.AddWithValue("i", t.DeadlocksWarning);
        cmd.Parameters.AddWithValue("j", t.DeadlocksCritical);
        await cmd.ExecuteNonQueryAsync(ct);
    }
}
