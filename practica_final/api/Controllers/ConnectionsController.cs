using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/[controller]")]
public class ConnectionsController : ControllerBase
{
    private readonly ControlDb _db;
    private readonly CredentialProtector _crypto;

    public ConnectionsController(ControlDb db, CredentialProtector crypto)
    {
        _db = db;
        _crypto = crypto;
    }

    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<ConnectionResponse>>> List(CancellationToken ct)
        => Ok(await _db.ListConnectionsAsync(ct));

    [HttpGet("{id:int}")]
    public async Task<ActionResult<ConnectionResponse>> Get(int id, CancellationToken ct)
    {
        var row = await _db.GetConnectionAsync(id, ct);
        return row is null ? NotFound() : Ok(row);
    }

    [HttpPost("test")]
    public async Task<ActionResult<ConnectionTestResult>> Test([FromBody] ConnectionCreateRequest req, CancellationToken ct)
    {
        var (ok, msg) = await ConnectionTester.TestAsync(
            req.Motor, req.Host, req.Port, req.DatabaseName, req.UserName, req.Password, ct);
        return Ok(new ConnectionTestResult(ok, msg));
    }

    /// <summary>Registro Módulo 1: valida conectividad y persiste credencial cifrada.</summary>
    [HttpPost]
    public async Task<ActionResult<ConnectionResponse>> Create([FromBody] ConnectionCreateRequest req, CancellationToken ct)
    {
        var (ok, msg) = await ConnectionTester.TestAsync(
            req.Motor, req.Host, req.Port, req.DatabaseName, req.UserName, req.Password, ct);

        var status = ok ? "ACTIVE" : (req.Motor.ToUpperInvariant() == "POSTGRESQL" ? "ERROR" : "INACTIVE");
        var cipher = _crypto.Encrypt(req.Password);
        var id = await _db.UpsertConnectionAsync(req, cipher, _crypto.Algorithm, status, ct);
        var created = await _db.GetConnectionAsync(id, ct);
        return Ok(new
        {
            connection = created,
            connectivity = new ConnectionTestResult(ok, msg)
        });
    }

    [HttpDelete("{id:int}")]
    public async Task<IActionResult> Delete(int id, CancellationToken ct)
    {
        if (await _db.GetConnectionAsync(id, ct) is null) return NotFound();
        await _db.DeleteConnectionAsync(id, ct);
        return NoContent();
    }
}
