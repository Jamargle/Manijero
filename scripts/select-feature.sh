#!/usr/bin/env bash
set -euo pipefail

# Feature selector over the lean index (feature_list.json), so an agent does not
# have to read and interpret the whole file. `--next` prints the next
# dependency-ready feature and its next role; `--status` prints the board
# summary plus one line per unfinished feature. A feature is dependency-ready
# only when it is not `blocked` and every `depends_on` id is `accepted`.
#
# Read-only: it runs before any Android/Gradle setup and needs no SDK, JDK, or
# local.properties.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# Prints the interpreter used to run the selector.
python_bin() {
  if [[ -n "${MANIJERO_PYTHON:-}" ]]; then
    printf '%s\n' "$MANIJERO_PYTHON"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' python
    return 0
  fi
  return 1
}

usage() {
  cat <<'EOF'
Usage: ./scripts/select-feature.sh [--next|--status]

  --next    Print the next dependency-ready feature id and its next role (default)
  --status  Print the feature status board and unfinished-feature readiness
  --help    Show this help
EOF
}

mode="${1:---next}"
case "$mode" in
  --help|-h)
    usage
    exit 0
    ;;
  --next|--status) ;;
  *)
    usage >&2
    exit 2
    ;;
esac

if ! py="$(python_bin)"; then
  printf 'Feature selection needs Python 3; install it or set MANIJERO_PYTHON.\n' >&2
  exit 1
fi

REPO_ROOT="$REPO_ROOT" "$py" - "$mode" <<'PY'
import json
import os
import sys


def main():
    mode = sys.argv[1]
    root = os.environ.get("REPO_ROOT", ".")
    index_path = os.path.join(root, "feature_list.json")
    try:
        with open(index_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        sys.stderr.write("feature_list.json not found at %s\n" % index_path)
        return 2
    except json.JSONDecodeError as error:
        sys.stderr.write("feature_list.json is not valid JSON: %s\n" % error)
        return 2

    features = data.get("features", [])
    status = {feature["id"]: feature.get("status", "not_started") for feature in features}

    def unmet(feature):
        return [dep for dep in (feature.get("depends_on") or []) if status.get(dep) != "accepted"]

    def ready(feature):
        return feature.get("status") != "blocked" and not unmet(feature)

    def spec_path(feature):
        return feature.get("spec") or "docs/specs/%s.md" % feature["id"]

    def validation_path(feature):
        return feature.get("validation") or "docs/validations/%s.md" % feature["id"]

    def has_spec(feature):
        return os.path.isfile(os.path.join(root, spec_path(feature)))

    def role(feature):
        state = feature.get("status")
        if state == "blocked":
            return "blocked"
        if state == "passing":
            return "validator"
        if not has_spec(feature):
            return "planner"
        return "implementer"

    open_features = [f for f in features if f.get("status") != "accepted"]
    selectable = [f for f in open_features if f.get("status") != "blocked"]

    def select():
        for feature in selectable:
            if feature.get("status") == "in_progress":
                return feature
        for feature in selectable:
            if feature.get("status") == "passing":
                return feature
        for feature in selectable:
            if ready(feature) and has_spec(feature):
                return feature
        for feature in selectable:
            if ready(feature) and not has_spec(feature):
                return feature
        return None

    def blockers():
        listed = []
        for feature in open_features:
            missing = unmet(feature)
            if feature.get("status") == "blocked":
                listed.append("%s(blocked)" % feature["id"])
            elif missing:
                listed.append("%s(%s)" % (feature["id"], ",".join(missing)))
        return listed

    selected = select()

    if mode == "--next":
        if selected is None:
            print("NEXT_FEATURE=")
            print("NEXT_ROLE=none")
            print("NEXT_STATUS=")
            if open_features:
                print("NEXT_REASON=no dependency-ready unfinished feature")
                print("NEXT_BLOCKED=%s" % ";".join(blockers()))
            else:
                print("NEXT_REASON=all features accepted")
                print("NEXT_BLOCKED=")
            return 0
        print("NEXT_FEATURE=%s" % selected["id"])
        print("NEXT_ROLE=%s" % role(selected))
        print("NEXT_STATUS=%s" % selected.get("status", "not_started"))
        print("NEXT_SPEC=%s" % (spec_path(selected) if has_spec(selected) else "-"))
        print("NEXT_VALIDATION=%s" % validation_path(selected))
        return 0

    counts = {}
    for feature in features:
        state = feature.get("status", "not_started")
        counts[state] = counts.get(state, 0) + 1
    order = ["accepted", "in_progress", "passing", "not_started", "blocked"]
    summary = " ".join("%s=%d" % (name, counts.get(name, 0)) for name in order)
    for name in sorted(set(counts) - set(order)):
        summary += " %s=%d" % (name, counts[name])
    print("SUMMARY total=%d %s open=%d" % (len(features), summary, len(open_features)))
    print("NEXT_FEATURE=%s" % (selected["id"] if selected else ""))
    print("NEXT_ROLE=%s" % (role(selected) if selected else "none"))
    for feature in open_features:
        print("FEATURE id=%s status=%s ready=%s unmet=%s role=%s spec=%s" % (
            feature["id"],
            feature.get("status", "not_started"),
            "yes" if ready(feature) else "no",
            ",".join(unmet(feature)) or "-",
            role(feature),
            "yes" if has_spec(feature) else "no",
        ))
    return 0


sys.exit(main())
PY
