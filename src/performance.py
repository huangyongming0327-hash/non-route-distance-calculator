from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class PerformanceLogger:
    """线程安全的 JSONL 性能日志；只记录阶段和文件元数据，不记录工作簿内容。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(
        self,
        operation: str,
        stage: str,
        elapsed_ms: float,
        *,
        status: str = "completed",
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "operation": operation,
            "stage": stage,
            "elapsed_ms": round(float(elapsed_ms), 2),
            "status": status,
            "thread_id": threading.get_ident(),
            "details": details or {},
        }
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
