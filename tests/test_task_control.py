from __future__ import annotations

import threading
import time

from src.application.task_control import TaskController
from src.domain.models import TaskState


def test_pause_resume_state_machine():
    controller = TaskController()
    reached = threading.Event()

    def worker():
        controller.safe_point(on_pause=reached.set)

    assert controller.request_pause()
    thread = threading.Thread(target=worker)
    thread.start()
    assert reached.wait(1)
    for _ in range(100):
        if controller.state == TaskState.PAUSED:
            break
        time.sleep(0.01)
    assert controller.state == TaskState.PAUSED
    assert controller.resume()
    thread.join(1)
    assert controller.state == TaskState.RUNNING


def test_stop_at_safe_point():
    controller = TaskController()
    assert controller.request_stop()
    assert controller.safe_point() is False
    assert controller.state == TaskState.STOPPED


def test_invalid_resume_is_rejected():
    assert TaskController().resume() is False


def test_completed_is_terminal_for_pause():
    controller = TaskController()
    controller.mark_completed()
    assert controller.state == TaskState.COMPLETED
    assert controller.request_pause() is False


def test_failure_state():
    controller = TaskController()
    controller.mark_failed()
    assert controller.state == TaskState.FAILED
