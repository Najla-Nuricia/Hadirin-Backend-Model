"""Runtime testing toggles that can be switched by an authenticated lecturer.

Disimpan in-memory karena hanya dipakai untuk pengujian; kembali ke False
saat server di-restart. Satu dosen (NIP) hanya mengontrol togglenya sendiri.
"""

from threading import Lock


class _TestingToggleStore:
    def __init__(self) -> None:
        self._location_bypass: set[str] = set()
        self._lock = Lock()

    def is_location_bypass_enabled(self, nip: str | None) -> bool:
        if not nip:
            return False
        with self._lock:
            return str(nip).strip() in self._location_bypass

    def set_location_bypass(self, nip: str, enabled: bool) -> None:
        key = str(nip).strip()
        with self._lock:
            if enabled:
                self._location_bypass.add(key)
            else:
                self._location_bypass.discard(key)


testing_toggles = _TestingToggleStore()
