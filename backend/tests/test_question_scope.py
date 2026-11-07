"""Tests for the pre-retrieval question-scope guard (``app.question_scope``)."""

import ast
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.abstention import (  # noqa: E402
    ABSTENTION_REASONS,
    Abstention,
    answer_or_abstain,
    prepare_corpus,
    scope_abstention,
    to_abstention_response,
)
from app.clarification import answer_with_clarification  # noqa: E402
from app.generation import MAX_QUESTION_CHARS  # noqa: E402
from app.question_scope import OUT_OF_SCOPE_TOPICS, out_of_scope_topic  # noqa: E402
from app.retrieval import Retriever, load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_PATH = REPO_ROOT / "knowledge" / "pac_answer_eval.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "abstention"

MUST_MATCH = {
    "importes de ayudas": [
        "¿Qué importe de ayuda me corresponde por hectárea?",
        "¿Cuánto voy a cobrar de la PAC?",
        "¿Cuánto se paga por hectárea de olivar?",
    ],
    "elegibilidad individual": [
        "¿Tengo derecho a la ayuda?",
        "¿Cumplo los requisitos para la ayuda al olivar?",
        "¿Qué ayuda de pesca me corresponde?",
    ],
    "notificaciones individuales": [
        "¿Me han enviado ya la notificación de mi expediente de la PAC?",
        "¿Cómo va mi expediente?",
        "¿Ya me han pagado la ayuda?",
    ],
    "reclamaciones y recursos": [
        "¿Cuál es el plazo para presentar una reclamación?",
        "¿Cómo recurro la resolución?",
        "¿Puedo presentar un recurso de alzada?",
    ],
    "penalizaciones por mora": [
        "¿Qué penalización tengo si presento tarde?",
        "¿Qué pasa si presento la solicitud fuera de plazo?",
    ],
    "fuerza mayor": [
        "¿Qué hago si no pude presentar por fuerza mayor?",
        "¿Cuentan las circunstancias excepcionales?",
    ],
    "adaptaciones por controles de monitorización": [
        "¿Cómo adapto la solicitud tras los controles de monitorización?",
        "¿Qué pasa si el satélite detecta otro cultivo?",
    ],
    "otras campañas": [
        "¿Cuál era el plazo de la campaña pasada?",
        "¿Cambia algo para la próxima campaña?",
    ],
}
MATCH_CASES = [
    (omission, question)
    for omission, questions in MUST_MATCH.items()
    for question in questions
]

NEAR_MISSES = [
    "¿Hasta cuándo puedo modificar mi solicitud?",
    "¿Las notificaciones se hacen por medios electrónicos?",
    "¿Puede la Administración corregir un error material en un acto?",
    "¿Qué es un recinto SIGPAC?",
    "¿Qué entidades reconocidas puedo usar?",
    "¿Cuál es el importe ficticio de ejemplo?",
    "¿Cuánto dura el plazo ficticio de prueba?",
    "¿Cuánto cuesta matricular un tractor viejo?",
    "¿Puedo usar el riego de apoyo en la parcela de muestra?",
    "¿Cómo se presenta la solicitud anual de la campaña ficticia?",
    "¿Qué recursos naturales protege la norma?",
]


def eval_document() -> Dict[str, Any]:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))


class ExplodingRetriever(Retriever):
    """A real retriever whose search fails the test if it is ever called."""

    def search(self, question, k=5):  # type: ignore[override]
        raise AssertionError("search must not run for an out-of-scope question")


def fixture_retriever(cls=Retriever) -> Retriever:
    return cls.from_documents(
        load_catalog(FIXTURES / "catalog.json"),
        load_passage_set(FIXTURES / "passages.json"),
        date(2026, 10, 13),
        active_campaign="2026",
    )


@pytest.mark.parametrize("omission,question", MATCH_CASES)
def test_each_omission_category_matches_its_phrasings(omission, question):
    topic = out_of_scope_topic(question)
    assert topic is not None
    assert topic.omission == omission
    expected = "unsafe_request" if omission in (
        "importes de ayudas",
        "elegibilidad individual",
        "notificaciones individuales",
    ) else "no_evidence"
    assert topic.reason == expected
    assert topic.reason in ABSTENTION_REASONS


def test_near_misses_and_reviewed_answered_questions_do_not_match():
    reviewed = [
        case["question"]
        for case in eval_document()["cases"]
        if case.get("expected_status") == "answered"
    ]
    assert len(reviewed) == 11
    for question in reviewed + NEAR_MISSES:
        assert out_of_scope_topic(question) is None, question


