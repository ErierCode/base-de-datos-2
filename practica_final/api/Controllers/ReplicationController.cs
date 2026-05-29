using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/[controller]")]
public class ReplicationController : ControllerBase
{
    private readonly ReplicationService _replication;

    public ReplicationController(ReplicationService replication) => _replication = replication;

    [HttpGet("latest")]
    public async Task<ActionResult<ReplicationLatestDto>> Latest(CancellationToken ct)
        => Ok(await _replication.GetLatestAsync(ct));

    [HttpGet("history")]
    public async Task<ActionResult<IReadOnlyList<ReplicationSampleDto>>> History(
        [FromQuery] int limit = 120, CancellationToken ct = default)
        => Ok(await _replication.GetHistoryAsync(limit, ct));

    [HttpGet("thresholds")]
    public async Task<ActionResult<ReplicationThresholdsDto>> Thresholds(CancellationToken ct)
        => Ok(await _replication.GetThresholdsAsync(ct));
}
