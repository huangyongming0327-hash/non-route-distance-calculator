from __future__ import annotations

import gc
import time
from datetime import datetime
from typing import Any, Callable

import psutil
import pythoncom
import win32com.client
import win32gui
import win32process


MsoAutomationSecurityForceDisable = 3
XL_CALCULATION_MANUAL = -4135


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def process_snapshot(names: set[str]) -> list[dict[str, Any]]:
    windows: dict[int, list[dict[str, Any]]] = {}

    def enum_window(hwnd: int, _: Any) -> None:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if win32gui.IsWindowVisible(hwnd) or title:
                windows.setdefault(pid, []).append(
                    {"hwnd": hwnd, "title": title, "visible": bool(win32gui.IsWindowVisible(hwnd))}
                )
        except Exception:
            pass

    win32gui.EnumWindows(enum_window, None)
    result: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "create_time", "exe"]):
        try:
            name = (process.info.get("name") or "").lower()
            if name not in names:
                continue
            result.append(
                {
                    "pid": process.pid,
                    "name": name,
                    "created_at": datetime.fromtimestamp(process.info["create_time"]).astimezone().isoformat(timespec="seconds")
                    if process.info.get("create_time") else None,
                    "exe": process.info.get("exe"),
                    "windows": windows.get(process.pid, []),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(result, key=lambda item: (item["name"], item["pid"]))


def visible_window_fingerprint(processes: list[dict[str, Any]]) -> list[list[Any]]:
    return sorted(
        [item["pid"], window["hwnd"], window["title"]]
        for item in processes
        for window in item.get("windows", [])
        if window.get("visible")
    )


def pid_from_hwnd(hwnd: Any) -> int | None:
    try:
        return int(win32process.GetWindowThreadProcessId(int(hwnd))[1]) if hwnd else None
    except Exception:
        return None


def configure_office(app: Any) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for name, value in (
        ("AutomationSecurity", MsoAutomationSecurityForceDisable),
        ("EnableEvents", False),
        ("DisplayAlerts", False),
        ("AskToUpdateLinks", False),
        ("ScreenUpdating", False),
        ("Calculation", XL_CALCULATION_MANUAL),
    ):
        try:
            setattr(app, name, value)
            changes[name] = {"requested": value, "accepted": True, "readback": getattr(app, name, None)}
        except Exception as exc:
            changes[name] = {"requested": value, "accepted": False, "error": repr(exc)}
    for required in ("AutomationSecurity", "EnableEvents"):
        if not changes[required]["accepted"]:
            raise RuntimeError(f"Office 安全设置 {required} 未被接受，已阻止打开工作簿。")
    return changes


def _release_com() -> None:
    gc.collect()
    try:
        pythoncom.CoFreeUnusedLibraries()
    except Exception:
        pass
    pythoncom.CoUninitialize()
    gc.collect()


def excel_session(action: Callable[[Any, dict[str, Any]], Any]) -> tuple[Any, dict[str, Any]]:
    """独立 worker 内创建 Excel 专属实例，只精确管理已证明归属的 PID。"""
    pythoncom.CoInitialize()
    app = None
    before = process_snapshot({"excel.exe"})
    before_pids = {item["pid"] for item in before}
    audit: dict[str, Any] = {"started_at": now(), "processes_before": before}
    result = None
    try:
        app = win32com.client.DispatchEx("Excel.Application")
        hwnd = int(app.Hwnd)
        pid = pid_from_hwnd(hwnd)
        ownership = bool(pid and pid not in before_pids and pid_from_hwnd(hwnd) == pid)
        audit.update(
            {
                "dispatch": "DispatchEx(Excel.Application)", "hwnd": hwnd, "pid": pid,
                "hwnd_pid_match_at_creation": pid_from_hwnd(hwnd) == pid,
                "ownership_confirmed": ownership, "version": str(app.Version), "build": str(app.Build),
            }
        )
        if not ownership:
            raise RuntimeError("Excel 专属实例 Hwnd/PID 归属无法确认，已阻止保存。")
        audit["security_settings"] = configure_office(app)
        result = action(app, audit)
    finally:
        if app is not None:
            try:
                audit["open_workbook_count_before_quit"] = int(app.Workbooks.Count)
            except Exception as exc:
                audit["open_workbook_count_before_quit_error"] = repr(exc)
            try:
                app.Quit()
                audit["quit_called"] = True
            except Exception as exc:
                audit["quit_called"] = False
                audit["quit_error"] = repr(exc)
            del app
        _release_com()
        pid = audit.get("pid")
        for _ in range(150):
            if not (pid and psutil.pid_exists(pid)):
                break
            time.sleep(0.1)
        residual = bool(pid and psutil.pid_exists(pid))
        audit["exact_pid_terminate_fallback_used"] = False
        safe_fallback = bool(
            residual and audit.get("ownership_confirmed") and audit.get("open_workbook_count_before_quit") == 0
        )
        if safe_fallback:
            try:
                process = psutil.Process(pid)
                if process.name().lower() == "excel.exe":
                    process.terminate()
                    process.wait(timeout=10)
                    audit["exact_pid_terminate_fallback_used"] = True
                    audit["exact_pid_terminated"] = pid
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as exc:
                audit["exact_pid_terminate_error"] = repr(exc)
        after = process_snapshot({"excel.exe"})
        after_pids = {item["pid"] for item in after}
        audit["own_pid_residual"] = bool(pid and pid in after_pids)
        audit["preexisting_processes_unchanged"] = before_pids <= after_pids
        audit["processes_after"] = after
        audit["finished_at"] = now()
    return result, audit


def wps_session(action: Callable[[Any, dict[str, Any]], Any]) -> tuple[Any, dict[str, Any]]:
    """只有 Hwnd 映射到唯一新 ET PID 时才允许执行动作和调用 Quit。"""
    pythoncom.CoInitialize()
    app = None
    names = {"et.exe", "wps.exe", "wpsoffice.exe", "wpscloudsvr.exe"}
    before = process_snapshot(names)
    before_pids = {item["pid"] for item in before}
    # wpscloudsvr 是无工作簿窗口的云后台服务，会在 WPS 检查点之间自然
    # 重启；严格保护用户 ET/WPS/WPSOffice PID 和所有可见窗口，同时单独
    # 审计云服务变化，避免把后台服务生命周期误判为用户工作簿被关闭。
    protected_before_pids = {
        item["pid"] for item in before if item["name"] != "wpscloudsvr.exe"
    }
    cloud_before_pids = {
        item["pid"] for item in before if item["name"] == "wpscloudsvr.exe"
    }
    audit: dict[str, Any] = {
        "started_at": now(), "processes_before": before,
        "visible_windows_before": visible_window_fingerprint(before),
    }
    result = None
    isolated = False
    own_pids: set[int] = set()
    try:
        app = win32com.client.DispatchEx("KET.Application")
        time.sleep(0.8)
        hwnd = int(getattr(app, "Hwnd"))
        pid = pid_from_hwnd(hwnd)
        current = process_snapshot(names)
        new_processes = [item for item in current if item["pid"] not in before_pids]
        new_et_pids = {item["pid"] for item in new_processes if item["name"] == "et.exe"}
        own_pids = {item["pid"] for item in new_processes}
        isolated = bool(pid and pid in new_et_pids and len(new_et_pids) == 1)
        audit.update(
            {
                "dispatch": "DispatchEx(KET.Application)", "hwnd": hwnd, "pid": pid,
                "version": getattr(app, "Version", None), "build": getattr(app, "Build", None),
                "new_processes": new_processes, "new_et_pids": sorted(new_et_pids),
                "isolation_confirmed": isolated,
            }
        )
        if not isolated:
            raise RuntimeError("WPS 无法证明 COM Hwnd 属于唯一新建 ET PID；已停止且未调用 Quit/结束进程，请改用 Excel。")
        audit["security_settings"] = configure_office(app)
        result = action(app, audit)
    finally:
        if app is not None:
            if isolated:
                try:
                    app.Quit()
                    audit["quit_called"] = True
                except Exception as exc:
                    audit["quit_called"] = False
                    audit["quit_error"] = repr(exc)
            else:
                audit["quit_called"] = False
                audit["quit_not_called_reason"] = "归属未确认，为保护用户已有 WPS 未调用 Quit。"
            del app
        _release_com()
        for _ in range(150):
            if not any(psutil.pid_exists(pid) for pid in own_pids):
                break
            time.sleep(0.1)
        after = process_snapshot(names)
        after_pids = {item["pid"] for item in after}
        audit["own_pids"] = sorted(own_pids)
        audit["own_process_residual_pids"] = sorted(pid for pid in own_pids if pid in after_pids)
        audit["own_pid_residual"] = bool(audit["own_process_residual_pids"])
        audit["preexisting_processes_unchanged"] = protected_before_pids <= after_pids
        audit["protected_preexisting_pids"] = sorted(protected_before_pids)
        audit["cloud_service_pids_before"] = sorted(cloud_before_pids)
        audit["cloud_service_pids_after"] = sorted(
            item["pid"] for item in after if item["name"] == "wpscloudsvr.exe"
        )
        audit["cloud_service_processes_unchanged"] = cloud_before_pids == {
            item["pid"] for item in after if item["name"] == "wpscloudsvr.exe"
        }
        audit["visible_windows_after"] = visible_window_fingerprint(after)
        audit["preexisting_visible_windows_unchanged"] = (
            audit["visible_windows_before"] == audit["visible_windows_after"]
        )
        audit["processes_after"] = after
        audit["finished_at"] = now()
    return result, audit
