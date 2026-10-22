#!/usr/bin/env python3
"""Fill a `Property Address` in a Harris County FRCL sale CSV — per case number.

Parallel-safe and idempotent:
  * exclusive `fcntl.flock` on a sidecar <csv>.lock  -> serializes concurrent writers
  * writes to a temp file then os.replace()          -> readers never see a torn file
  * if the row's address cell is already filled, the case is SKIPPED (no
    file change); pass --force to overwrite an existing value
Requires POSIX (Linux/macOS).

Usage:
  python3 append_address.py --csv PATH --case FRCL-2026-7606 \
      --address "2847 Trail Lake Drive, Houston, TX 77045"
  python3 append_address.py --csv PATH --case FRCL-2026-7606 \
      --address "..." --force    # overwrite an already-recorded address
"""
import argparse
import contextlib
import csv
import os
import sys
import tempfile


def die(msg):
    print("ERROR:", msg)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Record a FRCL case's physical address in the sale CSV.")
    ap.add_argument("--csv", required=True, help="Path to property_data.csv")
    ap.add_argument("--case", required=True, help="Exact File Name cell, e.g. FRCL-2026-7606")
    ap.add_argument("--address", required=True, help="Physical/street address value")
    ap.add_argument("--col", default="Property Address", help="Column name (default: Property Address)")
    ap.add_argument("--force", action="store_true", help="Overwrite even if the cell already has an address (default: skip)")
    a = ap.parse_args()

    csv_path = os.path.abspath(a.csv)
    lock_path = csv_path + ".lock"
    dir_ = os.path.dirname(csv_path)

    try:
        import fcntl
    except ImportError:
        die("fcntl not available (this host needs POSIX/Linux for the lock)")

    lid = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lid, fcntl.LOCK_EX)  # hold for the whole read-modify-write

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows:
            die("CSV is empty: " + csv_path)
        header = rows[0]

        # ensure column exists (append if this is the first run)
        if a.col in header:
            idx = header.index(a.col)
        else:
            header.append(a.col)
            idx = len(header) - 1
        for r in rows[1:]:
            while len(r) < len(header):
                r.append("")

        matched = []
        for r in rows[1:]:
            if (r[0] or "").strip() == a.case:
                matched.append(r)
        if len(matched) != 1:
            die(f"expected exactly 1 row for {a.case!r}; matched {len(matched)}")

        # skip if the address is already recorded (unless --force)
        cur = (matched[0][idx] or "").strip() if idx < len(matched[0]) else ""
        if cur and not a.force:
            print(f"SKIPPED: {a.case} already has address {cur!r}; use --force to overwrite")
            return
        overwrote = bool(cur)
        matched[0][idx] = a.address

        # atomic write: temp file in the same dir, then os.replace
        tfd, tmp = tempfile.mkstemp(dir=dir_, prefix=".addr-", suffix=".csv")
        try:
            with os.fdopen(tfd, "w", newline="", encoding="utf-8") as tf:
                w = csv.writer(tf, lineterminator="\r\n")
                w.writerow(header)
                for r in rows[1:]:
                    w.writerow(r)
            os.replace(tmp, csv_path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        ok = "OK (overwrote existing address):" if overwrote else "OK:"
        print(f"{ok} {a.case} -> {a.address!r}  [{a.col}] = column #{idx + 1}; total data rows {len(rows) - 1}")
    finally:
        try:
            fcntl.flock(lid, fcntl.LOCK_UN)
        finally:
            os.close(lid)


if __name__ == "__main__":
    main()
