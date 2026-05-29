"""
Módulo 5 — respaldos pg_dump FULL/DIFF/INC (parcialidades lógicas + marcas backup_touch),
hash SHA-256, subida S3-compatible opcional y retención con purga coordinada.

Cadena DIFF referencia FULL; INC referencia el BACKUP anterior (FULL/DIFF/INC).
restore_demo usa included_tables para TRUNCATE antes de aplicar DIFF/INC.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import pathlib
import subprocess
import sys
import time

import boto3  # boto3 viene en imagen opcional usar sin credenciales
import psycopg
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("backup-worker")

DUMP_URL = os.environ.get("DATABASE_DUMP_URL", "").strip()
REGISTRY_URL = os.environ.get("BACKUP_REGISTRY_URL", DUMP_URL).strip()
BACKUPS_DIR = pathlib.Path(os.environ.get("BACKUPS_DIR", "/backups")).resolve()

FULL_CRON = os.environ.get("FULL_CRON", "10 3 * * *").strip()
DIFF_CRON = os.environ.get("DIFF_CRON", "15 */6 * * *").strip()
INC_CRON = os.environ.get("INC_CRON", "20 */2 * * *").strip()
PURGE_CRON = os.environ.get("PURGE_CRON", "5 */4 * * *").strip()
RETENTION_DAYS = float(os.environ.get("RETENTION_DAYS", "14"))

S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_PREFIX = os.environ.get("S3_PREFIX", "dcc-control/").strip()
S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "").strip()
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1").strip()
AWS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()

SHA_EMPTY = hashlib.sha256(b"").hexdigest()


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def ensure_dirs() -> None:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: pathlib.Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return SHA_EMPTY
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_bucket_exists(client: object) -> None:
    """En AWS real el bucket debe existir; solo auto-crear con endpoint custom (MinIO/dev)."""
    cli = client  # boto3 client duck-typing
    try:
        getattr(cli, "head_bucket")(Bucket=S3_BUCKET)  # type: ignore[attr-defined]
    except Exception as ex:
        if not S3_ENDPOINT:
            raise RuntimeError(
                f"Bucket S3 '{S3_BUCKET}' no accesible en AWS. Créalo en la consola y revisa IAM."
            ) from ex
        getattr(cli, "create_bucket")(Bucket=S3_BUCKET)  # type: ignore[attr-defined]


def s3_upload(local: pathlib.Path, key: str) -> tuple[str | None, str]:
    """Sube el archivo y registra SHA-256 hex localmente (etag no siempre coincide)."""
    if not S3_BUCKET:
        LOG.info("S3_BUCKET vacío → subida omitida")
        return None, ""

    kwargs: dict[str, object] = dict(
        service_name="s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY or None,
        aws_secret_access_key=AWS_SECRET or None,
    )
    if S3_ENDPOINT:
        kwargs["endpoint_url"] = S3_ENDPOINT

    blob = local.read_bytes()
    client = boto3.client(**kwargs)  # type: ignore[arg-type]
    ensure_bucket_exists(client)

    client.put_object(Bucket=S3_BUCKET, Key=key, Body=blob)
    if S3_ENDPOINT:
        url = f"s3://{S3_BUCKET}/{key} (endpoint={S3_ENDPOINT})"
    else:
        url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
    return url, ""


def run_pg_dump(args: list[str]) -> tuple[float, pathlib.Path]:
    ensure_dirs()
    out_path = pathlib.Path(args[-1]).resolve()
    t0 = time.perf_counter()
    subprocess.run(args, check=True)
    return time.perf_counter() - t0, out_path


def sla_targets(cur: psycopg.Cursor) -> tuple[float, float]:
    cur.execute("SELECT target_rpo_sec, target_rto_sec FROM backup_sla_targets WHERE id=1")
    row = cur.fetchone()
    if not row:
        return (900.0, 2700.0)
    return float(row[0]), float(row[1])


def coerce_ts(value: object) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc)
    return None


def restore_point_previous_full(cur: psycopg.Cursor, exclude_last_n: int = 0) -> dt.datetime | None:
    """restore_point del penúltimo FULL con archivo (sirve como estimador de holgura de cadencia)."""
    cur.execute(
        """
        SELECT restore_point FROM backup_history
        WHERE kind='FULL'::backup_kind_t
          AND COALESCE(purged,false)=FALSE
          AND COALESCE(local_path,'') <> ''
        ORDER BY id DESC
        OFFSET %s LIMIT 1
        """,
        (exclude_last_n,),
    )
    row = cur.fetchone()
    return coerce_ts(row[0]) if row else None


def anchor_full_latest(cur: psycopg.Cursor) -> tuple[int | None, dt.datetime | None]:
    cur.execute(
        """
        SELECT id, restore_point FROM backup_history
        WHERE kind='FULL'::backup_kind_t
          AND COALESCE(purged,false)=FALSE
          AND COALESCE(local_path,'') <> ''
        ORDER BY id DESC LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return None, None
    return int(row[0]), coerce_ts(row[1])


