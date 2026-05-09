#!/usr/bin/env python3

import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


CSV_FILE = "migrations.csv"

SUCCESS_LOG = "success.log"
ERROR_LOG = "error.log"

# Extra free-space safety margin (1 GB)
SPACE_BUFFER_BYTES = 1 * 1024 * 1024 * 1024


# --------------------------------------------------
# Utility
# --------------------------------------------------


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_json(log_file: str, payload: dict):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def human_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.2f} {unit}"

        num /= 1024

    return f"{num:.2f} PB"


def ensure_dest_parent_exists(dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)


def get_free_space_bytes(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.free


# --------------------------------------------------
# Size Calculation
# --------------------------------------------------


def get_size_bytes(path: Path) -> int:
    """
    Uses:
        du -sb <path>

    Returns:
        Size in bytes as int
    """

    result = subprocess.run(
        ["du", "-sb", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )

    size_str = result.stdout.split()[0]

    return int(size_str)


# --------------------------------------------------
# Rsync Operations
# --------------------------------------------------


def run_rsync_copy(src: Path, dest: Path):
    cmd = [
        "rsync",
        "-ah",
        "--info=progress2",
        "--partial",
        str(src),
        str(dest),
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise Exception(
            f"rsync copy failed with exit code {result.returncode}"
        )


def run_rsync_verify(src: Path, dest: Path):
    """
    Verification strategy:
        - rsync dry-run
        - itemize changes

    If ANY meaningful output exists,
    source and destination differ.
    """
    """
    cmd = [
        "rsync",
        "-ahn",
        "--delete",
        "--itemize-changes",
        str(src),
        str(dest),
    ]
    """

    cmd = [
        "rsync",
        "-ahn",
        "--itemize-changes",
        str(src),
        str(dest),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise Exception(
            f"rsync verify failed with exit code {result.returncode}"
        )

    stdout = result.stdout.strip()

    meaningful_lines = []

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        # Ignore rsync summary noise
        if line.startswith("sending incremental file list"):
            continue

        if line.startswith("sent "):
            continue

        if line.startswith("total size is "):
            continue

        meaningful_lines.append(line)

    if meaningful_lines:
        raise Exception(
            "Verification failed. rsync detected differences:\n"
            + "\n".join(meaningful_lines[:20])
        )


# --------------------------------------------------
# Delete
# --------------------------------------------------


def delete_path(path: Path):
    if path.is_file() or path.is_symlink():
        path.unlink()

    elif path.is_dir():
        shutil.rmtree(path)

    else:
        raise Exception(f"Unsupported path type: {path}")


# --------------------------------------------------
# Migration Processing
# --------------------------------------------------


def process_mapping(src_raw: str, dest_raw: str):
    start_ts = now_iso()

    src = Path(src_raw).expanduser().resolve()
    dest = Path(dest_raw).expanduser().resolve()

    meta: dict[str, object] = {
        "start": start_ts,
        "src": str(src),
        "dest": str(dest),
    }

    try:
        if not src.exists():
            raise Exception("Source does not exist")

        ensure_dest_parent_exists(dest)

        src_size = get_size_bytes(src)
        free_space = get_free_space_bytes(dest.parent)

        meta["src_size_bytes"] = src_size
        meta["src_size_human"] = human_bytes(src_size)

        meta["dest_free_bytes"] = free_space
        meta["dest_free_human"] = human_bytes(free_space)

        required_space = src_size + SPACE_BUFFER_BYTES

        meta["required_space_bytes"] = required_space
        meta["required_space_human"] = human_bytes(required_space)

        if free_space < required_space:
            raise Exception(
                f"Insufficient destination space. "
                f"Required={human_bytes(required_space)}, "
                f"Available={human_bytes(free_space)}"
            )

        print("\n=== COPYING ===")
        print(f"SRC : {src}")
        print(f"DEST: {dest}")
        print(f"SIZE: {human_bytes(src_size)}")

        run_rsync_copy(src, dest)

        print("\n=== VERIFYING ===")

        run_rsync_verify(src, dest)

        print("Verification successful")

        print("\n=== DELETING SOURCE ===")

        delete_path(src)

        end_ts = now_iso()

        meta["end"] = end_ts
        meta["status"] = "success"

        log_json(SUCCESS_LOG, meta)

        print("Migration successful")

    except Exception as e:
        end_ts = now_iso()

        meta["end"] = end_ts
        meta["status"] = "error"
        meta["error"] = str(e)

        log_json(ERROR_LOG, meta)

        print(f"\nERROR: {e}")
        print("Source NOT deleted")


# --------------------------------------------------
# Main
# --------------------------------------------------


def main():
    if not os.path.exists(CSV_FILE):
        raise Exception(f"CSV file not found: {CSV_FILE}")

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)

        for row_num, row in enumerate(reader, start=1):
            try:
                if len(row) != 2:
                    raise Exception(
                        f"Invalid CSV row at line {row_num}: {row}"
                    )

                src, dest = row

                process_mapping(
                    src.strip(),
                    dest.strip(),
                )

            except KeyboardInterrupt:
                print("\nInterrupted by user")
                sys.exit(1)

            except Exception as e:
                payload = {
                    "start": now_iso(),
                    "end": now_iso(),
                    "status": "error",
                    "row": row_num,
                    "row_data": row,
                    "error": str(e),
                }

                log_json(ERROR_LOG, payload)

                print(f"\nERROR on row {row_num}: {e}")

                # Continue processing remaining rows


if __name__ == "__main__":
    main()



# Example `migrations.csv`
#
# ```csv
# "/mnt/Projects/0PhoneBackups","/media/vworld/MediaStore/PhoneBackups"
# "/mnt/Projects/Sonnis","/media/vworld/MediaStore/Sonnis"
# ```
#
# ---
#
# # Run
#
# ```bash
# python3 migrate.py
# ```
#
# ---
#
# # Notes
#
# * Safety-first behavior.
# * Source deleted ONLY after successful verification.
# * Continues processing next rows even on errors.
# * Uses rsync for both copy and verification.
# * Verification uses dry-run rsync comparison.
# * Logs are append-only JSON lines.
# * No recycle bin/trash.
# * Uses a 1 GB free-space safety buffer.
# * Handles paths with spaces safely.
