"""Static checks of the committed health dashboard: pins, thresholds, rules, panels, privacy.

No Docker, network, or Prometheus is needed; every file is JSON (valid YAML), read with ``json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app import local_monitoring as monitoring
from app.health_metrics import LABEL_NAMES

ROOT = Path(__file__).resolve().parents[1] / "monitoring"
FILES = [
    "images.json",
    "thresholds.json",
    "prometheus/rules.json",
    "grafana/provisioning/datasources/manijero.yaml",
    "grafana/provisioning/dashboards/manijero.yaml",
    "grafana/dashboards/manijero-health.json",
]
DENYLIST = ("question", "answer_text", "land", "client_id", "token", "notes", "name=", "passage")
FUNCTIONS = {
    "sum", "max", "min", "increase", "histogram_quantile", "min_over_time", "absent", "by", "on",
    "and", "or", "unless",
}
LABEL_WORDS = {"env", "le", "route", "code", "status"}
CHECKS = ("service", "speed", "errors", "abstentions")


def load(name: str) -> Any:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def rules() -> Dict[str, str]:
    return {rule["record"]: rule["expr"] for group in load("prometheus/rules.json")["groups"] for rule in group["rules"]}


def panels() -> List[Dict[str, Any]]:
    return [panel for panel in load("grafana/dashboards/manijero-health.json")["panels"] if panel["type"] == "stat"]


def mapping_texts(panel: Dict[str, Any]) -> Dict[str, str]:
    values = panel["fieldConfig"]["defaults"]["mappings"][0]["options"]
    return {code: entry["text"] for code, entry in values.items()}


@pytest.mark.parametrize("name", FILES)
def test_every_committed_file_parses(name: str) -> None:
    assert load(name)


def test_image_pins_are_reviewed_explicit_versions_and_digests_are_valid_when_present() -> None:
    pins = monitoring.load_pins(ROOT / "images.json")

    for pin in (pins.grafana, pins.prometheus):
        assert re.fullmatch(r"^[a-z0-9./-]+:[A-Za-z0-9._-]+$", pin.image)
        assert not pin.image.endswith(":latest")
        if pin.digest is not None:
            assert re.fullmatch(r"sha256:[0-9a-f]{64}", pin.digest)
            assert pin.reference == "{}@{}".format(pin.image, pin.digest)


def test_image_pins_carry_digests() -> None:
    pins = monitoring.load_pins(ROOT / "images.json")
    if any(pin.digest is None for pin in (pins.grafana, pins.prometheus)):
        pytest.skip("digests are pending: the pins use explicit version tags until a developer reads them")
    assert all("@sha256:" in pin.reference for pin in (pins.grafana, pins.prometheus))


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"grafana": {"image": "grafana/grafana-oss:latest", "digest": None, "reviewed_on": "2026-11-02", "reason": "x"},
         "prometheus": {"image": "prom/prometheus:v3.4.0", "digest": None, "reviewed_on": "2026-11-02", "reason": "x"}},
        {"grafana": {"image": "grafana/grafana-oss:12.0.0", "digest": "sha256:abc", "reviewed_on": "2026-11-02", "reason": "x"},
         "prometheus": {"image": "prom/prometheus:v3.4.0", "digest": None, "reviewed_on": "2026-11-02", "reason": "x"}},
    ],
)
def test_invalid_pins_are_refused(tmp_path: Path, document: Dict[str, Any]) -> None:
    path = tmp_path / "images.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(Exception) as error:
        monitoring.load_pins(path)

    assert "pins" in str(error.value)


def test_rule_bounds_match_the_thresholds_file() -> None:
    thresholds, expressions = load("thresholds.json"), rules()
    speed, errors, abstentions = thresholds["speed"], thresholds["errors"], thresholds["abstentions"]

    assert "0.9" in expressions["manijero:ask_p90_seconds_15m"] and speed["quantile"] == 0.9
    status_speed = expressions["manijero:status_speed"]
    assert "< {}".format(speed["warning_seconds"]) in status_speed
    assert ">= {}) < {}".format(speed["warning_seconds"], speed["problem_seconds"]) in status_speed
    assert ">= {})".format(speed["problem_seconds"]) in status_speed
    status_errors = expressions["manijero:status_errors"]
    assert "< {})".format(errors["warning_percent"]) in status_errors
    assert ">= {}) < {}".format(errors["warning_percent"], errors["problem_percent"]) in status_errors
    assert ">= {})".format(errors["problem_percent"]) in status_errors
    status_abstentions = expressions["manijero:status_abstentions"]
    assert "< {})".format(abstentions["warning_percent"]) in status_abstentions
    assert ">= {}) < {}".format(abstentions["warning_percent"], abstentions["problem_percent"]) in status_abstentions
    assert ">= {})".format(abstentions["problem_percent"]) in status_abstentions
    assert "manijero:answers_1h >= {}".format(abstentions["minimum_answers"]) in expressions["manijero:abstention_percent_1h"]
    for name, window in (("manijero:ask_requests_15m", speed["window"]), ("manijero:answers_1h", abstentions["window"])):
        assert "[{}]".format(window) in expressions[name]
    assert "[{}]".format(thresholds["service"]["window"]) in expressions["manijero:status_service"]


def test_every_rule_reads_only_manijero_series_and_up() -> None:
    for record, expression in rules().items():
        bare = re.sub(r'"[^"]*"', '""', expression)
        bare = re.sub(r"\[[^\]]*\]", "", bare)
        for word in re.findall(r"[A-Za-z_:][A-Za-z0-9_:]*", bare):
            if word in FUNCTIONS or word in LABEL_WORDS:
                continue
            assert word == "up" or word.startswith(("manijero_", "manijero:")), (record, word)


def test_every_label_a_rule_or_panel_uses_is_allowlisted_or_scrape_added() -> None:
    allowed = set(LABEL_NAMES) | {"env", "job", "instance", "le"}
    texts = list(rules().values()) + [target["expr"] for panel in panels() for target in panel["targets"]]
    for text in texts:
        for label in re.findall(r"(?:by \(|[{,])\s*([a-z_]+)\s*(?:=|=~|,|\))", text):
            assert label in allowed, (label, text)
    assert allowed <= set(monitoring.KEPT_LABELS)
    assert set(LABEL_NAMES) <= set(monitoring.KEPT_LABELS)


def test_panels_target_only_status_rules_for_local_and_qa() -> None:
    found = {}
    for panel in panels():
        (target,) = panel["targets"]
        match = re.fullmatch(r'(manijero:status_[a-z]+)\{env="(local|qa)"\}', target["expr"])
        assert match, target["expr"]
        assert match.group(1) in rules()
        found[(match.group(1), match.group(2))] = panel
    assert set(found) == {
        ("manijero:status_" + check, env) for check in CHECKS for env in ("local", "qa")
    }


def test_every_state_has_a_state_word_a_meaning_and_a_first_step() -> None:
    codes = {"service": {0, 1, 2, 3, 4}, "speed": {-1, 0, 1, 2, 4}, "errors": {-1, 0, 1, 2, 4}, "abstentions": {-1, 0, 1, 2, 4}}
    words = {"-1": "Not enough data.", "0": "OK.", "1": "Warning.", "2": "Problem.", "3": "Problem.", "4": "Not set up yet."}
    for panel in panels():
        check = re.search(r"status_([a-z]+)", panel["targets"][0]["expr"]).group(1)  # type: ignore[union-attr]
        texts = mapping_texts(panel)
        assert {int(code) for code in texts} == codes[check], panel["title"]
        for code, text in texts.items():
            assert text.startswith(words[code]), (panel["title"], code)
            assert len(text.split()) >= 6
            if code in ("1", "2", "3"):
                assert "First thing to do:" in text, (panel["title"], code)
            if code == "0":
                assert "Nothing to do." in text
        special = panel["fieldConfig"]["defaults"]["mappings"][1]
        assert special["type"] == "special" and "No information yet." in special["options"]["result"]["text"]
        assert monitoring.STATUS_COMMAND in special["options"]["result"]["text"]


def test_panel_texts_state_the_thresholds_file_numbers() -> None:
    thresholds = load("thresholds.json")
    by_title = {panel["title"]: mapping_texts(panel) for panel in panels()}
    speed, errors, abstentions = thresholds["speed"], thresholds["errors"], thresholds["abstentions"]

    assert "less than {} seconds".format(speed["warning_seconds"]) in by_title["Local: Answer speed"]["0"]
    assert "{} seconds or more".format(speed["problem_seconds"]) in by_title["Local: Answer speed"]["2"]
    assert "fewer than {} in 100".format(errors["warning_percent"]) in by_title["Local: Error rate"]["0"]
    assert "{} or more in 100".format(errors["problem_percent"]) in by_title["Local: Error rate"]["2"]
    assert "Fewer than {} in 100".format(abstentions["warning_percent"]) in by_title["Local: Abstention rate"]["0"]
    assert "{} or more in 100".format(abstentions["problem_percent"]) in by_title["Local: Abstention rate"]["2"]
    assert "Fewer than {} answers".format(abstentions["minimum_answers"]) in by_title["Local: Abstention rate"]["-1"]
    assert "outside the covered topics" in by_title["Local: Abstention rate"]["2"]
    assert "Nothing to do until the QA service is deployed." in by_title["QA: Service"]["4"]


def test_denylist_finds_nothing_in_expressions_labels_or_provisioning() -> None:
    texts = list(rules().values())
    texts += [target["expr"] for panel in panels() for target in panel["targets"]]
    texts += [json.dumps(load(name)) for name in FILES if name.startswith("grafana/provisioning")]
    texts += sorted(monitoring.KEPT_LABELS)
    texts += [json.dumps(monitoring.prometheus_config(8000, None))]
    for text in texts:
        for word in DENYLIST:
            assert word not in text.lower(), (word, text)


def test_grafana_runs_anonymous_viewer_with_every_extra_off() -> None:
    settings = dict(monitoring.GRAFANA_SETTINGS)

    assert settings["GF_AUTH_ANONYMOUS_ENABLED"] == "true"
    assert settings["GF_AUTH_ANONYMOUS_ORG_ROLE"] == "Viewer"
    assert settings["GF_AUTH_DISABLE_LOGIN_FORM"] == "true"
    for key in (
        "GF_EXPLORE_ENABLED", "GF_ANALYTICS_REPORTING_ENABLED", "GF_ANALYTICS_CHECK_FOR_UPDATES",
        "GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES", "GF_PLUGINS_PLUGIN_ADMIN_ENABLED", "GF_USERS_ALLOW_SIGN_UP",
        "GF_ALERTING_ENABLED", "GF_UNIFIED_ALERTING_ENABLED",
    ):
        assert settings[key] == "false", key
    assert settings["GF_PLUGINS_PREINSTALL_DISABLED"] == "true"
    assert monitoring.ADMIN_PASSWORD_KEY not in settings


def test_provisioning_points_at_the_pinned_prometheus_name_and_forbids_editing() -> None:
    source = load("grafana/provisioning/datasources/manijero.yaml")["datasources"][0]
    provider = load("grafana/provisioning/dashboards/manijero.yaml")["providers"][0]
    dashboard = load("grafana/dashboards/manijero-health.json")

    assert source["url"] == "http://{}:{}".format(monitoring.PROMETHEUS, monitoring.PROMETHEUS_PORT)
    assert source["editable"] is False
    assert provider["allowUiUpdates"] is False
    assert dashboard["editable"] is False
    assert all(panel["datasource"]["uid"] == source["uid"] for panel in panels())
