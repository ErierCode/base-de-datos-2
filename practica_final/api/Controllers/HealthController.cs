using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/[controller]")]
public class HealthController : ControllerBase
{
    private readonly ControlDb _db;

    public HealthController(ControlDb db) => _db = db;

    /// <summary>Último estado por motor (vista dashboard Módulo 2).</summary>
    [HttpGet("latest")]
    public async Task<ActionResult<IReadOnlyList<HealthSnapshotResponse>>> Latest(CancellationToken ct)
        => Ok(await _db.LatestHealthAsync(ct));

    [HttpGet("{dbId:int}/history")]
    public async Task<ActionResult<IReadOnlyList<MetricPointDto>>> History(
        int dbId, [FromQuery] int limit = 60, CancellationToken ct = default)
        => Ok(await _db.MetricsHistoryAsync(dbId, Math.Clamp(limit, 5, 500), ct));

    [HttpGet("thresholds")]
    public async Task<ActionResult<ThresholdsDto>> GetThresholds(CancellationToken ct)
        => Ok(await _db.GetThresholdsAsync(ct));

    [HttpPut("thresholds")]
    public async Task<IActionResult> PutThresholds([FromBody] ThresholdsDto dto, CancellationToken ct)
    {
        await _db.UpdateThresholdsAsync(dto, ct);
        return NoContent();
    }
}
