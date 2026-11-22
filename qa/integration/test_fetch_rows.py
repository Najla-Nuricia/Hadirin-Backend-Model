"""Tests for Supabase paginated `BaseRepository.fetch_rows_in` helper."""

from types import SimpleNamespace

from app.db.repositories.base import BaseRepository


class FakeQuery:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._start = 0
        self._end = 0

    def select(self, columns: str, count: str | None = None) -> "FakeQuery":
        return self

    def in_(self, column: str, values: list[str]) -> "FakeQuery":
        self._rows = [row for row in self._rows if row[column] in values]
        return self

    def order(self, column: str) -> "FakeQuery":
        self._rows = sorted(self._rows, key=lambda row: row[column])
        return self

    def range(self, start: int, end: int) -> "FakeQuery":
        self._start, self._end = start, end
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(
            data=self._rows[self._start : self._end + 1],
            count=len(self._rows),
        )


class FakeSupabase:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.requests = 0

    def table(self, name: str) -> FakeQuery:
        self.requests += 1
        return FakeQuery(list(self._rows))


def test_fetch_rows_in_reads_every_page() -> None:
    rows = [{"id": number, "kelas_id": "a"} for number in (5, 3, 1, 4, 2)]
    rows.append({"id": 6, "kelas_id": "b"})
    sb = FakeSupabase(rows)

    result = BaseRepository.fetch_rows_in(
        sb, "mahasiswa", "id, kelas_id", "kelas_id", ["a"], "id", page_size=2
    )

    assert [row["id"] for row in result] == [1, 2, 3, 4, 5]
    assert sb.requests == 3


def test_fetch_rows_in_skips_request_without_filter_values() -> None:
    sb = FakeSupabase([{"id": 1, "kelas_id": "a"}])

    assert (
        BaseRepository.fetch_rows_in(
            sb, "mahasiswa", "id", "kelas_id", [], "id", page_size=2
        )
        == []
    )
    assert sb.requests == 0
