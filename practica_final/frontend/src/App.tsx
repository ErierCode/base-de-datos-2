import { useCallback, useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import { apiDelete, apiGet, apiPatch, apiPost, login } from "./api";

type Tab =
  | "health"
  | "register"
  | "queries"
  | "concurrency"
  | "backup"
  | "replication"
  | "cache"
  | "alerts";

type Conn = {
  id: number;
  nombre: string;
  motor: string;
  host: string;
  port: number;
  databaseName: string;
  userName: string;
  status: string;
  createdAt: string;
};

type Health = {
  dbId: number;
  nombre: string;
  motor: string;
  healthGrade: string;
  cpuPct: number;
  memoryPct: number;
  connections: number;
  locks: number;
  deadlocks: number;
  diskUsageMb: number;
  captureTime: string;
};

type Metric = {
  captureTime: string;
  cpuPct: number;
  memoryPct: number;
  connections: number;
  healthGrade: string;
};

type QueryRow = {
  id: number;
  dbId: number;
  speedClass: string;
  durationMs: number;
  rowsReturned: number | null;
  indexUsed: string | null;
  isOptimized: boolean;
  queryText: string;
  createdAt: string;
  durationBeforeMs: number | null;
  durationAfterMs: number | null;
  improvementPct: number | null;
  indexApplied: string | null;
};

type TxRow = {
  id: number;
  dbId: number;
  session: string;
  operacion: string;
  inicio: string;
  fin: string;
  waitTime: number;
  lockType: string;
};

type DeadlockRow = {
  id: number;
  sessionId: string | null;
  detectedAt: string;
  resolutionAction: string;
  resolvedAt: string | null;
  detail: string | null;
  waitTimeMs: number | null;
};

type ConcSummary = {
  ops24h: number;
  deadlocks24h: number;
  timeouts24h: number;
  avgWaitMs24h: number;
};

type BackupSla = {
  targetRpoSec: number;
  targetRtoSec: number;
  description: string | null;
  secondsSinceLastFull: number | null;
  lastFullRestorePoint: string | null;
  meetsRpoNow: boolean;
  meetsRtoLastRestore: boolean | null;
  lastRtoObservedSec: number | null;
  cloudReplicationEnabled: boolean;
  cloudProviderHint: string;
};

type ReplSample = {
  id: number;
  lagSeconds: number;
  grade: string;
  scenarioLabel: string | null;
  capturedAt: string;
  standbyState: string | null;
};

type ReplLatest = {
  sample: ReplSample | null;
  thresholds: {
    acceptableMaxSec: number;
    warningReferenceSec: number;
    criticalMinSec: number;
    description: string;
  };
};

type CacheStats = {
  hits24h: number;
  misses24h: number;
  hitRatio24h: number;
  avgLatencyHitMs: number | null;
  avgLatencyMissMs: number | null;
  ttlSeconds: number;
  cacheKey: string;
};

type CacheEvent = {
  id: number;
  cacheKey: string;
  outcome: string;
  latencyMs: number;
  detail: string | null;
  createdAt: string;
};

type CacheDemo = {
  source: string;
  latencyMs: number;
  message: string;
  stats: CacheStats;
};

type AlertRule = {
  id: number;
  code: string;
  name: string;
  enabled: boolean;
  metricSource: string;
  thresholdNum: number;
  windowMinutes: number;
  severity: string;
  action: string;
  cooldownSec: number;
  description: string | null;
};

type AlertLog = {
  id: number;
  ruleId: number | null;
  ruleCode: string | null;
  dbId: number | null;
  severity: string;
  conditionText: string;
  message: string | null;
  status: string;
  actionTaken: string | null;
  engineName: string | null;
  triggeredAt: string;
  resolvedAt: string | null;
};

type BackupRow = {
  id: number;
  kind: string;
  sizeMb: number;
  durationSec: number;
  restorePoint: string;
  remoteUrl: string | null;
  cloudObjectKey: string | null;
  checksumSha256: string;
  dependsOnId: number | null;
  parentFullId: number | null;
  snapshotLabel: string | null;
  slaMet: boolean;
  purged: boolean;
  createdAt: string;
};

const gradeClass: Record<string, string> = {
  HEALTHY: "pill ok",
  WARNING: "pill warn",
  CRITICAL: "pill crit",
  FAST: "pill ok",
  MEDIUM: "pill warn",
  SLOW: "pill warn",
  ACCEPTABLE: "pill ok",
};

function replPill(grade: string) {
  if (grade === "CRITICAL") return "pill crit";
  if (grade === "WARNING") return "pill warn";
  return "pill ok";
}

function speedPill(c: string) {
  if (c === "CRITICAL") return "pill crit";
  if (c === "SLOW" || c === "MEDIUM") return "pill warn";
  return "pill ok";
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("dcc_token"));
  const [user, setUser] = useState("admin");
  const [pass, setPass] = useState("Admin123!");
  const [tab, setTab] = useState<Tab>("health");
  const [connections, setConnections] = useState<Conn[]>([]);
  const [health, setHealth] = useState<Health[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [history, setHistory] = useState<Metric[]>([]);
  const [queries, setQueries] = useState<QueryRow[]>([]);
  const [txLog, setTxLog] = useState<TxRow[]>([]);
  const [deadlocks, setDeadlocks] = useState<DeadlockRow[]>([]);
  const [concSummary, setConcSummary] = useState<ConcSummary | null>(null);
  const [backupSla, setBackupSla] = useState<BackupSla | null>(null);
  const [backups, setBackups] = useState<BackupRow[]>([]);
  const [replLatest, setReplLatest] = useState<ReplLatest | null>(null);
  const [replHistory, setReplHistory] = useState<ReplSample[]>([]);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [cacheEvents, setCacheEvents] = useState<CacheEvent[]>([]);
  const [cacheDemo, setCacheDemo] = useState<CacheDemo | null>(null);
  const [cacheMsg, setCacheMsg] = useState("");
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [alertLogs, setAlertLogs] = useState<AlertLog[]>([]);
  const [optMsg, setOptMsg] = useState("");
  const [err, setErr] = useState("");
  const [form, setForm] = useState({
    nombre: "mi-postgres",
    motor: "POSTGRESQL",
    host: "postgres-control",
    port: 5432,
    databaseName: "dcc_control",
    userName: "dcc_admin",
    password: "dcc_secret_change_me",
  });
  const [testMsg, setTestMsg] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setConnections(await apiGet<Conn[]>("/api/connections"));
      setHealth(await apiGet<Health[]>("/api/health/latest"));
      setErr("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setErr(msg);
      if (msg.includes("Sesión expirada") || msg.includes("token inválido")) {
        localStorage.removeItem("dcc_token");
        setToken(null);
      }
    }
  }, [token]);

  const loadQueries = useCallback(async () => {
    if (!token) return;
    setQueries(await apiGet<QueryRow[]>("/api/queries?limit=50"));
  }, [token]);

  const loadConcurrency = useCallback(async () => {
    if (!token) return;
    const [s, tx, dl] = await Promise.all([
      apiGet<ConcSummary>("/api/concurrency/summary"),
      apiGet<TxRow[]>("/api/concurrency/tx-log?limit=80"),
      apiGet<DeadlockRow[]>("/api/concurrency/deadlocks?limit=30"),
    ]);
    setConcSummary(s);
    setTxLog(tx);
    setDeadlocks(dl);
  }, [token]);

  const loadBackups = useCallback(async () => {
    if (!token) return;
    const [slaRes, histRes] = await Promise.allSettled([
      apiGet<BackupSla>("/api/backups/sla"),
      apiGet<BackupRow[]>("/api/backups?limit=40"),
    ]);
    if (slaRes.status === "fulfilled") setBackupSla(slaRes.value);
    if (histRes.status === "fulfilled") setBackups(histRes.value);
  }, [token]);

  const loadReplication = useCallback(async () => {
    if (!token) return;
    const [latest, history] = await Promise.all([
      apiGet<ReplLatest>("/api/replication/latest"),
      apiGet<ReplSample[]>("/api/replication/history?limit=120"),
    ]);
    setReplLatest(latest);
    setReplHistory(history);
  }, [token]);

  const loadCache = useCallback(async () => {
    if (!token) return;
    const [stats, events] = await Promise.all([
      apiGet<CacheStats>("/api/cache/stats"),
      apiGet<CacheEvent[]>("/api/cache/events?limit=30"),
    ]);
    setCacheStats(stats);
    setCacheEvents(events);
  }, [token]);

  const loadAlerts = useCallback(async () => {
    if (!token) return;
    const [rules, logs] = await Promise.all([
      apiGet<AlertRule[]>("/api/alerts/rules"),
      apiGet<AlertLog[]>("/api/alerts?limit=50&openOnly=false"),
    ]);
    setAlertRules(rules);
    setAlertLogs(logs);
  }, [token]);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (tab === "queries") {
      loadQueries();
      const id = setInterval(loadQueries, 20000);
      return () => clearInterval(id);
    }
    if (tab === "concurrency") {
      loadConcurrency();
      const id = setInterval(loadConcurrency, 10000);
      return () => clearInterval(id);
    }
    if (tab === "backup") {
      loadBackups();
      const id = setInterval(loadBackups, 20000);
      return () => clearInterval(id);
    }
    if (tab === "replication") {
      loadReplication();
      const id = setInterval(loadReplication, 5000);
      return () => clearInterval(id);
    }
    if (tab === "cache") {
      loadCache();
      const id = setInterval(loadCache, 10000);
      return () => clearInterval(id);
    }
    if (tab === "alerts") {
      loadAlerts();
      const id = setInterval(loadAlerts, 15000);
      return () => clearInterval(id);
    }
  }, [tab, loadQueries, loadConcurrency, loadBackups, loadReplication, loadCache, loadAlerts]);

  useEffect(() => {
    if (!selectedId || !token) return;
    apiGet<Metric[]>(`/api/health/${selectedId}/history?limit=40`)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [selectedId, token]);

  const doLogin = async () => {
    try {
      const res = await login(user, pass);
      localStorage.setItem("dcc_token", res.token);
      setToken(res.token);
      setErr("");
    } catch {
      setErr("Credenciales incorrectas (demo: admin / Admin123!)");
    }
  };

  const testConn = async () => {
    try {
      const r = await apiPost<{ ok: boolean; message: string }>("/api/connections/test", form);
      setTestMsg(r.ok ? `OK: ${r.message}` : `Error: ${r.message}`);
    } catch (e) {
      setTestMsg(String(e));
    }
  };

  const register = async () => {
    try {
      const res = await apiPost<{ connection: Conn; connectivity: { ok: boolean; message: string } }>(
        "/api/connections",
        form
      );
      const ok = res.connectivity?.ok;
      setTestMsg(
        ok
          ? `Registrado/actualizado (${res.connection?.status ?? "OK"}).`
          : `Guardado con estado ${res.connection?.status}: ${res.connectivity?.message}`
      );
      await load();
      if (ok) setTab("health");
    } catch (e) {
      setTestMsg(String(e));
    }
  };

  const runLabBaseline = async () => {
    try {
      const dbId = connections[0]?.id ?? 1;
      const row = await apiPost<QueryRow>(`/api/queries/lab/baseline?dbId=${dbId}`, {});
      setOptMsg(`Baseline: ${row.durationMs} ms (${row.speedClass}) — id ${row.id}`);
      await loadQueries();
    } catch (e) {
      setOptMsg(String(e));
    }
  };

  const optimize = async (id: number) => {
    try {
      const res = await apiPost<{
        durationBeforeMs: number;
        durationAfterMs: number;
        improvementPct: number;
        indexApplied: string;
      }>(`/api/queries/${id}/optimize`, {});
      setOptMsg(
        `Antes ${res.durationBeforeMs.toFixed(1)} ms → Después ${res.durationAfterMs.toFixed(1)} ms (${res.improvementPct}% mejora). Índice: ${res.indexApplied}`
      );
      await loadQueries();
    } catch (e) {
      setOptMsg(String(e));
    }
  };

  const runCacheDemo = async (forceRefresh: boolean) => {
    try {
      const d = await apiGet<CacheDemo>(`/api/cache/demo?forceRefresh=${forceRefresh}`);
      setCacheDemo(d);
      setCacheMsg(d.message);
      await loadCache();
    } catch (e) {
      setCacheMsg(String(e));
    }
  };

  const invalidateCache = async () => {
    try {
      await apiPost<{ ok: boolean }>("/api/cache/invalidate", {});
      setCacheMsg("Cache invalidada manualmente.");
      setCacheDemo(null);
      await loadCache();
    } catch (e) {
      setCacheMsg(String(e));
    }
  };

  const replChart = replHistory.map((s) => ({
    t: new Date(s.capturedAt).toLocaleTimeString(),
    lag: Number(s.lagSeconds.toFixed(2)),
    grade: s.grade,
  }));

  const cacheLatencyChart =
    cacheStats?.avgLatencyHitMs != null || cacheStats?.avgLatencyMissMs != null
      ? [
          { name: "HIT", ms: cacheStats?.avgLatencyHitMs ?? 0 },
          { name: "MISS", ms: cacheStats?.avgLatencyMissMs ?? 0 },
        ]
      : [];

  const compareChart = queries
    .filter((q) => q.durationBeforeMs != null && q.durationAfterMs != null)
    .slice(0, 8)
    .map((q) => ({
      name: `#${q.id}`,
      antes: Number(q.durationBeforeMs),
      despues: Number(q.durationAfterMs),
    }));

  if (!token) {
    return (
      <div className="layout center">
        <div className="card login">
          <h1>DataOps Control Center</h1>
          <p className="muted">JWT — usuario demo: admin / Admin123!</p>
          <label>Usuario</label>
          <input value={user} onChange={(e) => setUser(e.target.value)} />
          <label>Contraseña</label>
          <input type="password" value={pass} onChange={(e) => setPass(e.target.value)} />
          {err && <p className="error">{err}</p>}
          <button onClick={doLogin}>Entrar</button>
        </div>
      </div>
    );
  }

  return (
    <div className="layout">
      <header>
        <h1>DataOps Control Center</h1>
        <nav>
          <button className={tab === "health" ? "active" : ""} onClick={() => setTab("health")}>
            Salud (2)
          </button>
          <button className={tab === "register" ? "active" : ""} onClick={() => setTab("register")}>
            Motores (1)
          </button>
          <button className={tab === "queries" ? "active" : ""} onClick={() => setTab("queries")}>
            Queries (3)
          </button>
          <button className={tab === "concurrency" ? "active" : ""} onClick={() => setTab("concurrency")}>
            Concurrencia (4)
          </button>
          <button className={tab === "backup" ? "active" : ""} onClick={() => setTab("backup")}>
            Backup (5)
          </button>
          <button className={tab === "replication" ? "active" : ""} onClick={() => setTab("replication")}>
            Replicacion (6)
          </button>
          <button className={tab === "cache" ? "active" : ""} onClick={() => setTab("cache")}>
            Cache (7)
          </button>
          <button className={tab === "alerts" ? "active" : ""} onClick={() => setTab("alerts")}>
            Alertas (9)
          </button>
          <a href="/swagger" target="_blank" rel="noreferrer">
            Swagger
          </a>
          <button
            className="ghost"
            onClick={() => {
              localStorage.removeItem("dcc_token");
              setToken(null);
            }}
          >
            Salir
          </button>
        </nav>
      </header>

      {err && <p className="error banner">{err}</p>}

      {tab === "register" && (
        <section className="card grid-form">
          <h2>Registro de conexión</h2>
          <input placeholder="Nombre" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          <select value={form.motor} onChange={(e) => setForm({ ...form, motor: e.target.value })}>
            <option>POSTGRESQL</option>
            <option>SQL_SERVER</option>
            <option>ORACLE</option>
          </select>
          <input placeholder="Host" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
          <input type="number" value={form.port} onChange={(e) => setForm({ ...form, port: +e.target.value })} />
          <input placeholder="Base" value={form.databaseName} onChange={(e) => setForm({ ...form, databaseName: e.target.value })} />
          <input placeholder="Usuario" value={form.userName} onChange={(e) => setForm({ ...form, userName: e.target.value })} />
          <input type="password" placeholder="Contraseña" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <div className="row">
            <button type="button" onClick={testConn}>
              Probar conexión
            </button>
            <button type="button" onClick={register}>
              Guardar (AES-GCM)
            </button>
          </div>
          {testMsg && <p className="muted">{testMsg}</p>}
        </section>
      )}

      {tab === "health" && (
        <>
          <section className="cards">
            {health.map((h) => (
              <article
                key={h.dbId}
                className={`card stat ${selectedId === h.dbId ? "selected" : ""}`}
                onClick={() => setSelectedId(h.dbId)}
              >
                <h3>{h.nombre}</h3>
                <span className={gradeClass[h.healthGrade] ?? "pill"}>{h.healthGrade}</span>
                <ul>
                  <li>CPU: {h.cpuPct}%</li>
                  <li>Mem: {h.memoryPct}%</li>
                  <li>Conexiones: {h.connections}</li>
                </ul>
                <small>{new Date(h.captureTime).toLocaleString()}</small>
              </article>
            ))}
          </section>
          {selectedId && history.length > 0 && (
            <section className="card chart">
              <h2>Histórico — {connections.find((c) => c.id === selectedId)?.nombre}</h2>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={history.map((m) => ({ ...m, t: new Date(m.captureTime).toLocaleTimeString() }))}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="t" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="cpuPct" stroke="#38bdf8" name="CPU %" />
                  <Line type="monotone" dataKey="connections" stroke="#a78bfa" name="Conexiones" />
                </LineChart>
              </ResponsiveContainer>
            </section>
          )}
        </>
      )}

      {tab === "queries" && (
        <>
          <section className="card">
            <h2>Módulo 3 — Slow Query Analyzer</h2>
            <p className="muted">
              1) Genera baseline lento (sin índice). 2) Optimiza con índice y compara tiempos antes/después.
            </p>
            <div className="row">
              <button onClick={runLabBaseline}>1. Ejecutar baseline (lab)</button>
            </div>
            {optMsg && <p className="muted">{optMsg}</p>}
          </section>

          {compareChart.length > 0 && (
            <section className="card chart">
              <h3>Comparativa antes / después (ms)</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={compareChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="antes" fill="#f87171" name="Antes" />
                  <Bar dataKey="despues" fill="#4ade80" name="Después" />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          <section className="card">
            <h3>QUERY_LOG</h3>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Clase</th>
                  <th>ms</th>
                  <th>Antes→Después</th>
                  <th>Índice</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {queries.map((q) => (
                  <tr key={q.id}>
                    <td>{q.id}</td>
                    <td>
                      <span className={speedPill(q.speedClass)}>{q.speedClass}</span>
                    </td>
                    <td>{Number(q.durationMs).toFixed(1)}</td>
                    <td>
                      {q.durationBeforeMs != null && q.durationAfterMs != null
                        ? `${Number(q.durationBeforeMs).toFixed(0)} → ${Number(q.durationAfterMs).toFixed(0)} (${q.improvementPct}%)`
                        : "—"}
                    </td>
                    <td>{q.indexUsed ?? q.indexApplied ?? "—"}</td>
                    <td>
                      {!q.isOptimized && (
                        <button className="ghost" onClick={() => optimize(q.id)}>
                          Optimizar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <details className="muted" style={{ marginTop: "1rem" }}>
              <summary>Vista previa SQL</summary>
              {queries.slice(0, 5).map((q) => (
                <pre key={q.id} className="sql-preview">
                  {q.queryText}
                </pre>
              ))}
            </details>
          </section>
        </>
      )}

      {tab === "backup" && (
        <>
          <section className="cards">
            <article className="card stat">
              <h3>SLA RPO (objetivo)</h3>
              <p className="big">{backupSla ? Math.round(backupSla.targetRpoSec / 60) : "—"} min</p>
              <span className={backupSla?.meetsRpoNow ? "pill ok" : "pill crit"}>
                {backupSla?.meetsRpoNow ? "Cumple" : "No cumple"}
              </span>
            </article>
            <article className="card stat">
              <h3>SLA RTO (objetivo)</h3>
              <p className="big">{backupSla ? Math.round(backupSla.targetRtoSec / 60) : "—"} min</p>
              <span
                className={
                  backupSla?.meetsRtoLastRestore === true
                    ? "pill ok"
                    : backupSla?.meetsRtoLastRestore === false
                      ? "pill crit"
                      : "pill warn"
                }
              >
                {backupSla?.meetsRtoLastRestore === true
                  ? "Cumple"
                  : backupSla?.meetsRtoLastRestore === false
                    ? "No cumple"
                    : "Sin medición"}
              </span>
              {backupSla?.lastRtoObservedSec != null && (
                <small>Último restore: {backupSla.lastRtoObservedSec.toFixed(1)} s</small>
              )}
            </article>
            <article className="card stat">
              <h3>Replicación nube</h3>
              <p className="big">{backupSla?.cloudReplicationEnabled ? "AWS/S3" : "Local"}</p>
              <small className="muted">{backupSla?.cloudProviderHint}</small>
            </article>
          </section>
          <p className="muted">
            Worker: FULL nocturno, DIFF cada 6 h, INC cada 2 h. SHA-256 + subida automática a S3 cuando{" "}
            <code>S3_BUCKET</code> está configurado. Demostración:{" "}
            <code>docker compose run --rm backup-worker python disaster_demo.py</code> y luego{" "}
            <code>restore_demo.py --measure-rto</code>.
          </p>
          <section className="card">
            <h3>BACKUP_HISTORY</h3>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Tipo</th>
                  <th>MB</th>
                  <th>Restore point</th>
                  <th>SLA</th>
                  <th>Nube</th>
                  <th>SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((b) => (
                  <tr key={b.id}>
                    <td>{b.id}</td>
                    <td>
                      <span className="pill">{b.kind}</span>
                      {b.snapshotLabel && <small> ({b.snapshotLabel})</small>}
                    </td>
                    <td>{Number(b.sizeMb).toFixed(2)}</td>
                    <td>{new Date(b.restorePoint).toLocaleString()}</td>
                    <td>
                      <span className={b.slaMet ? "pill ok" : "pill warn"}>{b.slaMet ? "Sí" : "No"}</span>
                    </td>
                    <td>{b.remoteUrl || b.cloudObjectKey ? "✓ S3" : "—"}</td>
                    <td title={b.checksumSha256}>{b.checksumSha256.slice(0, 12)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === "replication" && (
        <>
          <section className="cards">
            <article className="card stat">
              <h3>Lag actual</h3>
              <p className="big">
                {replLatest?.sample ? `${Number(replLatest.sample.lagSeconds).toFixed(2)} s` : "—"}
              </p>
              {replLatest?.sample && (
                <span className={replPill(replLatest.sample.grade)}>{replLatest.sample.grade}</span>
              )}
            </article>
            <article className="card stat">
              <h3>Escenario</h3>
              <p className="big">{replLatest?.sample?.scenarioLabel ?? "—"}</p>
              <small className="muted">NORMAL ~2s | MEDIUM ~5s | HIGH ~20s</small>
            </article>
            <article className="card stat">
              <h3>Umbrales PDF</h3>
              <ul className="muted" style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.85rem" }}>
                <li>&lt;= {replLatest?.thresholds.acceptableMaxSec ?? 2}s Aceptable</li>
                <li>~ {replLatest?.thresholds.warningReferenceSec ?? 5}s Advertencia</li>
                <li>&gt;= {replLatest?.thresholds.criticalMinSec ?? 20}s Critico</li>
              </ul>
            </article>
          </section>
          <p className="muted">
            Primario-réplica Bitnami (escrituras en primario, lectura en réplica). Workers{" "}
            <code>replication-monitor</code> + <code>replication-load</code>. Actualización cada 5 s.
          </p>
          {replChart.length > 0 && (
            <section className="card chart">
              <h3>Lag de replicación en tiempo real (s)</h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={replChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="t" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="lag" stroke="#fbbf24" name="Lag (s)" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </section>
          )}
          <section className="card">
            <h3>Muestras recientes</h3>
            <table>
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Lag (s)</th>
                  <th>Estado</th>
                  <th>Escenario</th>
                  <th>Standby</th>
                </tr>
              </thead>
              <tbody>
                {[...replHistory].reverse().slice(0, 15).map((s) => (
                  <tr key={s.id}>
                    <td>{new Date(s.capturedAt).toLocaleTimeString()}</td>
                    <td>{Number(s.lagSeconds).toFixed(2)}</td>
                    <td>
                      <span className={replPill(s.grade)}>{s.grade}</span>
                    </td>
                    <td>{s.scenarioLabel ?? "—"}</td>
                    <td>{s.standbyState ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section className="card muted">
            <h3>Teorema CAP (informe)</h3>
            <p>
              Arquitectura primario-réplica: prioriza <strong>disponibilidad</strong> y partición tolerante
              (réplica puede quedar atrasada). La <strong>consistencia</strong> es eventual: el lag medido
              cuantifica el retardo entre escritura en primario y replay en réplica.
            </p>
          </section>
        </>
      )}

      {tab === "cache" && (
        <>
          <section className="cards">
            <article className="card stat">
              <h3>Hit ratio 24h</h3>
              <p className="big">
                {cacheStats ? `${(cacheStats.hitRatio24h * 100).toFixed(1)}%` : "—"}
              </p>
              <small className="muted">
                {cacheStats?.hits24h ?? 0} hits / {cacheStats?.misses24h ?? 0} misses
              </small>
            </article>
            <article className="card stat">
              <h3>TTL Redis</h3>
              <p className="big">{cacheStats?.ttlSeconds ?? 45}s</p>
              <small className="muted">Clave: {cacheStats?.cacheKey ?? "—"}</small>
            </article>
            <article className="card stat">
              <h3>Ultima demo</h3>
              <p className="big">{cacheDemo ? `${cacheDemo.latencyMs} ms` : "—"}</p>
              <small className="muted">{cacheDemo?.source ?? "pulse Probar miss/hit"}</small>
            </article>
          </section>
          <section className="card">
            <h2>Módulo 7 — Redis</h2>
            <p className="muted">
              Sin caché ~400 ms (miss). Con caché ~40 ms (hit). Invalidación: TTL + botón manual.
            </p>
            <div className="row">
              <button onClick={() => runCacheDemo(true)}>Probar MISS (sin caché)</button>
              <button onClick={() => runCacheDemo(false)}>Probar HIT (con caché)</button>
              <button className="ghost" onClick={invalidateCache}>
                Invalidar caché
              </button>
            </div>
            {cacheMsg && <p className="muted">{cacheMsg}</p>}
          </section>
          {cacheLatencyChart.length > 0 && (
            <section className="card chart">
              <h3>Latencia media HIT vs MISS (ms, 24h)</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={cacheLatencyChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="ms" fill="#38bdf8" name="ms" />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}
          <section className="card">
            <h3>cache_event_log</h3>
            <table>
              <thead>
                <tr>
                  <th>Resultado</th>
                  <th>ms</th>
                  <th>Detalle</th>
                  <th>Hora</th>
                </tr>
              </thead>
              <tbody>
                {cacheEvents.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <span className={e.outcome === "HIT" ? "pill ok" : "pill warn"}>{e.outcome}</span>
                    </td>
                    <td>{Number(e.latencyMs).toFixed(1)}</td>
                    <td>{e.detail ?? "—"}</td>
                    <td>{new Date(e.createdAt).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === "alerts" && (
        <>
          <section className="card">
            <h2>Módulo 9 — Motor de alertas</h2>
            <p className="muted">
              Reglas editables sin redeploy. Correo opcional vía SMTP en appsettings / variables Alerts:*.
            </p>
          </section>
          <section className="card">
            <h3>Reglas (alert_rules)</h3>
            <table>
              <thead>
                <tr>
                  <th>Activa</th>
                  <th>Código</th>
                  <th>Umbral</th>
                  <th>Severidad</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {alertRules.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={r.enabled}
                        onChange={async (e) => {
                          await apiPatch(`/api/alerts/rules/${r.id}`, { enabled: e.target.checked });
                          await loadAlerts();
                        }}
                      />
                    </td>
                    <td title={r.description ?? ""}>{r.code}</td>
                    <td>
                      <input
                        type="number"
                        style={{ width: "4.5rem" }}
                        value={r.thresholdNum}
                        onChange={async (e) => {
                          const v = +e.target.value;
                          if (Number.isNaN(v)) return;
                          await apiPatch(`/api/alerts/rules/${r.id}`, { thresholdNum: v });
                          await loadAlerts();
                        }}
                      />
                    </td>
                    <td>
                      <span className={r.severity === "CRITICAL" ? "pill crit" : "pill warn"}>
                        {r.severity}
                      </span>
                    </td>
                    <td>{r.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section className="card">
            <h3>ALERT_LOG</h3>
            <table>
              <thead>
                <tr>
                  <th>Severidad</th>
                  <th>Condición</th>
                  <th>Motor</th>
                  <th>Estado</th>
                  <th>Hora</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {alertLogs.map((a) => (
                  <tr key={a.id} className={a.severity === "CRITICAL" ? "row-crit" : ""}>
                    <td>
                      <span className={a.severity === "CRITICAL" ? "pill crit" : "pill warn"}>
                        {a.severity}
                      </span>
                    </td>
                    <td>{a.conditionText}</td>
                    <td>{a.engineName ?? "—"}</td>
                    <td>{a.status}</td>
                    <td>{new Date(a.triggeredAt).toLocaleString()}</td>
                    <td>
                      {a.status === "OPEN" && (
                        <button
                          className="ghost"
                          onClick={async () => {
                            await apiPost(`/api/alerts/${a.id}/resolve`, {});
                            await loadAlerts();
                          }}
                        >
                          Resolver
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      {tab === "concurrency" && (
        <>
          <section className="cards">
            <article className="card stat">
              <h3>Ops 24h</h3>
              <p className="big">{concSummary?.ops24h ?? 0}</p>
            </article>
            <article className="card stat">
              <h3>Deadlocks 24h</h3>
              <p className="big crit-text">{concSummary?.deadlocks24h ?? 0}</p>
            </article>
            <article className="card stat">
              <h3>Timeouts 24h</h3>
              <p className="big">{concSummary?.timeouts24h ?? 0}</p>
            </article>
            <article className="card stat">
              <h3>Wait medio (ms)</h3>
              <p className="big">{concSummary?.avgWaitMs24h ?? 0}</p>
            </article>
          </section>
          <p className="muted">
            Simulador activo: ≥120 hilos, operaciones mixtas. Deadlocks detectados en tx_log y resueltos por PostgreSQL
            (rollback víctima).
          </p>

          <section className="card">
            <h3>Deadlocks detectados (plataforma)</h3>
            <table>
              <thead>
                <tr>
                  <th>Sesión</th>
                  <th>Detectado</th>
                  <th>Resolución</th>
                  <th>Resuelto</th>
                </tr>
              </thead>
              <tbody>
                {deadlocks.map((d) => (
                  <tr key={d.id}>
                    <td>{d.sessionId}</td>
                    <td>{new Date(d.detectedAt).toLocaleString()}</td>
                    <td>{d.resolutionAction}</td>
                    <td>{d.resolvedAt ? new Date(d.resolvedAt).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <h3>TX_LOG (reciente)</h3>
            <table>
              <thead>
                <tr>
                  <th>Sesión</th>
                  <th>Op</th>
                  <th>Wait ms</th>
                  <th>Lock</th>
                  <th>Fin</th>
                </tr>
              </thead>
              <tbody>
                {txLog.map((t) => (
                  <tr key={t.id}>
                    <td>{t.session}</td>
                    <td>{t.operacion}</td>
                    <td>{t.waitTime}</td>
                    <td>
                      <span className={t.lockType === "DEADLOCK" ? "pill crit" : "pill"}>{t.lockType}</span>
                    </td>
                    <td>{new Date(t.fin).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
