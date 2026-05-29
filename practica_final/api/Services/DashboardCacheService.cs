using System.Text.Json;
using DataOps.Api.Models;
using Npgsql;
using StackExchange.Redis;

namespace DataOps.Api.Services;

/// <summary>Módulo 7 — Redis con hit/miss registrado en cache_event_log.</summary>
public sealed class DashboardCacheService
{
    private readonly ControlDb _db;
    private readonly IConnectionMultiplexer _redis;
    private readonly string _key;
    private readonly int _ttlSec;

    public DashboardCacheService(ControlDb db, IConfiguration config)
    {
        _db = db;
        var redisCs = config["Redis:Connection"] ?? "localhost:6379";
        _redis = ConnectionMultiplexer.Connect(redisCs);
        _key = config["Redis:DashboardKey"] ?? "dcc:dashboard:summary:v1";
        _ttlSec = int.Parse(config["Redis:TtlSeconds"] ?? "45");
    }

    public async Task<DashboardSummaryDto> GetSummaryAsync(bool forceRefresh, CancellationToken ct)
    {
        var db = _redis.GetDatabase();
        var sw = System.Diagnostics.Stopwatch.StartNew();

        if (!forceRefresh)
        {
            var cached = await db.StringGetAsync(_key);
            if (cached.HasValue)
            {
                await Task.Delay(40, ct);
                sw.Stop();
                await LogCacheEventAsync("HIT", sw.Elapsed.TotalMilliseconds, "redis", ct);
                var dto = JsonSerializer.Deserialize<DashboardSummaryDto>(cached!)!;
                return dto with { Source = "redis" };
            }
        }

        var summary = await BuildFromDatabaseAsync(ct);
        await Task.Delay(400, ct);
        sw.Stop();
        var json = JsonSerializer.Serialize(summary);
        await db.StringSetAsync(_key, json, TimeSpan.FromSeconds(_ttlSec));
        await LogCacheEventAsync("MISS", sw.Elapsed.TotalMilliseconds, $"TTL={_ttlSec}s", ct);
        return summary with { Source = "database" };
    }

    public async Task InvalidateAsync(CancellationToken ct)
    {
        await _redis.GetDatabase().KeyDeleteAsync(_key);
        await LogCacheEventAsync("MISS", 0, "manual_invalidate", ct);
    }

    public int TtlSeconds => _ttlSec;

    public async Task<CacheStatsDto> GetStatsAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT hits, misses, hit_ratio,
                   avg_latency_ms_hit, avg_latency_ms_miss
            FROM v_cache_hit_ratio_24h
            LIMIT 1
            """, conn);
        await using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct))
            return new CacheStatsDto(0, 0, 0, null, null, _ttlSec, _key);

        return new CacheStatsDto(
            r.GetInt64(0),
            r.GetInt64(1),
            r.IsDBNull(2) ? 0.0 : (double)r.GetDecimal(2),
            r.IsDBNull(3) ? null : (double)r.GetDecimal(3),
            r.IsDBNull(4) ? null : (double)r.GetDecimal(4),
            _ttlSec,
            _key);
    }

    public async Task<IReadOnlyList<CacheEventDto>> ListEventsAsync(int limit, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            SELECT id, cache_key, outcome::text, latency_ms, detail, created_at
            FROM cache_event_log
            ORDER BY created_at DESC, id DESC
            LIMIT @lim
            """, conn);
        cmd.Parameters.AddWithValue("lim", Math.Clamp(limit, 5, 200));
        var list = new List<CacheEventDto>();
        await using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new CacheEventDto(
                r.GetInt64(0),
                r.GetString(1),
                r.GetString(2),
                r.GetDecimal(3),
                r.IsDBNull(4) ? null : r.GetString(4),
                r.GetDateTime(5)));
        }
        return list;
    }

    public async Task<CacheDemoDto> RunDemoAsync(bool forceRefresh, CancellationToken ct)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        var summary = await GetSummaryAsync(forceRefresh, ct);
        sw.Stop();
        var stats = await GetStatsAsync(ct);
        var msg = summary.Source == "redis"
            ? "Cache HIT (~40 ms simulados + Redis)."
            : "Cache MISS (~400 ms simulados + consulta BD + guardado Redis).";
        return new CacheDemoDto(summary.Source, Math.Round(sw.Elapsed.TotalMilliseconds, 2), msg, stats);
    }

    private async Task<DashboardSummaryDto> BuildFromDatabaseAsync(CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        double avgLag = 0;
        int samples = 0;
        DateTime? latest = null;
        await using (var cmd = new NpgsqlCommand(
            """
            SELECT COUNT(*)::int, COALESCE(AVG(lag_seconds),0)::float8, MAX(captured_at)
            FROM replication_lag_samples
            WHERE captured_at > NOW() - INTERVAL '6 hours'
            """, conn))
        {
            await using var r = await cmd.ExecuteReaderAsync(ct);
            if (await r.ReadAsync(ct))
            {
                samples = r.GetInt32(0);
                avgLag = r.GetDouble(1);
                latest = r.IsDBNull(2) ? null : r.GetDateTime(2);
            }
        }

        CacheRatioDto? ratio = null;
        await using (var cmd = new NpgsqlCommand(
            "SELECT hits, misses, hit_ratio FROM v_cache_hit_ratio_24h LIMIT 1", conn))
        {
            await using var r = await cmd.ExecuteReaderAsync(ct);
            if (await r.ReadAsync(ct))
            {
                var hitRatio = r.IsDBNull(2) ? 0.0 : (double)r.GetDecimal(2);
                ratio = new CacheRatioDto(r.GetInt64(0), r.GetInt64(1), hitRatio);
            }
        }

        return new DashboardSummaryDto(
            "database",
            samples,
            avgLag,
            latest,
            ratio);
    }

    private async Task LogCacheEventAsync(string outcome, double latencyMs, string detail, CancellationToken ct)
    {
        await using var conn = await _db.OpenAsync(ct);
        await using var cmd = new NpgsqlCommand(
            """
            INSERT INTO cache_event_log (cache_key, outcome, latency_ms, detail)
            VALUES (@k, @o::cache_event_outcome_t, @ms, @d)
            """, conn);
        cmd.Parameters.AddWithValue("k", _key);
        cmd.Parameters.AddWithValue("o", outcome);
        cmd.Parameters.AddWithValue("ms", Math.Round(latencyMs, 3));
        cmd.Parameters.AddWithValue("d", detail);
        await cmd.ExecuteNonQueryAsync(ct);
    }
}
