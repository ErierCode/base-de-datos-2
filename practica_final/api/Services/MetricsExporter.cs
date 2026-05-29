using Npgsql;
using Prometheus;

namespace DataOps.Api.Services;

/// <summary>Expone gauges desde db_metrics para Grafana/Prometheus (Módulo 2).</summary>
public sealed class MetricsExporter : BackgroundService
{
    private static readonly Gauge CpuGauge = Metrics.CreateGauge(
        "dcc_db_cpu_percent", "CPU proxy %", new GaugeConfiguration { LabelNames = ["connection", "db_id"] });
    private static readonly Gauge HealthGauge = Metrics.CreateGauge(
        "dcc_db_health_grade", "0=HEALTHY 1=WARNING 2=CRITICAL", new GaugeConfiguration { LabelNames = ["connection", "db_id"] });
    private static readonly Gauge ConnGauge = Metrics.CreateGauge(
        "dcc_db_connections", "Conexiones activas", new GaugeConfiguration { LabelNames = ["connection", "db_id"] });

    private readonly ControlDb _db;
    private readonly ILogger<MetricsExporter> _log;

    public MetricsExporter(ControlDb db, ILogger<MetricsExporter> log)
    {
        _db = db;
        _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await RefreshAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _log.LogWarning(ex, "Refresh métricas Prometheus falló");
            }
            await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
        }
    }

    private async Task RefreshAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT DISTINCT ON (m.db_id)
              m.db_id, c.nombre, m.cpu_pct, m.connections, m.health_grade::text
            FROM db_metrics m
            JOIN connections c ON c.id = m.db_id
            ORDER BY m.db_id, m.capture_time DESC
            """, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            var id = r.GetInt32(0).ToString();
            var name = r.GetString(1);
            var cpu = (double)r.GetDecimal(2);
            var conns = r.GetInt32(3);
            var grade = r.GetString(4);
            var g = grade switch
            {
                "WARNING" => 1.0,
                "CRITICAL" => 2.0,
                _ => 0.0
            };
            CpuGauge.WithLabels(name, id).Set(cpu);
            ConnGauge.WithLabels(name, id).Set(conns);
            HealthGauge.WithLabels(name, id).Set(g);
        }
    }
}
