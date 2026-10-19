#!/usr/bin/env python3
"""Check that coverage model keys resolve to reviewed, safe rendered Spanish copy."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XML = ROOT / "shared/src/commonMain/composeResources/values/strings.xml"
CONTENT = ROOT / "shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageContent.kt"
SCREEN = ROOT / "shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageScreen.kt"
DISPLAY_SOURCES = (
    SCREEN,
    ROOT / "shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt",
    ROOT / "shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt",
)

# Independently reviewed expectation based on the four current official sources and their
# seeded passages; intentionally not imported from the production model.
EXPECTED_TOPICS = {
    "coverage_topic_application", "coverage_topic_sigpac", "coverage_topic_olive_aid",
    "coverage_topic_procedure", "coverage_topic_notifications",
}
EXPECTED_NOT_YET = {
    "producción ecológica", "riego y agua", "condicionalidad en detalle",
    "cuaderno digital", "seguros agrarios", "quema de restos de poda",
}
FORBIDDEN = re.compile(r"\d|garantizad[oa]|\bseguro\b|\bcorrect[oa]\b", re.I)


def require_rendered_coverage_strings(rendered, strings):
    missing = {key for key in rendered if key.startswith("coverage_")} - strings.keys()
    assert not missing, f"rendered coverage strings missing from strings.xml: {sorted(missing)}"


# Regression guard: a rendered key absent from the resource table must fail, not vanish
# when the defined-key filter is applied later.
try:
    require_rendered_coverage_strings({"coverage_regression_missing"}, {})
except AssertionError:
    pass
else:
    raise AssertionError("missing rendered coverage key regression check did not fail")

xml = ET.parse(XML).getroot()
strings = {node.attrib["name"]: "".join(node.itertext()).strip() for node in xml.findall("string")}
content = CONTENT.read_text()
source_text = "\n".join(path.read_text() for path in DISPLAY_SOURCES)
covered = set(re.findall(r'"(coverage_topic_[a-z_]+)"', content))
assert covered == EXPECTED_TOPICS, f"covered model differs from reviewed corpus: {covered ^ EXPECTED_TOPICS}"
not_yet_key = "coverage_not_yet_topics"
assert not_yet_key in content, "not-yet topics absent from the content model"
assert not_yet_key in SCREEN.read_text(), "not-yet topics are not rendered by CoverageScreen"

modeled = covered | {not_yet_key} | set(re.findall(r'"(coverage_no_[a-z_]+)"', content))
rendered = set(re.findall(r'Res\.string\.([a-z][a-z0-9_]*)', source_text))
# Validate resource resolution before intersecting with the defined-key set. If this
# happens after intersection, a missing rendered key silently disappears from the audit.
require_rendered_coverage_strings(rendered, strings)
# Check only copy introduced by this feature, plus the existing shared back label used
# by the new screen. This intentionally excludes unrelated app/privacy strings.
feature_copy = {key for key in strings if key.startswith("coverage_")} | {"privacy_back"}
displayed_feature_copy = rendered & feature_copy
assert displayed_feature_copy == feature_copy, (
    f"feature copy must be displayed and checked; missing references: {feature_copy - rendered}"
)
assert modeled <= rendered, f"modeled keys not rendered: {modeled - rendered}"
for key in displayed_feature_copy:
    assert key in strings and strings[key], f"missing displayed string {key}"
    assert not FORBIDDEN.search(strings[key]), f"unsafe promise/legal fact in {key}: {strings[key]}"
copy = strings[not_yet_key].lower()
assert all(topic in copy for topic in EXPECTED_NOT_YET), "not-yet copy omits a documented uncovered topic"
print(f"coverage copy validated: {len(displayed_feature_copy)} displayed feature resource keys")
