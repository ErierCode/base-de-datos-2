using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/v1/[controller]")]
public class DashboardController : ControllerBase
{
    private readonly DashboardCacheService _cache;

    public DashboardController(DashboardCacheService cache) => _cache = cache;

    [HttpGet("summary")]
    public async Task<ActionResult<DashboardSummaryDto>> Summary(
        [FromQuery] bool forceRefresh = false, CancellationToken ct = default)
        => Ok(await _cache.GetSummaryAsync(forceRefresh, ct));

    [HttpPost("cache/invalidate")]
    public async Task<IActionResult> Invalidate(CancellationToken ct)
    {
        await _cache.InvalidateAsync(ct);
        return Ok(new { ok = true });
    }
}