def last_backup_row(cur: psycopg.Cursor) -> tuple[int, str]:
    cur.execute(
        """
        SELECT id, kind::text FROM backup_history
        WHERE COALESCE(purged,false)=FALSE
        ORDER BY id DESC LIMIT 1
        """
    )
    row = cur.fetchone()
    return (int(row[0]), str(row[1])) if row else (-1, "NONE")


def list_dirty_pairs(cur: psycopg.Cursor, mode: str) -> list[tuple[str, str]]:
    col = "touched_since_full" if mode == "DIFF" else "touched_since_any"
    cur.execute(
        f"""
        SELECT schema_name, table_name
        FROM backup_touch
        WHERE {col} IS TRUE
        ORDER BY schema_name, table_name
        """
    )
    return [(str(a), str(b)) for (a, b) in cur.fetchall()]


def reset_touch(cur: psycopg.Cursor, mode: str, pairs: list[tuple[str, str]]) -> None:
    if not pairs:
        return
    col = "touched_since_full" if mode == "DIFF" else "touched_since_any"
    sch = [p[0] for p in pairs]
    tbl = [p[1] for p in pairs]
    cur.execute(
        f"""
        UPDATE backup_touch bt
           SET {col}=FALSE
         FROM unnest(%s::text[], %s::text[]) AS d(s,t)
        WHERE bt.schema_name=d.s AND bt.table_name=d.t
        """,
        (sch, tbl),
    )


def insert_row(
    cur: psycopg.Cursor,
    *,
    kind: str,
    size_mb: float,
    duration_sec: float,
    restore_point: dt.datetime,
    local_path: str,
    checksum_sha256: str,
    depends_on_id: int | None,
    parent_full_id: int | None,
    snapshot_label: str | None,
    notes: str | None,
    included_tables: str | None,
    rpo_estimate_sec: float | None,
    sla_met_flag: bool,
    retention_until: dt.datetime | None,
    remote_url: str | None,
    cloud_object_key: str | None,
) -> int:
    cur.execute(
        """
        INSERT INTO backup_history (
          kind, size_mb, duration_sec, restore_point,
          local_path, remote_url, cloud_object_key,
          checksum_sha256,
          depends_on_id, parent_full_id,
          snapshot_label, notes, included_tables,
          rpo_estimate_sec,
          sla_met, retention_until
        )
        VALUES (
          %s::backup_kind_t, %s, %s, %s,
          %s, %s, %s,
          %s,
          %s, %s,
          %s, %s, %s,
          %s,
          %s, %s
        ) RETURNING id
        """,
        (
            kind,
            round(size_mb, 4),
            round(duration_sec, 4),
            restore_point,
            local_path or "",
            remote_url,
            cloud_object_key,
            checksum_sha256,
            depends_on_id,
            parent_full_id,
            snapshot_label,
            notes,
            included_tables,
            rpo_estimate_sec,
            sla_met_flag,
            retention_until,
        ),
    )
    rid = cur.fetchone()
    if not rid:
        raise RuntimeError("INSERT backup_history sin id")
    return int(rid[0])


