"""JSON file storage for the archive."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import List

from .models import EditorialArchive

DEFAULT_DB_PATH = "data/editorial_archives.json"


class JsonStorage:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)

    def load(self) -> List[EditorialArchive]:
        if not self.db_path.exists():
            return []
        with open(self.db_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [EditorialArchive.from_dict(d) for d in raw]

    def save(self, archives: List[EditorialArchive]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [a.to_dict() for a in archives]
        fd, tmp_path = tempfile.mkstemp(
            dir=self.db_path.parent, suffix=".tmp", prefix=self.db_path.name
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.db_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
