using DataOps.Api.Models;
using Npgsql;

namespace DataOps.Api.Services;

/// <summary>Módulo 4 — detecta deadlocks en tx_log y registra resolución automática del motor.</summary>
public sealed class DeadlockMonitorService : BackgroundService
{
    private readonly ControlDb _db;
    private readonly ILogger<DeadlockMonitorService> _log;

    public DeadlockMonitorService(ControlDb db, ILogger<DeadlockMonitorService> log)
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
                await ScanAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _log.LogWarning(ex, "Escaneo deadlocks falló");
            }
            await Task.Delay(TimeSpan.FromSeconds(8), stoppingToken);
        }
    }

    private async Task ScanAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            INSERT INTO deadlock_events (db_id, tx_log_id, session_id, detected_at, resolution_action, resolved_at, detail)
            SELECT t.db_id, t.id, t.session, t.fin,
                   'POSTGRES_ROLLBACK_VICTIM',
                   t.fin,
                   'PostgreSQL abortó una transacción víctima; la sesión puede reintentar.'
            FROM tx_log t
            WHERE t.lock_type = 'DEADLOCK'::lock_type_t
              AND NOT EXISTS (SELECT 1 FROM deadlock_events d WHERE d.tx_log_id = t.id)
            """, conn);
        var n = await cmd.ExecuteNonQueryAsync(ct);
        if (n > 0)
            _log.LogWarning("Deadlocks detectados y registrados: {Count}", n);
    }
}
