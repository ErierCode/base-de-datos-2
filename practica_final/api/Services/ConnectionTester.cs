using Npgsql;

namespace DataOps.Api.Services;

public static class ConnectionTester
{
    public static async Task<(bool Ok, string Message)> TestAsync(
        string motor,
        string host,
        int port,
        string database,
        string user,
        string password,
        CancellationToken ct = default)
    {
        var m = motor.Trim().ToUpperInvariant();
        if (m is not ("POSTGRESQL" or "ORACLE" or "SQL_SERVER"))
            return (false, $"Motor no soportado: {motor}");

        if (m != "POSTGRESQL")
            return (false, $"Validación de conectividad para {motor} pendiente; registro permitido en INACTIVE.");

        try
        {
            var cs = new NpgsqlConnectionStringBuilder
            {
                Host = host,
                Port = port,
                Database = database,
                Username = user,
                Password = password,
                Timeout = 8,
                CommandTimeout = 8
            };
            await using var conn = new NpgsqlConnection(cs.ConnectionString);
            await conn.OpenAsync(ct);
            await using var cmd = new NpgsqlCommand("SELECT 1", conn);
            await cmd.ExecuteScalarAsync(ct);
            return (true, "Conexión PostgreSQL exitosa.");
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }
}
