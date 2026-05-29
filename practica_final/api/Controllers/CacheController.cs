using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/[controller]")]
public class CacheController : ControllerBase
{
    private readonly DashboardCacheService _cache;

    public CacheController(DashboardCacheService cache) => _cache = cache;

    [HttpGet("stats")]
    public async Task<ActionResult<CacheStatsDto>> Stats(CancellationToken ct)
        => Ok(await _cache.GetStatsAsync(ct));

    [HttpGet("events")]
    public async Task<ActionResult<IReadOnlyList<CacheEventDto>>> Events(
        [FromQuery] int limit = 40, CancellationToken ct = default)
        => Ok(await _cache.ListEventsAsync(limit, ct));

    /// <summary>Demuestra miss (~400ms) o hit (~40ms) según forceRefresh.</summary>
    [HttpGet("demo")]
    public async Task<ActionResult<CacheDemoDto>> Demo(
        [FromQuery] bool forceRefresh = false, CancellationToken ct = default)
        => Ok(await _cache.RunDemoAsync(forceRefresh, ct));

    [HttpPost("invalidate")]
    public async Task<IActionResult> Invalidate(CancellationToken ct)
    {
        await _cache.InvalidateAsync(ct);
        return Ok(new { ok = true, message = "Cache invalidada (invalidacion manual por evento)." });
    }
}
