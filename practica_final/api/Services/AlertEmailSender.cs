namespace DataOps.Api.Services;

/// <summary>Envío opcional SMTP (si no hay configuración, solo registra en log).</summary>
public sealed class AlertEmailSender
{
    private readonly IConfiguration _config;
    private readonly ILogger<AlertEmailSender> _log;

    public AlertEmailSender(IConfiguration config, ILogger<AlertEmailSender> log)
    {
        _config = config;
        _log = log;
    }

    public async Task SendAsync(string subject, string body, CancellationToken ct)
    {
        var host = _config["Alerts:SmtpHost"]?.Trim();
        var to = _config["Alerts:EmailTo"]?.Trim();
        if (string.IsNullOrEmpty(host) || string.IsNullOrEmpty(to))
        {
            _log.LogInformation("[ALERT EMAIL omitido] {Subject}", subject);
            return;
        }

        try
        {
            using var client = new System.Net.Mail.SmtpClient(host)
            {
                Port = int.Parse(_config["Alerts:SmtpPort"] ?? "587"),
                EnableSsl = bool.Parse(_config["Alerts:SmtpSsl"] ?? "true"),
                Credentials = new System.Net.NetworkCredential(
                    _config["Alerts:SmtpUser"],
                    _config["Alerts:SmtpPassword"])
            };
            var from = _config["Alerts:EmailFrom"] ?? "dcc-alerts@localhost";
            using var msg = new System.Net.Mail.MailMessage(from, to, subject, body);
            await client.SendMailAsync(msg, ct);
            _log.LogInformation("Alerta enviada por correo: {Subject}", subject);
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex, "No se pudo enviar correo de alerta");
        }
    }
}
