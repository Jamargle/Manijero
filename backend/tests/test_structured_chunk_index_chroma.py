"""One real-Chroma build of the structured index, with a fake four-dimension embedder.

Skipped when the optional ``chromadb`` runtime is absent (the default backend
environment). Run it with the pinned hybrid runtime::

    backend/.venv-hybrid/bin/python -m pytest backend/tests/test_structured_chunk_index_chroma.py

No model is loaded and nothing is downloaded.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("chromadb")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import structured_chunk_index as sci  # noqa: E402
from app.embeddings import load_model_spec  # noqa: E402
from app.retrieval import Retriever  # noqa: E402
from app.vector_store import STORE_UP_TO_DATE, ChromaPassageStore, store_status  # noqa: E402

FIXTURES = BACKEND_ROOT / "tests" / "fixtures"
CHUNKS = FIXTURES / "structured_chunk_index" / "chunks"
CATALOG = FIXTURES / "legal_structure_chunker" / "source_catalog.json"
SPEC_PATH = FIXTURES / "embeddings" / "spec.json"
AS_OF = date(2099, 6, 1)


class FakeEmbedder:
    model_id = "fixture/embedding-model"
    model_revision = "0123456789abcdef0123456789abcdef01234567"
    dimension = 4
    normalized = True

    def embed(self, texts):
        return tuple(tuple(1.0 if column == position % 4 else 0.0 for column in range(4)) for position, _ in enumerate(texts))


def test_real_chroma_store_is_built_recorded_and_deeply_verified(tmp_path: Path) -> None:
    from app.vector_store import write_store

    options = sci.VectorOptions(
        artifact=tmp_path,
        config=SPEC_PATH,
        load_embedder=lambda spec, artifact: FakeEmbedder(),
        write_store=write_store,
    )
    report = sci.build_index(
        chunks_root=CHUNKS,
        catalog_path=CATALOG,
        output_root=tmp_path / "index",
        as_of=AS_OF,
        active_campaign="2099",
        reviewed_baseline_revision="0123456789abcdef0123456789abcdef01234567",
        vectors=options,
    )
    index = tmp_path / "index"
    verified = sci.verify_index(index)
    assert verified.manifest["vectors"] == report.manifest["vectors"]

    spec = load_model_spec(SPEC_PATH)
    retriever = Retriever.from_documents(verified.catalog, verified.passages, AS_OF, "2099")
    status = store_status(index / "vector-store", spec, "2099", retriever.indexed_documents())
    assert status.state == STORE_UP_TO_DATE
    store = ChromaPassageStore.open(index / "vector-store", spec)
    assert sorted(json.loads((index / "structured-passages.json").read_text(encoding="utf-8"))["passages"][0]) == [
        "id",
        "location",
        "source_id",
        "text",
    ]
    assert store.query([1.0, 0.0, 0.0, 0.0], depth=2)
    assert report.manifest["vectors"]["documents_sha256"] == store.manifest["inputs"]["documents_sha256"]
