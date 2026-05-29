using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

/// <summary>Módulo 6 — lag de replicación primario-réplica (tiempo real vía replication_lag_samples).</summary>
public sealed class ReplicationService
{
    private readonly ControlDb _db;

    public ReplicationService(ControlDb db) => _db = db;

    public async Task<ReplicationThresholdsDto> GetThresholdsAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT acceptable_max_sec, warning_ceiling_sec, critical_min_sec
            FROM replication_lag_thresholds WHERE id = 1
            """, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct))
            return new ReplicationThresholdsDto(2, 5, 20,
                "Carga normal <=2s Aceptable; media ~5s Advertencia; alta >=20s Critico.");

        return new ReplicationThresholdsDto(
            r.GetDouble(0),
            r.GetDouble(1),
            r.GetDouble(2),
            "Carga normal <=2s Aceptable; media ~5s Advertencia; alta >=20s Critico.");
    }

    public async Task<ReplicationLatestDto> GetLatestAsync(CancellationToken ct)
    {
        var thresholds = await GetThresholdsAsync(ct);
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, lag_seconds, grade::text, scenario_label, captured_at, standby_state
            FROM replication_lag_samples
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct))
            return new ReplicationLatestDto(null, thresholds);

        return new ReplicationLatestDto(ReadSample(r), thresholds);
    }

    public async Task<IReadOnlyList<ReplicationSampleDto>> GetHistoryAsync(int limit, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, lag_seconds, grade::text, scenario_label, captured_at, standby_state
            FROM replication_lag_samples
            ORDER BY captured_at DESC, id DESC
            LIMIT @lim
            """, conn);
        cmd.Parameters.AddWithValue("lim", Math.Clamp(limit, 10, 500));
        var list = new List<ReplicationSampleDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            list.Add(ReadSample(r));
        list.Reverse();
        return list;
    }

    private static ReplicationSampleDto ReadSample(NpgsqlDataReader r) => new(
        r.GetInt64(0),
        r.GetDouble(1),
        r.GetString(2),
        r.IsDBNull(3) ? null : r.GetString(3),
        r.GetDateTime(4),
        r.IsDBNull(5) ? null : r.GetString(5));
}
