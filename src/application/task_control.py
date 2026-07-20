from __future__ import annotations

import threading

from src.domain.models import TaskState


class TaskController:
    """线程安全状态机；暂停和停止只在业务安全点生效。"""

    def __init__(self) -> None:
        self._state = TaskState.RUNNING
        self._condition = threading.Condition()

    @property
    def state(self) -> TaskState:
        with self._condition:
            return self._state

    def request_pause(self) -> bool:
        with self._condition:
            if self._state != TaskState.RUNNING:
                return False
            self._state = TaskState.PAUSING
            self._condition.notify_all()
            return True

    def resume(self) -> bool:
        with self._condition:
            if self._state not in {TaskState.PAUSED, TaskState.PAUSING}:
                return False
            self._state = TaskState.RUNNING
            self._condition.notify_all()
            return True

    def request_stop(self) -> bool:
        with self._condition:
            if self._state in {TaskState.STOPPED, TaskState.COMPLETED, TaskState.FAILED}:
                return False
            self._state = TaskState.STOPPING
            self._condition.notify_all()
            return True

    def safe_point(self, on_pause=None, on_stop=None) -> bool:
        with self._condition:
            if self._state == TaskState.STOPPING:
                if on_stop:
                    on_stop()
                self._state = TaskState.STOPPED
                self._condition.notify_all()
                return False
            if self._state == TaskState.PAUSING:
                if on_pause:
                    on_pause()
                self._state = TaskState.PAUSED
                self._condition.notify_all()
            while self._state == TaskState.PAUSED:
                self._condition.wait(timeout=0.25)
            if self._state == TaskState.STOPPING:
                if on_stop:
                    on_stop()
                self._state = TaskState.STOPPED
                self._condition.notify_all()
                return False
            return self._state == TaskState.RUNNING

    def mark_completed(self) -> None:
        with self._condition:
            if self._state == TaskState.RUNNING:
                self._state = TaskState.COMPLETED
                self._condition.notify_all()

    def mark_failed(self) -> None:
        with self._condition:
            self._state = TaskState.FAILED
            self._condition.notify_all()

