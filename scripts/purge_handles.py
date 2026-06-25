#!/usr/bin/env python3
"""Remove KOL leaderboard entries and all linked mentions for one or more handles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.services.kol import purge_author_handle

DEFAULT_HANDLES = ["@marachadev", "@crud_cq5ds0", "@queuecrud"]


def main() -> int:
    handles = sys.argv[1:] or DEFAULT_HANDLES
    db = SessionLocal()
    try:
        for handle in handles:
            result = purge_author_handle(db, handle)
            print(result)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
