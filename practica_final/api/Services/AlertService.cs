using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

public sealed class AlertService
{
    private readonly ControlDb _db;

    public AlertService(ControlDb db) => _db = db;

    public async Task<IReadOnlyList<AlertRuleDto>> ListRulesAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, code, name, enabled, metric_source, threshold_num, window_minutes,
                   severity::text, action::text, cooldown_sec, description
            FROM alert_rules ORDER BY id
            """, conn);
        var list = new List<AlertRuleDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            list.Add(ReadRule(r));
        return list;
    }

    public async Task<AlertRuleDto?> UpdateRuleAsync(int id, AlertRuleUpdateDto patch, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            UPDATE alert_rules SET
              enabled = COALESCE(@en, enabled),
              threshold_num = COALESCE(@th, threshold_num),
              window_minutes = COALESCE(@win, window_minutes),
              severity = COALESCE(@sev::alert_severity_t, severity),
              action = COALESCE(@act::alert_action_t, action),
              cooldown_sec = COALESCE(@cd, cooldown_sec),
              updated_at = NOW()
            WHERE id = @id
            RETURNING id, code, name, enabled, metric_source, threshold_num, window_minutes,
                      severity::text, action::text, cooldown_sec, description
            """, conn);
        cmd.Parameters.AddWithValue("id", id);
        cmd.Parameters.AddWithValue("en", (object?)patch.Enabled ?? DBNull.Value);
        cmd.Parameters.AddWithValue("th", (object?)patch.ThresholdNum ?? DBNull.Value);
        cmd.Parameters.AddWithValue("win", (object?)patch.WindowMinutes ?? DBNull.Value);
        cmd.Parameters.AddWithValue("sev", (object?)patch.Severity ?? DBNull.Value);
        cmd.Parameters.AddWithValue("act", (object?)patch.Action ?? DBNull.Value);
        cmd.Parameters.AddWithValue("cd", (object?)patch.CooldownSec ?? DBNull.Value);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? ReadRule(r) : null;
    }

    public async Task<IReadOnlyList<AlertLogDto>> ListAlertsAsync(int limit, bool openOnly, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        var sql = """
            SELECT a.id, a.rule_id, r.code, a.db_id, a.severity::text, a.condition_text,
                   a.message, a.status::text, a.action_taken::text, a.engine_name,
                   a.triggered_at, a.resolved_at
            FROM alert_log a
            LEFT JOIN alert_rules r ON r.id = a.rule_id
            """;
        if (openOnly) sql += " WHERE a.status = 'OPEN'";
        sql += " ORDER BY a.triggered_at DESC LIMIT @lim";
        await using var cmd = new NpgsqlCommand(sql, conn);
        cmd.Parameters.AddWithValue("lim", Math.Clamp(limit, 5, 200));
        var list = new List<AlertLogDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new AlertLogDto(
                r.GetInt64(0),
                r.IsDBNull(1) ? null : r.GetInt32(1),
                r.IsDBNull(2) ? null : r.GetString(2),
                r.IsDBNull(3) ? null : r.GetInt32(3),
                r.GetString(4),
                r.GetString(5),
                r.IsDBNull(6) ? null : r.GetString(6),
                r.GetString(7),
                r.IsDBNull(8) ? null : r.GetString(8),
                r.IsDBNull(9) ? null : r.GetString(9),
                r.GetDateTime(10),
                r.IsDBNull(11) ? null : r.GetDateTime(11)));
        }
        return list;
    }

    public async Task<bool> ResolveAlertAsync(long id, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            UPDATE alert_log SET status = 'RESOLVED', resolved_at = NOW()
            WHERE id = @id AND status <> 'RESOLVED'
            """, conn);
        cmd.Parameters.AddWithValue("id", id);
        return await cmd.ExecuteNonQueryAsync(ct) > 0;
    }

    public async Task InsertWebhookAlertAsync(string summary, string severity, CancellationToken ct)
    {
        var sev = severity.Equals("critical", StringComparison.OrdinalIgnoreCase) ? "CRITICAL" : "WARNING";
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            INSERT INTO alert_log (severity, condition_text, message, action_taken, engine_name)
            VALUES (@sev::alert_severity_t, @cond, @msg, 'DASHBOARD'::alert_action_t, 'prometheus')
            """, conn);
        cmd.Parameters.AddWithValue("sev", sev);
        cmd.Parameters.AddWithValue("cond", "alertmanager_webhook");
        cmd.Parameters.AddWithValue("msg", summary);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static AlertRuleDto ReadRule(NpgsqlDataReader r) => new(
        r.GetInt32(0), r.GetString(1), r.GetString(2), r.GetBoolean(3),
        r.GetString(4), r.GetDouble(5), r.GetInt32(6),
        r.GetString(7), r.GetString(8), r.GetInt32(9),
        r.IsDBNull(10) ? null : r.GetString(10));
}
