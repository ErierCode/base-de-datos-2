using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/[controller]")]
public class ConcurrencyController : ControllerBase
{
    private readonly ConcurrencyService _svc;

    public ConcurrencyController(ConcurrencyService svc) => _svc = svc;

    [HttpGet("summary")]
    public async Task<ActionResult<ConcurrencySummaryDto>> Summary(CancellationToken ct)
        => Ok(await _svc.GetSummaryAsync(ct));

    [HttpGet("tx-log")]
    public async Task<ActionResult<IReadOnlyList<TxLogDto>>> TxLog([FromQuery] int limit = 100, CancellationToken ct = default)
        => Ok(await _svc.ListTxLogAsync(Math.Clamp(limit, 10, 500), ct));

    [HttpGet("deadlocks")]
    public async Task<ActionResult<IReadOnlyList<DeadlockEventDto>>> Deadlocks(
        [FromQuery] int limit = 50, CancellationToken ct = default)
        => Ok(await _svc.ListDeadlockEventsAsync(Math.Clamp(limit, 5, 200), ct));
}
