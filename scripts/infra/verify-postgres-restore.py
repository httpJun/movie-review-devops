#!/usr/bin/env python3
"""로컬 backup-lab의 앱 DB 백업 및 새 DB 복원 검증."""

from datetime import datetime
import json
from pathlib import Path
import subprocess
import time

CONTEXT = "k3d-rancher-lab"
NAMESPACE = "backup-lab"
SOURCE_DB = "movie_app_lab"
stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
target_db = f"movie_restore_{stamp}"
output = Path.home() / "movie-review-backup-lab" / f"auto-{stamp}"

base = [
    "kubectl", "--context", CONTEXT, "-n", NAMESPACE,
    "exec", "-i", "postgres-0", "--",
]

snapshot_sql = """
SELECT 'movies', count(*),
       md5(string_agg(row_to_json(m)::text, E'\n' ORDER BY movie_id))
FROM movies m;
SELECT 'reviews', count(*),
       md5(string_agg(row_to_json(r)::text, E'\n' ORDER BY review_id))
FROM reviews r;
SELECT 'alembic_version', version_num
FROM alembic_version ORDER BY version_num;
"""

def run(args, **kwargs):
    return subprocess.run(base + args, check=True, **kwargs)

def query(db, sql):
    return run(
        ["psql", "-X", "-v", "ON_ERROR_STOP=1",
         "-U", "lab", "-d", db, "-At", "-c", sql],
        capture_output=True, text=True,
    ).stdout

output.mkdir(parents=True, exist_ok=False)
print(f"기록 경로: {output}", flush=True)
print(f"복원 대상 DB: {target_db}", flush=True)

try:
    before = query(SOURCE_DB, snapshot_sql)
    (output / "before.txt").write_text(before, encoding="utf-8")

    backup = output / "movie_app_lab.dump"
    with backup.open("wb") as stream:
        run(["pg_dump", "-U", "lab", "-d", SOURCE_DB, "-Fc"],
            stdout=stream)
    if backup.stat().st_size == 0:
        raise RuntimeError("백업 파일이 비어 있습니다.")

    with backup.open("rb") as stream:
        listing = run(["pg_restore", "--list"],
                      stdin=stream, capture_output=True)
    (output / "backup-contents.txt").write_bytes(listing.stdout)

    run(["createdb", "-U", "lab", "-T", "template0", target_db])

    with backup.open("rb") as stream, \
         (output / "restore.log").open("wb") as log:
        started = time.perf_counter()
        run(
            ["pg_restore", "-U", "lab", "-d", target_db,
             "--exit-on-error", "--single-transaction"],
            stdin=stream, stdout=log, stderr=log,
        )
        elapsed = time.perf_counter() - started

    after = query(target_db, snapshot_sql)
    (output / "after.txt").write_text(after, encoding="utf-8")

    orphan_count = int(query(target_db, """
        SELECT count(*) FROM reviews r
        LEFT JOIN movies m ON m.movie_id = r.movie_id
        WHERE m.movie_id IS NULL;
    """).strip())

    tables_sql = """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' ORDER BY tablename;
    """
    source_tables = query(SOURCE_DB, tables_sql)
    restored_tables = query(target_db, tables_sql)
    (output / "restored-tables.txt").write_text(
        restored_tables, encoding="utf-8"
    )

    passed = (
        before == after
        and source_tables == restored_tables
        and orphan_count == 0
    )
    result = {
        "context": CONTEXT,
        "source_database": SOURCE_DB,
        "target_database": target_db,
        "backup_bytes": backup.stat().st_size,
        "restore_seconds": round(elapsed, 6),
        "snapshot_match": before == after,
        "table_list_match": source_tables == restored_tables,
        "orphan_reviews": orphan_count,
        "passed": passed,
    }
    (output / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    if not passed:
        raise SystemExit("검증 실패 — 기록 파일을 확인하세요.")
    print("검증 성공: 백업·새 DB 복원·데이터 비교 완료")

except subprocess.CalledProcessError as error:
    if error.stderr:
        print(error.stderr)
    raise SystemExit(
        f"명령 실패. 기록 경로: {output}\n"
        "생성된 복원 DB와 파일은 진단을 위해 유지합니다."
    )
