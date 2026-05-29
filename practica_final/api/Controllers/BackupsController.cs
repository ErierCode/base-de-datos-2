using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/[controller]")]
public class BackupsController : ControllerBase
{
    private readonly BackupService _backups;

    public BackupsController(BackupService backups) => _backups = backups;

    /// <summary>Dashboard SLA Módulo 5: RPO/RTO objetivo vs estado actual.</summary>
    [HttpGet("sla")]
    public async Task<ActionResult<BackupSlaDashboardDto>> Sla(CancellationToken ct)
        => Ok(await _backups.GetSlaDashboardAsync(ct));

    /// <summary>Historial reciente (FULL / DIFF / INC) con URL remoto y checksum.</summary>
    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<BackupHistoryDto>>> List(
        [FromQuery] int limit = 30, CancellationToken ct = default)
        => Ok(await _backups.ListHistoryAsync(limit, ct));

    /// <summary>Cadena de restauración FULL → DIFF → INC desde un ancla (p. ej. último FULL).</summary>
    [HttpGet("{anchorId:long}/chain")]
    public async Task<ActionResult<IReadOnlyList<BackupHistoryDto>>> Chain(long anchorId, CancellationToken ct)
        => Ok(await _backups.GetRestoreChainAsync(anchorId, ct));
}
