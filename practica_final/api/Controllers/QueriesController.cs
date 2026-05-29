using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/[controller]")]
public class QueriesController : ControllerBase
{
    private readonly QueryOptimizationService _queries;

    public QueriesController(QueryOptimizationService queries) => _queries = queries;

    /// <summary>Top consultas (incluye SLOW/CRITICAL) desde query_log.</summary>
    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<QueryLogDto>>> List([FromQuery] int limit = 30, CancellationToken ct = default)
        => Ok(await _queries.ListSlowQueriesAsync(Math.Clamp(limit, 5, 200), ct));

    /// <summary>Prepara laboratorio query_lab, ejecuta baseline lento y registra en query_log.</summary>
    [HttpPost("lab/baseline")]
    public async Task<ActionResult<QueryLogDto>> LabBaseline([FromQuery] int dbId = 1, CancellationToken ct = default)
        => Ok(await _queries.SetupLabAndBaselineAsync(dbId, ct));

    /// <summary>Aplica índice, re-mide y guarda evidencia antes/después (Módulo 3).</summary>
    [HttpPost("{id:long}/optimize")]
    public async Task<ActionResult<OptimizationResultDto>> Optimize(long id, CancellationToken ct = default)
    {
        try
        {
            return Ok(await _queries.OptimizeQueryLogAsync(id, ct));
        }
        catch (KeyNotFoundException)
        {
            return NotFound();
        }
        catch (InvalidOperationException ex)
        {
            return Conflict(new { message = ex.Message });
        }
    }
}