def test_guard_is_one_to_one_with_declared_omissions():
    declared = eval_document()["coverage"]["omissions"]
    labels = [topic.omission for topic in OUT_OF_SCOPE_TOPICS]
    assert sorted(labels) == sorted(declared)
    assert len(set(labels)) == len(labels)
    assert all(topic.patterns for topic in OUT_OF_SCOPE_TOPICS)


def test_patterns_are_accent_case_and_punctuation_insensitive():
    for question in (
        "¿QUÉ IMPORTE DE AYUDA ME CORRESPONDE POR HECTÁREA?",
        "que importe de ayuda me corresponde por hectarea",
        "  ¡¿Qué...importe, de ayuda?!  ",
    ):
        topic = out_of_scope_topic(question)
        assert topic is not None and topic.omission == "importes de ayudas"
    assert out_of_scope_topic("") is None
    assert out_of_scope_topic("   ") is None
    assert out_of_scope_topic(None) is None  # type: ignore[arg-type]


def test_scope_abstention_never_calls_search():
    retriever = fixture_retriever(ExplodingRetriever)
    lands = {
        "mode": "all_active",
        "lands": [
            {"id": "land-A", "water_regime": "irrigated"},
            {"id": "land-B", "water_regime": "dryland"},
        ],
    }
    for _omission, question in MATCH_CASES:
        direct = answer_or_abstain(question, retriever, as_of=date(2026, 10, 13))
        assert isinstance(direct, Abstention)
        assert direct.generation_reason == "out_of_scope_question"
        clarified = answer_with_clarification(
            question, lands, retriever, as_of=date(2026, 10, 13)
        )
        assert isinstance(clarified, Abstention)
        assert clarified.reason == direct.reason


def test_stale_corpus_and_invalid_question_win_over_scope():
    question = "¿Qué importe de ayuda me corresponde por hectárea?"
    stale = Abstention(reason="stale_evidence")
    assert answer_or_abstain(question, stale, as_of=date(2026, 10, 13)) is stale
    retriever = fixture_retriever(ExplodingRetriever)
    blank = answer_or_abstain("   ", retriever, as_of=date(2026, 10, 13))
    assert blank.reason == "invalid_question"
    long_question = question + " x" * MAX_QUESTION_CHARS
    too_long = answer_or_abstain(long_question, retriever, as_of=date(2026, 10, 13))
    assert too_long.reason == "invalid_question"
    assert scope_abstention("   ") is None
    assert scope_abstention(long_question) is None
    assert scope_abstention(123) is None  # type: ignore[arg-type]


def test_guard_issue_carries_omission_label_not_question_text():
    question = "¿Cómo va mi expediente? Soy Pepe Pérez"
    abstention = scope_abstention(question)
    assert abstention is not None
    assert len(abstention.issues) == 1
    issue = abstention.issues[0]
    assert issue.code == "out_of_scope_question"
    assert issue.detail == "notificaciones individuales"
    assert "Pepe" not in repr(abstention)
    payload = to_abstention_response(abstention)
    assert payload["status"] == "abstained"
    assert payload["sources"] == []
    assert not any(character.isdigit() for character in payload["answer"])


def test_reviewed_regressions_abstain_through_ask():
    from fastapi.testclient import TestClient

    from app.ask_api import (
        get_active_campaign,
        get_as_of_date,
        get_corpus_documents,
        load_corpus_documents,
    )
    from app.main import app

    documents = load_corpus_documents(
        REPO_ROOT / "knowledge" / "source_catalog.json",
        REPO_ROOT / "knowledge" / "passages.json",
    )
    app.dependency_overrides[get_as_of_date] = lambda: date(2026, 11, 7)
    app.dependency_overrides[get_active_campaign] = lambda: "2026"
    app.dependency_overrides[get_corpus_documents] = lambda: documents
    try:
        client = TestClient(app)
        for question in (
            "¿Qué importe de ayuda me corresponde por hectárea?",
            "¿Cuál es el plazo para presentar una reclamación?",
        ):
            response = client.post(
                "/ask",
                json={"question": question, "land_context": {"mode": "general", "lands": []}},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "abstained"
            assert body["sources"] == []
    finally:
        app.dependency_overrides.clear()


def test_guard_module_is_standard_library_only():
    source = (BACKEND_ROOT / "app" / "question_scope.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names) | {"app"}
    assert "app.procedure_map" not in source and "source_validity" not in source
