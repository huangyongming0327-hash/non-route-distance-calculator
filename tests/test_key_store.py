from __future__ import annotations

from src.security.key_store import SecureKeyStore, mask_key


class FakeBackend:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.value = None
        self.deleted = False

    def load(self):
        if self.fail:
            raise OSError("unavailable")
        return self.value

    def save(self, value):
        if self.fail:
            raise OSError("unavailable")
        self.value = value

    def delete(self):
        if self.fail:
            raise OSError("unavailable")
        self.value = None
        self.deleted = True


def test_mask_key_reveals_only_required_edges():
    assert mask_key("ABCDEF1234") == "ABC***34"
    assert mask_key("short") == "***"
    assert mask_key("") == "未保存"


def test_key_store_prefers_first_persistent_backend(tmp_path):
    first = FakeBackend("credential-manager")
    second = FakeBackend("dpapi")
    store = SecureKeyStore(tmp_path, persistent_backends=[first, second])
    state = store.save("  SECRET-KEY  ")
    assert state.backend == "credential-manager"
    assert state.persisted is True
    assert store.get_key() == "SECRET-KEY"
    assert second.value is None


def test_key_store_falls_back_to_dpapi_then_memory(tmp_path):
    unavailable = FakeBackend("credential-manager", fail=True)
    dpapi = FakeBackend("dpapi")
    store = SecureKeyStore(tmp_path, persistent_backends=[unavailable, dpapi])
    assert store.save("SECRET").backend == "dpapi"

    memory_only = SecureKeyStore(
        tmp_path,
        persistent_backends=[FakeBackend("one", fail=True), FakeBackend("two", fail=True)],
    )
    state = memory_only.save("MEMORY-SECRET")
    assert state.persisted is False
    assert state.backend == "仅当前运行内存"
    assert memory_only.get_key() == "MEMORY-SECRET"


def test_key_store_delete_clears_all_backends(tmp_path):
    first = FakeBackend("first")
    second = FakeBackend("second")
    first.value = "A"
    second.value = "B"
    store = SecureKeyStore(tmp_path, persistent_backends=[first, second])
    store.delete()
    assert first.deleted and second.deleted
    assert store.get_key() is None
