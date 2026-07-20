from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Protocol


CREDENTIAL_TARGET = "AmapTruckDistance/WebServiceKey/v1"


def mask_key(value: str | None) -> str:
    """只显示前三位和后两位；短值不暴露任何原文。"""
    key = (value or "").strip()
    if not key:
        return "未保存"
    if len(key) < 6:
        return "***"
    return f"{key[:3]}***{key[-2:]}"


@dataclass(frozen=True)
class KeyState:
    key: str | None
    backend: str
    persisted: bool

    @property
    def masked(self) -> str:
        return mask_key(self.key)


class KeyBackend(Protocol):
    name: str

    def load(self) -> str | None: ...

    def save(self, value: str) -> None: ...

    def delete(self) -> None: ...


class WindowsCredentialBackend:
    name = "Windows Credential Manager"

    def load(self) -> str | None:
        import win32cred

        try:
            item = win32cred.CredRead(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC)
        except Exception as exc:
            not_found = getattr(win32cred, "ERROR_NOT_FOUND", 1168)
            if getattr(exc, "winerror", None) == not_found or (
                getattr(exc, "args", ()) and exc.args[0] == not_found
            ):
                return None
            raise
        blob = item.get("CredentialBlob", b"")
        if isinstance(blob, bytes):
            return blob.decode("utf-16-le").rstrip("\x00")
        return str(blob) or None

    def save(self, value: str) -> None:
        import win32cred

        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": CREDENTIAL_TARGET,
                "CredentialBlob": value.encode("utf-16-le"),
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                "UserName": os.environ.get("USERNAME", "current-user"),
                "Comment": "非线路运距计算工具高德 Web 服务 Key",
            },
            0,
        )

    def delete(self) -> None:
        import win32cred

        try:
            win32cred.CredDelete(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC)
        except Exception as exc:
            not_found = getattr(win32cred, "ERROR_NOT_FOUND", 1168)
            if getattr(exc, "winerror", None) == not_found or (
                getattr(exc, "args", ()) and exc.args[0] == not_found
            ):
                return
            raise


class DpapiFileBackend:
    name = "Windows DPAPI（当前用户）"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> str | None:
        if not self.path.exists():
            return None
        import win32crypt

        _description, clear = win32crypt.CryptUnprotectData(self.path.read_bytes(), None, None, None, 0)
        return clear.decode("utf-8") or None

    def save(self, value: str) -> None:
        import win32crypt

        encrypted = win32crypt.CryptProtectData(
            value.encode("utf-8"), "AmapTruckDistance", None, None, None, 0
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def delete(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class SecureKeyStore:
    """Credential Manager → DPAPI → 内存的安全降级链。"""

    def __init__(
        self,
        project_root: str | Path,
        *,
        persistent_backends: list[KeyBackend] | None = None,
    ) -> None:
        root = Path(project_root).resolve()
        self._persistent = persistent_backends if persistent_backends is not None else [
            WindowsCredentialBackend(),
            DpapiFileBackend(root / "config" / "local_amap_key.credential"),
        ]
        self._memory: str | None = None

    def load(self) -> KeyState:
        for backend in self._persistent:
            try:
                value = backend.load()
            except Exception:
                continue
            if value:
                return KeyState(value, backend.name, True)
        if self._memory:
            return KeyState(self._memory, "仅当前运行内存", False)
        return KeyState(None, "未配置", False)

    def get_key(self) -> str | None:
        return self.load().key

    def save(self, value: str) -> KeyState:
        key = value.strip()
        if not key:
            raise ValueError("Key 不能为空。")
        for backend in self._persistent:
            try:
                backend.save(key)
                self._memory = None
                return KeyState(key, backend.name, True)
            except Exception:
                continue
        self._memory = key
        return KeyState(key, "仅当前运行内存", False)

    def delete(self) -> None:
        failures: list[str] = []
        for backend in self._persistent:
            try:
                backend.delete()
            except Exception:
                failures.append(backend.name)
        self._memory = None
        if failures:
            raise RuntimeError("以下安全存储无法删除：" + "、".join(failures))
