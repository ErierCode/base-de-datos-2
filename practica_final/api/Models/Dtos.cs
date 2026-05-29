namespace DataOps.Api.Models;

public record LoginRequest(string Username, string Password);
public record LoginResponse(string Token, DateTime ExpiresAt);

public record ConnectionCreateRequest(
    string Nombre,
    string Motor,
    string Host,
    int Port,
    string DatabaseName,
    string UserName,
    string Password
);

public record ConnectionResponse(
    int Id,
    string Nombre,
    string Motor,
    string Host,
    int Port,
    string DatabaseName,
    string UserName,
    string Status,
    DateTime CreatedAt
);

public record ConnectionTestResult(bool Ok, string Message);

public record HealthSnapshotResponse(
    int DbId,
    string Nombre,
    string Motor,
    string HealthGrade,
    decimal CpuPct,
    decimal MemoryPct,
    int Connections,
    int Locks,
    int Deadlocks,
    decimal DiskUsageMb,
    DateTime CaptureTime,
    string? CollectError
);

public record MetricPointDto(DateTime CaptureTime, decimal CpuPct, decimal MemoryPct, int Connections, string HealthGrade);

public record ThresholdsDto(
    decimal CpuWarningPct,
    decimal CpuCriticalPct,
    decimal MemoryWarningPct,
    decimal MemoryCriticalPct,
    decimal ConnWarningPct,
    decimal ConnCriticalPct,
    int LocksWarning,
    int LocksCritical,
    int DeadlocksWarning,
    int DeadlocksCritical
);

public record DashboardSummaryDto(
    string Source,
    int RecentReplicationSamples6h,
    double AvgLagRecentSeconds,
    DateTime? LatestSampleAt,
    CacheRatioDto? CacheHitRatio24h
);

public record CacheRatioDto(long Hits, long Misses, double HitRatio);

public record QueryLogDto(
    long Id,
    int DbId,
    string SpeedClass,
    decimal DurationMs,
    long? RowsReturned,
    string? IndexUsed,
    bool IsOptimized,
    string QueryText,
    DateTime CreatedAt,
    string? OptimizedQueryText,
    decimal? DurationBeforeMs,
    decimal? DurationAfterMs,
    decimal? ImprovementPct,
    string? IndexApplied
);

public record OptimizationResultDto(
    long OptimizationId,
    double DurationBeforeMs,
    double DurationAfterMs,
    double ImprovementPct,
    string IndexApplied,
    string DdlApplied,
    long RowsBefore,
    long RowsAfter,
    QueryLogDto UpdatedQuery
);

public record TxLogDto(
    long Id,
    int DbId,
    string Session,
    string Operacion,
    DateTime Inicio,
    DateTime Fin,
    int WaitTime,
    string LockType
);

public record DeadlockEventDto(
    long Id,
    int? DbId,
    string? SessionId,
    DateTime DetectedAt,
    string ResolutionAction,
    DateTime? ResolvedAt,
    string? Detail,
    int? WaitTimeMs
);

public record ConcurrencySummaryDto(long Ops24h, long Deadlocks24h, long Timeouts24h, int AvgWaitMs24h);

public record BackupHistoryDto(
    long Id,
    string Kind,
    decimal SizeMb,
    decimal DurationSec,
    DateTime RestorePoint,
    string? LocalPath,
    string? RemoteUrl,
    string? CloudObjectKey,
    string ChecksumSha256,
    long? DependsOnId,
    long? ParentFullId,
    string? SnapshotLabel,
    string? Notes,
    string? IncludedTables,
    double? RpoEstimateSec,
    double? RtoObservedSec,
    bool SlaMet,
    bool Purged,
    DateTime CreatedAt
);

public record ReplicationSampleDto(
    long Id,
    double LagSeconds,
    string Grade,
    string? ScenarioLabel,
    DateTime CapturedAt,
    string? StandbyState
);

public record ReplicationThresholdsDto(
    double AcceptableMaxSec,
    double WarningReferenceSec,
    double CriticalMinSec,
    string Description
);

public record ReplicationLatestDto(
    ReplicationSampleDto? Sample,
    ReplicationThresholdsDto Thresholds
);

public record CacheStatsDto(
    long Hits24h,
    long Misses24h,
    double HitRatio24h,
    double? AvgLatencyHitMs,
    double? AvgLatencyMissMs,
    int TtlSeconds,
    string CacheKey
);

public record CacheEventDto(
    long Id,
    string CacheKey,
    string Outcome,
    decimal LatencyMs,
    string? Detail,
    DateTime CreatedAt
);

public record CacheDemoDto(
    string Source,
    double LatencyMs,
    string Message,
    CacheStatsDto Stats
);

public record AlertRuleDto(
    int Id,
    string Code,
    string Name,
    bool Enabled,
    string MetricSource,
    double ThresholdNum,
    int WindowMinutes,
    string Severity,
    string Action,
    int CooldownSec,
    string? Description
);

public record AlertRuleUpdateDto(
    bool? Enabled,
    double? ThresholdNum,
    int? WindowMinutes,
    string? Severity,
    string? Action,
    int? CooldownSec
);

public record AlertLogDto(
    long Id,
    int? RuleId,
    string? RuleCode,
    int? DbId,
    string Severity,
    string ConditionText,
    string? Message,
    string Status,
    string? ActionTaken,
    string? EngineName,
    DateTime TriggeredAt,
    DateTime? ResolvedAt
);

public record BackupSlaDashboardDto(
    int TargetRpoSec,
    int TargetRtoSec,
    string? Description,
    double? SecondsSinceLastFull,
    DateTime? LastFullRestorePoint,
    bool MeetsRpoNow,
    bool? MeetsRtoLastRestore,
    double? LastRtoObservedSec,
    bool CloudReplicationEnabled,
    string CloudProviderHint
);
