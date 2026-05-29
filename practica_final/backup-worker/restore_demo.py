#!/usr/bin/env python3
"""
Cadena FULL → DIFF → INC en una base nueva y medición opcional del RTO.
Usa rutas locales registradas en backup_history.

Ejemplo:
  docker compose run --rm backup-worker python restore_demo.py --measure-rto

Variables:
  DATABASE_DUMP_URL  (postgresql://...@host:5432/dcc_control origen restores)
  BACKUP_REGISTRY_URL (igual suele bastar para leer metadatos + TRUNCATE)
  POSTGRES_ADMIN_URL (postgresql://...@host:5432/postgres opcional para DROP/CREATE)
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.parse as up
from pathlib import Path

import psycopg
from psycopg import sql

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore[assignment]

_SAFE_DB = re.compile(r"^[A-Za-z0-9_]{1,63}$")

S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "").strip()
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1").strip()
AWS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
BACKUPS_DIR = Path(os.environ.get("BACKUPS_DIR", "/backups"))


def make_admin_dsn(pg_dsn: str, *, admin_db: str) -> str:
    p = up.urlparse(pg_dsn)
    user_raw = up.unquote(p.username or "")
    pwd_raw = up.unquote(p.password or "") if p.password is not None else ""
    host = p.hostname or "localhost"
    port = p.port or 5432

    auth = ""
    if user_raw or pwd_raw is not None:
        user_part = up.quote(user_raw or "", safe="")
        pwd_part = up.quote(pwd_raw, safe="")
        if pwd_raw != "":
            auth = f"{user_part}:{pwd_part}@"
        else:
            auth = f"{user_part}@" if user_part else ""

    netloc = f"{auth}{host}:{port}"
    return up.urlunsplit(("postgresql", netloc, f"/{admin_db}", "", ""))


def swap_dbname(pg_dsn: str, new_db: str) -> str:
    p = up.urlparse(pg_dsn)
    user_raw = up.unquote(p.username or "")
    pwd_raw = up.unquote(p.password or "") if p.password is not None else ""
    host = p.hostname or "localhost"
    port = p.port or 5432

    auth = ""
    if user_raw or pwd_raw is not None:
        user_part = up.quote(user_raw or "", safe="")
        pwd_part = up.quote(pwd_raw, safe="")
        if pwd_raw != "":
            auth = f"{user_part}:{pwd_part}@"
        else:
            auth = f"{user_part}@" if user_part else ""

    netloc = f"{auth}{host}:{port}"
    return up.urlunsplit(("postgresql", netloc, f"/{new_db}", "", ""))


def run_restore(argv: list[str]) -> None:
    print("+", " ".join(argv))
    subprocess.run(argv, check=True)


def resolve_backup_path(local_path: str, cloud_key: str | None) -> Path:
    p = Path(local_path) if local_path else Path()
    if p.exists():
        return p
    if not S3_BUCKET or not cloud_key:
        raise FileNotFoundError(f"Archivo local no encontrado: {local_path}")
    if boto3 is None:
        raise RuntimeError("boto3 requerido para descargar desde S3")
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUPS_DIR / Path(cloud_key).name
    kw: dict[str, object] = dict(
        service_name="s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY or None,
        aws_secret_access_key=AWS_SECRET or None,
    )
    if S3_ENDPOINT:
        kw["endpoint_url"] = S3_ENDPOINT
    client = boto3.client(**kw)  # type: ignore[arg-type]
    print(f"Descargando s3://{S3_BUCKET}/{cloud_key} -> {target}")
    client.download_file(S3_BUCKET, cloud_key, str(target))
    return target


def fetch_latest_full(cur, full_id: int | None) -> tuple[int, Path]:
    if full_id:
        cur.execute(
            """
            SELECT id, local_path::text, cloud_object_key::text FROM backup_history
            WHERE id=%s AND kind='FULL'::backup_kind_t
              AND COALESCE(purged,false)=false
              AND (COALESCE(local_path,'')<>'' OR cloud_object_key IS NOT NULL)
            """,
            (full_id,),
        )
    else:
        cur.execute(
            """
            SELECT id, local_path::text, cloud_object_key::text FROM backup_history
            WHERE kind='FULL'::backup_kind_t
              AND COALESCE(purged,false)=false
              AND (COALESCE(local_path,'')<>'' OR cloud_object_key IS NOT NULL)
            ORDER BY id DESC LIMIT 1
            """
        )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No existe un FULL recuperable.")
    fid, lp, ck = row
    return int(fid), resolve_backup_path(str(lp or ""), str(ck) if ck else None)


def fetch_chain(cur, anchor_id: int) -> list[tuple[str, Path, str]]:
    cur.execute(
        """
        WITH RECURSIVE chain AS (
            SELECT bh.* FROM backup_history bh WHERE bh.id=%s
            UNION ALL
            SELECT bh.* FROM backup_history bh
              INNER JOIN chain c ON bh.depends_on_id = c.id
        )
        SELECT kind::text, local_path::text, cloud_object_key::text,
               COALESCE(included_tables,''), COALESCE(notes,''), id
        FROM chain
        ORDER BY created_at ASC, id ASC
        """,
        (anchor_id,),
    )
    out: list[tuple[str, Path, str]] = []
    for kind, lp, ck, inc, notes, _bid in cur.fetchall():
        if notes and "SKIP" in notes.upper():
            continue
        if not lp and not ck:
            continue
        path = resolve_backup_path(str(lp or ""), str(ck) if ck else None)
        out.append((str(kind), path, str(inc or "")))
    return out


def truncate_for_partial(cur, tables_csv: str) -> None:
    parts = [p.strip() for p in tables_csv.split(",") if p.strip()]
    if not parts:
        return
    identifiers: list[sql.SQL] = []
    for fq in parts:
        if fq.count(".") != 1:
            continue
        sch, tbl = fq.split(".", 1)
        identifiers.append(sql.SQL("{}.{}").format(sql.Identifier(sch), sql.Identifier(tbl)))
    if not identifiers:
        return
    stmt = sql.SQL("TRUNCATE TABLE {} CASCADE").format(sql.SQL(", ").join(identifiers))
    cur.execute(stmt)


def update_rto_metric(reg_url: str, full_backup_id: int, seconds: float) -> None:
    with psycopg.connect(reg_url, autocommit=True) as reg:
        with reg.cursor() as cur:
            cur.execute(
                "UPDATE backup_history SET rto_observed_sec=%s WHERE id=%s",
                (round(seconds, 3), full_backup_id),
            )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recovery-db", default=os.environ.get("RECOVERY_DATABASE", "dcc_control_recovery"))
    ap.add_argument("--full-id", type=int, default=None)
    ap.add_argument("--measure-rto", action="store_true")
    args = ap.parse_args(argv)

    dump_url = os.environ.get("DATABASE_DUMP_URL", "").strip()
    reg_url = os.environ.get("BACKUP_REGISTRY_URL", dump_url).strip()
    if not dump_url or not reg_url:
        print("Configura DATABASE_DUMP_URL y BACKUP_REGISTRY_URL", file=sys.stderr)
        return 2

    if not _SAFE_DB.match(args.recovery_db):
        print("recovery-db inválido", file=sys.stderr)
        return 2

    admin_url = os.environ.get("POSTGRES_ADMIN_URL", "").strip() or make_admin_dsn(dump_url, admin_db="postgres")

    t0 = time.perf_counter()
    with psycopg.connect(reg_url, autocommit=True) as reg:
        with reg.cursor() as cur:
            full_id, full_path = fetch_latest_full(cur, args.full_id)
            chain = fetch_chain(cur, full_id)

    restore_target_url = swap_dbname(dump_url, args.recovery_db)

    print("Creando BD de recuperación:", args.recovery_db)
    with psycopg.connect(admin_url, autocommit=True) as adm:
        with adm.cursor() as c:
            c.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                (args.recovery_db,),
            )
            c.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(args.recovery_db))
            )
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(args.recovery_db)))

    print("Cadena ordenada:")
    for k, p, _inc in chain:
        print("-", k, p)

    for kind, path, inc in chain:
        if kind.upper() == "FULL":
            run_restore(["pg_restore", "--no-owner", "-d", restore_target_url, str(path)])
            continue

        kind_u = kind.upper()
        if kind_u in {"DIFF", "INC"}:
            with psycopg.connect(restore_target_url, autocommit=True) as cx:
                with cx.cursor() as cur:
                    truncate_for_partial(cur, inc)
            run_restore(["pg_restore", "--data-only", "--no-owner", "-d", restore_target_url, str(path)])

    elapsed = time.perf_counter() - t0
    print(f"Restore completado en {elapsed:.3f}s (RTO puntual)")
    if args.measure_rto:
        update_rto_metric(reg_url, full_id, elapsed)

    print("OK.")
    print("Conectar a la recuperación usando DB:", args.recovery_db)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as exc:
        print("Fallo pg_restore:", exc, file=sys.stderr)
        raise SystemExit(1)
