using System.Text.Json;
using DataOps.Api.Models;
using DataOps.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DataOps.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AlertsController : ControllerBase
{
    private readonly AlertService _alerts;
    private readonly ILogger<AlertsController> _log;

    public AlertsController(AlertService alerts, ILogger<AlertsController> log)
    {
        _alerts = alerts;
        _log = log;
    }

    [Authorize]
    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<AlertLogDto>>> List(
        [FromQuery] int limit = 50, [FromQuery] bool openOnly = true, CancellationToken ct = default)
        => Ok(await _alerts.ListAlertsAsync(limit, openOnly, ct));

    [Authorize]
    [HttpGet("rules")]
    public async Task<ActionResult<IReadOnlyList<AlertRuleDto>>> Rules(CancellationToken ct)
        => Ok(await _alerts.ListRulesAsync(ct));

    [Authorize]
    [HttpPatch("rules/{id:int}")]
    public async Task<ActionResult<AlertRuleDto>> UpdateRule(
        int id, [FromBody] AlertRuleUpdateDto patch, CancellationToken ct)
    {
        var updated = await _alerts.UpdateRuleAsync(id, patch, ct);
        return updated is null ? NotFound() : Ok(updated);
    }

    [Authorize]
    [HttpPost("{id:long}/resolve")]
    public async Task<IActionResult> Resolve(long id, CancellationToken ct)
    {
        if (!await _alerts.ResolveAlertAsync(id, ct))
            return NotFound();
        return Ok(new { ok = true });
    }

    /// <summary>Webhook Alertmanager → alert_log (sin JWT).</summary>
    [AllowAnonymous]
    [HttpPost("webhook")]
    public async Task<IActionResult> Webhook([FromBody] JsonElement payload, CancellationToken ct)
    {
        try
        {
            if (payload.TryGetProperty("alerts", out var alerts) && alerts.ValueKind == JsonValueKind.Array)
            {
                foreach (var a in alerts.EnumerateArray())
                {
                    var status = a.TryGetProperty("status", out var st) ? st.GetString() : "firing";
                    if (status == "resolved") continue;
                    var summary = a.TryGetProperty("annotations", out var ann) && ann.TryGetProperty("summary", out var s)
                        ? s.GetString() ?? "Alertmanager"
                        : "Alertmanager";
                    var severity = a.TryGetProperty("labels", out var lab) && lab.TryGetProperty("severity", out var sev)
                        ? sev.GetString() ?? "warning"
                        : "warning";
                    await _alerts.InsertWebhookAlertAsync(summary!, severity!, ct);
                }
            }
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex, "Webhook Alertmanager parse error");
        }
        return Ok(new { received = true });
    }
}