def purge_old(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, local_path::text, cloud_object_key::text
            FROM backup_history
            WHERE COALESCE(retention_until, created_at + interval '365 days') < NOW()
              AND COALESCE(purged,false)=FALSE
              AND COALESCE(local_path,'') <> ''
            """
        )
        rows = cur.fetchall()
        for bid, lp, ck in rows:
            pth = pathlib.Path(str(lp))
            try:
                if pth.exists():
                    pth.unlink(missing_ok=True)
            except OSError:
                LOG.warning("No se pudo borrar archivo id=%s %s", bid, pth)

            try:
                if S3_BUCKET and ck:
                    kw: dict[str, object] = dict(service_name="s3", region_name=AWS_REGION)
                    if AWS_KEY:
                        kw["aws_access_key_id"] = AWS_KEY  # pragma: allow secret keyword
                        kw["aws_secret_access_key"] = AWS_SECRET
                    if S3_ENDPOINT:
                        kw["endpoint_url"] = S3_ENDPOINT
                    cli = boto3.client(**kw)  # type: ignore[arg-type]
                    cli.delete_object(Bucket=S3_BUCKET, Key=str(ck))
            except Exception as ex:
                LOG.warning("Borrado remoto omitido id=%s: %s", bid, ex)

            cur.execute("UPDATE backup_history SET purged=TRUE WHERE id=%s", (int(bid),))
    conn.commit()
    LOG.info("Purge: ejecutado sobre filas caducadas (si hubo).")


def purge_job() -> None:
    if not REGISTRY_URL:
        return
    try:
        with psycopg.connect(REGISTRY_URL, autocommit=False) as cx:
            purge_old(cx)
    except psycopg.Error as ex:
        LOG.warning("Purge omitido/error: %s", ex)


def snapshot_cli(label: str) -> None:
    run_full(snapshot_label=label, notes=f"Etiqueta {label}")


def run_full(*, snapshot_label: str | None = None, notes: str | None = None) -> None:
    if not DUMP_URL or not REGISTRY_URL:
        LOG.error("Configura DATABASE_DUMP_URL y BACKUP_REGISTRY_URL.")
        return
    ensure_dirs()
    ts = utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_file = BACKUPS_DIR / f"dcc_FULL_{ts}.dump"
    rp_start = utcnow()

    elapsed, dumped = run_pg_dump(["pg_dump", DUMP_URL, "-Fc", "--file", str(out_file)])

    digest = sha256_file(dumped)
    size_mb = dumped.stat().st_size / (1024.0 * 1024.0)

    with psycopg.connect(REGISTRY_URL, autocommit=False) as conn:
        with conn.cursor() as cur:
            prev_full_rp = restore_point_previous_full(cur, exclude_last_n=0)
            if prev_full_rp is None:
                rpo_estimate = None
                sla_met_flag = True
            else:
                rpo_estimate = max(0.0, (rp_start - prev_full_rp).total_seconds())
                sla_met_flag = rpo_estimate <= sla_targets(cur)[0]

            cur.execute("UPDATE backup_touch SET touched_since_full=FALSE, touched_since_any=FALSE")

            key = ""
            remote = None
            if S3_BUCKET:
                key = f"{S3_PREFIX}FULL/{dumped.name}"
                try:
                    remote, err = s3_upload(dumped, key)
                    if err:
                        LOG.warning("%s", err)
                except Exception as ex:
                    LOG.warning("FULL subida omitida/error: %s", ex)

            fid = insert_row(
                cur,
                kind="FULL",
                size_mb=size_mb,
                duration_sec=elapsed,
                restore_point=rp_start,
                local_path=str(out_file),
                checksum_sha256=digest,
                depends_on_id=None,
                parent_full_id=None,
                snapshot_label=snapshot_label,
                notes=notes,
                included_tables=None,
                rpo_estimate_sec=rpo_estimate,
                sla_met_flag=sla_met_flag,
                retention_until=rp_start + dt.timedelta(days=RETENTION_DAYS),
                remote_url=remote,
                cloud_object_key=key or None,
            )
        conn.commit()
        LOG.info("FULL terminado id=%s path=%s sha256=%s", fid, dumped, digest)


def run_diff() -> None:
    run_partial(kind="DIFF", depends_mode="FULL")


def run_inc() -> None:
    run_partial(kind="INC", depends_mode="ANY")


def resolve_parent_full_id(cur: psycopg.Cursor, depends_row_id: int) -> int | None:
    cur.execute(
        """
        SELECT kind::text, parent_full_id FROM backup_history WHERE id=%s
        """,
        (depends_row_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    k, pf = row
    if str(k).upper() == "FULL":
        return int(depends_row_id)
    if pf:
        return int(pf)
    return None


def run_partial(*, kind: str, depends_mode: str) -> None:
    if not DUMP_URL or not REGISTRY_URL:
        LOG.error("URLs de conexión faltantes.")
        return

    with psycopg.connect(REGISTRY_URL, autocommit=False) as conn:
        cur = conn.cursor()
        anchor_id, anchor_rp = anchor_full_latest(cur)
        latest_id_before, latest_kind_before = last_backup_row(cur)

        if anchor_id is None:
            conn.rollback()
            LOG.warning("%s omitido (sin FULL).", kind)
            return

        dirty_mode = "DIFF" if kind == "DIFF" else "INC"
        dirty_pairs = list_dirty_pairs(cur, dirty_mode)
        rp = utcnow()

        tgt_rpo, _tgt_rto = sla_targets(cur)
        sla_met_flag = False
        rpo_estimate: float | None = None
        if anchor_rp:
            gap = max(0.0, (rp - anchor_rp).total_seconds())
            sla_met_flag = gap <= tgt_rpo
            rpo_estimate = gap

        depends_on_target: int
        parent_full_calc: int
        notes: str | None = None
        included_tables: str | None = None
        elapsed = 0.0
        size_mb_val = 0.0
        digest_val = SHA_EMPTY
        uploaded_key: str | None = None
        remote_url_obj: str | None = None
        local_txt = ""

        if depends_mode == "FULL":
            depends_on_target = int(anchor_id)
            parent_full_calc = int(anchor_id)
        else:
            if latest_id_before < 1 or latest_kind_before == "NONE":
                conn.rollback()
                LOG.warning("INC omitido (sin historia previa).")
                return
            depends_on_target = int(latest_id_before)
            pf = resolve_parent_full_id(cur, depends_on_target) or anchor_id
            parent_full_calc = int(pf)

        if not dirty_pairs:
            notes = f"{kind}_SIN_TABLAS_MARCADAS"
            elapsed = 0.0
            size_mb_val = 0.0
            digest_val = SHA_EMPTY
            local_txt = ""
        else:
            ensure_dirs()
            ts = utcnow().strftime("%Y%m%dT%H%M%SZ")
            out_file = BACKUPS_DIR / f"dcc_{kind}_{ts}.dump"
            args = ["pg_dump", DUMP_URL, "-Fc", "--data-only"]
            for sch, tbl in dirty_pairs:
                args.extend(["-t", f"{sch}.{tbl}"])
            args.extend(["--file", str(out_file)])
            try:
                elapsed, dumped_path = run_pg_dump(args)
            except subprocess.CalledProcessError:
                conn.rollback()
                LOG.error("pg_dump (%s) falló; no se registra HISTORY.", kind)
                return

            digest_val = sha256_file(dumped_path)
            size_mb_val = dumped_path.stat().st_size / (1024.0 * 1024.0)
            local_txt = str(dumped_path)
            included_tables = ",".join([f"{a}.{b}" for a, b in dirty_pairs])
            uploaded_key = f"{S3_PREFIX}{kind}/{dumped_path.name}"
            reset_touch(cur, kind, dirty_pairs)
            try:
                if S3_BUCKET and uploaded_key:
                    remote_url_obj, _err = s3_upload(pathlib.Path(local_txt), uploaded_key)
            except Exception as ex:
                LOG.warning("SUBIDA DIFF/INC %s omitida/error: %s", kind, ex)

        fid = insert_row(
            cur,
            kind=kind,
            size_mb=size_mb_val,
            duration_sec=elapsed if dirty_pairs else 0.0,
            restore_point=rp,
            local_path=local_txt,
            checksum_sha256=digest_val,
            depends_on_id=depends_on_target,
            parent_full_id=parent_full_calc,
            snapshot_label=None,
            notes=notes,
            included_tables=included_tables,
            rpo_estimate_sec=rpo_estimate,
            sla_met_flag=sla_met_flag,
            retention_until=rp + dt.timedelta(days=RETENTION_DAYS),
            remote_url=remote_url_obj,
            cloud_object_key=uploaded_key,
        )

        conn.commit()
        LOG.info("%s registrado id=%s archivos=%s", kind, fid, len(dirty_pairs) if dirty_pairs else 0)


def sched_main() -> None:
    if not DUMP_URL:
        LOG.error("DATABASE_DUMP_URL requerido para arrancar el worker.")
        return
    LOG.info(
        "Programación UTC — FULL:'%s' DIFF:'%s' INC:'%s' purge:'%s'",
        FULL_CRON,
        DIFF_CRON,
        INC_CRON,
        PURGE_CRON,
    )

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_full, CronTrigger.from_crontab(FULL_CRON), max_instances=1, coalesce=True, misfire_grace_time=600)
    scheduler.add_job(run_diff, CronTrigger.from_crontab(DIFF_CRON), max_instances=1, coalesce=True, misfire_grace_time=600)
    scheduler.add_job(run_inc, CronTrigger.from_crontab(INC_CRON), max_instances=1, coalesce=True, misfire_grace_time=600)
    scheduler.add_job(purge_job, CronTrigger.from_crontab(PURGE_CRON), max_instances=1)

    # arranque inmediato LIGHT (solo DIFF/INC suaves) — opcional FULL se deja solo a cron si FULL_BOOTSTRAP=0 (default)

    bootstrap = os.environ.get("FULL_BOOTSTRAP_ON_STARTUP", "0").strip().lower() in {"1", "true", "yes"}

    LOG.info(
        "CRON inicial ok. FULL inicial según FULL_BOOTSTRAP_ON_STARTUP=%s",
        os.environ.get("FULL_BOOTSTRAP_ON_STARTUP", "0"),
    )
    if bootstrap:
        run_full(notes="Arranque contenedor FULL_BOOTSTRAP")

    scheduler.start()


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "snapshot" and len(argv) >= 3:
        lbl = argv[2].strip()
        snapshot_cli(lbl)
        return 0
    sched_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
