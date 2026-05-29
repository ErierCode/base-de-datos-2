using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

/// <summary>Módulo 5 — lectura de BACKUP_HISTORY, SLA (RPO/RTO) y estado de replicación a nube.</summary>
public sealed class BackupService
{
    private readonly ControlDb _db;
    private readonly IConfiguration _config;

    public BackupService(ControlDb db, IConfiguration config)
    {
        _db = db;
        _config = config;
    }

    public async Task<BackupSlaDashboardDto> GetSlaDashboardAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT
                v.target_rpo_sec,
                v.target_rto_sec,
                t.description,
                v.seconds_since_full_restore_point,
                v.last_full_restore_point,
                v.meets_rpo_objective_vs_last_full_now,
                last_full.rto_observed_sec,
                last_full.sla_met
            FROM v_backup_sla_last v
            JOIN backup_sla_targets t ON t.id = 1
            LEFT JOIN LATERAL (
                SELECT bh.rto_observed_sec, bh.sla_met
                FROM backup_history bh
                WHERE bh.kind = 'FULL'::backup_kind_t
                  AND COALESCE(bh.purged, false) = false
                ORDER BY bh.id DESC
                LIMIT 1
            ) AS last_full ON TRUE
            """, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct))
        {
            await r.CloseAsync();
            var cloudEmpty = await HasCloudBackupsAsync(conn, ct);
            return BuildSlaDto(900, 2700, null, null, null, false, null, null, cloudEmpty);
        }

        var targetRpo = r.GetInt32(0);
        var targetRto = r.GetInt32(1);
        var desc = r.IsDBNull(2) ? null : r.GetString(2);
        var secsSince = r.IsDBNull(3) ? (double?)null : r.GetDouble(3);
        var lastRp = r.IsDBNull(4) ? (DateTime?)null : r.GetDateTime(4);
        var meetsRpo = !r.IsDBNull(5) && r.GetBoolean(5);
        var rtoObs = r.IsDBNull(6) ? (double?)null : r.GetDouble(6);
        bool? meetsRto = rtoObs.HasValue ? rtoObs.Value <= targetRto : null;

        await r.CloseAsync();
        var cloudFromDb = await HasCloudBackupsAsync(conn, ct);
        return BuildSlaDto(targetRpo, targetRto, desc, secsSince, lastRp, meetsRpo, rtoObs, meetsRto, cloudFromDb);
    }

    private static async Task<bool> HasCloudBackupsAsync(NpgsqlConnection conn, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            SELECT EXISTS (
                SELECT 1 FROM backup_history
                WHERE COALESCE(purged, false) = false
                  AND (
                    cloud_object_key IS NOT NULL
                    OR COALESCE(remote_url, '') <> ''
                  )
                LIMIT 1
            )
            """, conn);
        var scalar = await cmd.ExecuteScalarAsync(ct);
        return scalar is bool b && b;
    }

    public async Task<IReadOnlyList<BackupHistoryDto>> ListHistoryAsync(int limit, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, kind::text, size_mb, duration_sec, restore_point,
                   NULLIF(local_path,''), remote_url, cloud_object_key,
                   checksum_sha256, depends_on_id, parent_full_id,
                   snapshot_label, notes, included_tables,
                   rpo_estimate_sec, rto_observed_sec, sla_met, purged, created_at
            FROM backup_history
            ORDER BY created_at DESC, id DESC
            LIMIT @lim
            """, conn);
        cmd.Parameters.AddWithValue("lim", Math.Clamp(limit, 5, 100));
        var list = new List<BackupHistoryDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            list.Add(ReadRow(r));
        return list;
    }

    public async Task<IReadOnlyList<BackupHistoryDto>> GetRestoreChainAsync(long anchorId, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            WITH RECURSIVE chain AS (
                SELECT bh.* FROM backup_history bh WHERE bh.id = @id
                UNION ALL
                SELECT bh.* FROM backup_history bh
                  INNER JOIN chain c ON bh.depends_on_id = c.id
            )
            SELECT id, kind::text, size_mb, duration_sec, restore_point,
                   NULLIF(local_path,''), remote_url, cloud_object_key,
                   checksum_sha256, depends_on_id, parent_full_id,
                   snapshot_label, notes, included_tables,
                   rpo_estimate_sec, rto_observed_sec, sla_met, purged, created_at
            FROM chain
            ORDER BY created_at ASC, id ASC
            """, conn);
        cmd.Parameters.AddWithValue("id", anchorId);
        var list = new List<BackupHistoryDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            list.Add(ReadRow(r));
        return list;
    }

    private BackupSlaDashboardDto BuildSlaDto(
        int targetRpo,
        int targetRto,
        string? desc,
        double? secsSince,
        DateTime? lastRp,
        bool meetsRpo,
        double? rtoObs,
        bool? meetsRto,
        bool cloudFromHistory)
    {
        var bucket = _config["Backup:S3Bucket"]
            ?? _config["S3_BUCKET"]
            ?? Environment.GetEnvironmentVariable("S3_BUCKET")
            ?? "";
        var endpoint = _config["Backup:S3EndpointUrl"]
            ?? _config["S3_ENDPOINT_URL"]
            ?? Environment.GetEnvironmentVariable("S3_ENDPOINT_URL")
            ?? "";
        var cloudOn = !string.IsNullOrWhiteSpace(bucket) || cloudFromHistory;
        string hint;
        if (!string.IsNullOrWhiteSpace(bucket))
            hint = string.IsNullOrWhiteSpace(endpoint) ? "Amazon S3" : "S3-compatible (MinIO / custom endpoint)";
        else if (cloudFromHistory)
            hint = "Amazon S3 activo (backups en nube). Reinicie api: docker compose up -d api";
        else
            hint = "Solo local (configure S3_BUCKET en .env y reinicie api + backup-worker)";

        return new BackupSlaDashboardDto(
            targetRpo,
            targetRto,
            desc,
            secsSince,
            lastRp,
            meetsRpo,
            meetsRto,
            rtoObs,
            cloudOn,
            hint);
    }

    private static BackupHistoryDto ReadRow(NpgsqlDataReader r) => new(
        r.GetInt64(0),
        r.GetString(1),
        r.GetDecimal(2),
        r.GetDecimal(3),
        r.GetDateTime(4),
        r.IsDBNull(5) ? null : r.GetString(5),
        r.IsDBNull(6) ? null : r.GetString(6),
        r.IsDBNull(7) ? null : r.GetString(7),
        r.GetString(8),
        r.IsDBNull(9) ? null : r.GetInt64(9),
        r.IsDBNull(10) ? null : r.GetInt64(10),
        r.IsDBNull(11) ? null : r.GetString(11),
        r.IsDBNull(12) ? null : r.GetString(12),
        r.IsDBNull(13) ? null : r.GetString(13),
        r.IsDBNull(14) ? null : r.GetDouble(14),
        r.IsDBNull(15) ? null : r.GetDouble(15),
        r.GetBoolean(16),
        r.GetBoolean(17),
        r.GetDateTime(18));
}
