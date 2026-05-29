using System.Text.Json;
using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

/// <summary>Módulo 9 — evalúa alert_rules contra métricas y escribe alert_log (configurable sin redeploy).</summary>
public sealed class AlertEngineService : BackgroundService
{
    private readonly ControlDb _db;
    private readonly AlertEmailSender _email;
    private readonly ILogger<AlertEngineService> _log;

    public AlertEngineService(ControlDb db, AlertEmailSender email, ILogger<AlertEngineService> log)
    {
        _db = db;
        _email = email;
        _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await Task.Delay(TimeSpan.FromSeconds(15), stoppingToken);
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await EvaluateAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _log.LogWarning(ex, "Ciclo motor de alertas falló");
            }
            await Task.Delay(TimeSpan.FromSeconds(45), stoppingToken);
        }
    }

    private async Task EvaluateAsync(CancellationToken ct)
    {
        var rules = await LoadRulesAsync(ct);
        if (rules.Count == 0) return;

        await using var conn = await _db.OpenAsync(ct);
        foreach (var rule in rules.Where(r => r.Enabled))
        {
            var hits = await EvaluateRuleAsync(conn, rule, ct);
            foreach (var hit in hits)
            {
                if (await IsInCooldownAsync(conn, rule.Id, hit.DbId, rule.CooldownSec, ct))
                    continue;

                await InsertAlertAsync(conn, rule, hit, ct);
                if (rule.Action is "EMAIL" or "EMAIL_DASHBOARD")
                {
                    await _email.SendAsync(
                        $"[DCC {rule.Severity}] {rule.Name}",
                        hit.Message,
                        ct);
                }
                _log.LogWarning("Alerta {Code} db={Db} {Msg}", rule.Code, hit.DbId, hit.Condition);
            }
        }
    }

    private async Task<List<RuleHit>> EvaluateRuleAsync(
        NpgsqlConnection conn, AlertRuleDto rule, CancellationToken ct)
    {
        var list = new List<RuleHit>();
        switch (rule.MetricSource)
        {
            case "cpu_pct":
                await foreach (var h in QueryLatestMetricsAsync(conn, rule, "cpu_pct", ct))
                    list.Add(h);
                break;
            case "memory_pct":
                await foreach (var h in QueryLatestMetricsAsync(conn, rule, "memory_pct", ct))
                    list.Add(h);
                break;
            case "conn_pressure_pct":
                await foreach (var h in QueryConnPressureAsync(conn, rule, ct))
                    list.Add(h);
                break;
            case "deadlocks_window":
                list.AddRange(await QueryDeadlocksAsync(conn, rule, ct));
                break;
            case "replication_lag_sec":
                list.AddRange(await QueryReplicationLagAsync(conn, rule, ct));
                break;
            case "backup_sla_fail":
                list.AddRange(await QueryBackupSlaAsync(conn, rule, ct));
                break;
        }
        return list;
    }

    private async IAsyncEnumerable<RuleHit> QueryLatestMetricsAsync(
        NpgsqlConnection conn, AlertRuleDto rule, string column, CancellationToken ct)
    {
        var sql = column switch
        {
            "cpu_pct" => """
                SELECT DISTINCT ON (m.db_id) m.db_id, c.nombre, m.cpu_pct::float8
                FROM db_metrics m JOIN connections c ON c.id = m.db_id
                ORDER BY m.db_id, m.capture_time DESC
                """,
            "memory_pct" => """
                SELECT DISTINCT ON (m.db_id) m.db_id, c.nombre, m.memory_pct::float8
                FROM db_metrics m JOIN connections c ON c.id = m.db_id
                ORDER BY m.db_id, m.capture_time DESC
                """,
            _ => throw new InvalidOperationException(column)
        };
        await using var cmd = new NpgsqlCommand(sql, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            var dbId = r.GetInt32(0);
            var name = r.GetString(1);
            var val = r.GetDouble(2);
            if (val <= rule.ThresholdNum) continue;
            yield return new RuleHit(
                dbId,
                name,
                $"{column}={val:F1} > {rule.ThresholdNum}",
                $"{rule.Name}: {name} — {column} {val:F1}% (umbral {rule.ThresholdNum}%)");
        }
    }

    private async IAsyncEnumerable<RuleHit> QueryConnPressureAsync(
        NpgsqlConnection conn, AlertRuleDto rule, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            SELECT DISTINCT ON (m.db_id) m.db_id, c.nombre, m.connections,
                   GREATEST(1, (SELECT setting::int FROM pg_settings WHERE name='max_connections')) AS max_conn
            FROM db_metrics m JOIN connections c ON c.id = m.db_id
            ORDER BY m.db_id, m.capture_time DESC
            """, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            var dbId = r.GetInt32(0);
            var name = r.GetString(1);
            var conns = r.GetInt32(2);
            var maxConn = r.GetInt32(3);
            var pct = 100.0 * conns / maxConn;
            if (pct <= rule.ThresholdNum) continue;
            yield return new RuleHit(
                dbId,
                name,
                $"conn_pressure={pct:F1}% > {rule.ThresholdNum}",
                $"{rule.Name}: {name} — conexiones {conns}/{maxConn} ({pct:F1}%)");
        }
    }

    private async Task<List<RuleHit>> QueryDeadlocksAsync(
        NpgsqlConnection conn, AlertRuleDto rule, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            SELECT COUNT(*)::int FROM deadlock_events
            WHERE detected_at > NOW() - make_interval(mins => @mins)
            """, conn);
        cmd.Parameters.AddWithValue("mins", rule.WindowMinutes);
        var cnt = Convert.ToInt32(await cmd.ExecuteScalarAsync(ct) ?? 0);
        if (cnt <= rule.ThresholdNum) return [];
        return
        [
            new RuleHit(
                null,
                "plataforma",
                $"deadlocks_{rule.WindowMinutes}m={cnt} > {rule.ThresholdNum}",
                $"{rule.Name}: {cnt} deadlocks en últimos {rule.WindowMinutes} min")
        ];
    }

    private async Task<List<RuleHit>> QueryReplicationLagAsync(
        NpgsqlConnection conn, AlertRuleDto rule, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            SELECT lag_seconds FROM replication_lag_samples
            ORDER BY captured_at DESC LIMIT 1
            """, conn);
        var scalar = await cmd.ExecuteScalarAsync(ct);
        if (scalar is null or DBNull) return [];
        var lag = Convert.ToDouble(scalar);
        if (lag <= rule.ThresholdNum) return [];
        return
        [
            new RuleHit(
                null,
                "replicacion-ha",
                $"replication_lag={lag:F2}s > {rule.ThresholdNum}",
                $"{rule.Name}: lag actual {lag:F2} s")
        ];
    }

    private async Task<List<RuleHit>> QueryBackupSlaAsync(
        NpgsqlConnection conn, AlertRuleDto rule, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            SELECT EXISTS (
              SELECT 1 FROM backup_history
              WHERE kind='FULL' AND COALESCE(purged,false)=false
                AND sla_met = false
                AND created_at > NOW() - make_interval(mins => @mins)
            )
            """, conn);
        cmd.Parameters.AddWithValue("mins", rule.WindowMinutes);
        var fail = (bool)(await cmd.ExecuteScalarAsync(ct) ?? false);
        if (!fail) return [];
        return
        [
            new RuleHit(
                null,
                "backups",
                "backup_sla_fail",
                $"{rule.Name}: último FULL con SLA no cumplido")
        ];
    }

    private static async Task<bool> IsInCooldownAsync(
        NpgsqlConnection conn, int ruleId, int? dbId, int cooldownSec, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            SELECT EXISTS (
              SELECT 1 FROM alert_log
              WHERE rule_id = @rid
                AND (db_id IS NOT DISTINCT FROM @db)
                AND status IN ('OPEN','ACKNOWLEDGED')
                AND triggered_at > NOW() - make_interval(secs => @cd)
            )
            """, conn);
        cmd.Parameters.AddWithValue("rid", ruleId);
        cmd.Parameters.AddWithValue("db", (object?)dbId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("cd", cooldownSec);
        return (bool)(await cmd.ExecuteScalarAsync(ct) ?? false);
    }

    private static async Task InsertAlertAsync(
        NpgsqlConnection conn, AlertRuleDto rule, RuleHit hit, CancellationToken ct)
    {
        await using var cmd = new NpgsqlCommand(
            """
            INSERT INTO alert_log (
              rule_id, db_id, severity, condition_text, message,
              action_taken, engine_name, detail
            ) VALUES (
              @rid, @db, @sev::alert_severity_t, @cond, @msg,
              @act::alert_action_t, @eng,
              @det::jsonb
            )
            """, conn);
        cmd.Parameters.AddWithValue("rid", rule.Id);
        cmd.Parameters.AddWithValue("db", (object?)hit.DbId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("sev", rule.Severity);
        cmd.Parameters.AddWithValue("cond", hit.Condition);
        cmd.Parameters.AddWithValue("msg", hit.Message);
        cmd.Parameters.AddWithValue("act", rule.Action);
        cmd.Parameters.AddWithValue("eng", hit.EngineName);
        cmd.Parameters.AddWithValue("det", JsonSerializer.Serialize(new { rule.Code, hit.EngineName }));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private async Task<List<AlertRuleDto>> LoadRulesAsync(CancellationToken ct)
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
        {
            list.Add(new AlertRuleDto(
                r.GetInt32(0), r.GetString(1), r.GetString(2), r.GetBoolean(3),
                r.GetString(4), r.GetDouble(5), r.GetInt32(6),
                r.GetString(7), r.GetString(8), r.GetInt32(9),
                r.IsDBNull(10) ? null : r.GetString(10)));
        }
        return list;
    }

    private sealed record RuleHit(int? DbId, string EngineName, string Condition, string Message);
}
