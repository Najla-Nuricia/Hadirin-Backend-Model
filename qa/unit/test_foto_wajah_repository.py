"""Unit tests for pgvector serialization in `FotoWajahRepository` (no live DB)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ExternalServiceError
from app.db.repositories.foto_wajah_repository import (
    EMBEDDING_DIMENSION,
    FotoWajahRepository,
    parse_embedding,
    to_vector_literal,
)


def test_parse_embedding_accepts_legacy_list_and_pgvector_literal() -> None:
    assert parse_embedding([0.1, 0.2]) == [0.1, 0.2]
    assert parse_embedding("[0.1, 0.2, -0.3]") == [0.1, 0.2, -0.3]
    assert parse_embedding(None) == []
    assert parse_embedding("[]") == []


def test_parse_embedding_rejects_garbage() -> None:
    with pytest.raises(ExternalServiceError):
        parse_embedding("[not,a,vector]")


def test_to_vector_literal_enforces_mobilefacenet_dimension() -> None:
    literal = to_vector_literal([0.25] * EMBEDDING_DIMENSION)
    assert literal.startswith("[0.25")
    assert literal.endswith("]")
    assert len(literal.strip("[]").split(",")) == EMBEDDING_DIMENSION

    with pytest.raises(ExternalServiceError):
        to_vector_literal([0.1] * 128)
    with pytest.raises(ExternalServiceError):
        to_vector_literal(["x"] * EMBEDDING_DIMENSION)


def test_create_many_serializes_embeddings_as_pgvector_literals() -> None:
    client = MagicMock()
    result = MagicMock()
    result.execute.return_value = SimpleNamespace(data=[{"id": "new-row"}])
    client.table.return_value.insert.return_value = result
    repo = FotoWajahRepository(client=client, settings=MagicMock())

    created = repo.create_many([
        {"nim": "24000001", "embedding": [0.5] * EMBEDDING_DIMENSION, "is_active": True}
    ])

    payload = client.table.return_value.insert.call_args.args[0]
    assert created == [{"id": "new-row"}]
    assert isinstance(payload[0]["embedding"], str)
    assert len(payload[0]["embedding"].strip("[]").split(",")) == EMBEDDING_DIMENSION
