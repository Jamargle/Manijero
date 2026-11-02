"""Environment profiles: QA setup, access keys, the settings reader, and the status lines.

Offline: every home is a temporary directory, the prompter and output are fakes, and a socket
guard fails any network use. Tokens are random per test and never asserted by value except to
prove they never appear in output or in the clients file.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from app import environment_profiles as ep
from app import local_rag_bootstrap as lrb
from app.pilot_config import load_clients_file, token_sha256

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network use is not allowed")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


class FakePrompter:
    def __init__(self) -> None:
        self.answers: List[Optional[str]] = []
        self.questions: List[str] = []

    def ask(self, question: str) -> Optional[str]:
        self.questions.append(question)
        return self.answers.pop(0) if self.answers else None


class Rig:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.local = tmp_path / "manijero" / "local"
        self.qa = tmp_path / "manijero" / "qa"
        self.lines: List[str] = []
        self.prompter = FakePrompter()

    def ports(self, tty: bool = True) -> ep.Ports:
        return ep.Ports(out=self.lines.append, prompter=self.prompter, tty=tty)

    @property
    def output(self) -> str:
        return "\n".join(self.lines)

    def status(self) -> int:
        self.lines.clear()
        return ep.run_status(self.ports(), local=self.local, qa=self.qa)

    def qa_setup(self, *answers: Optional[str], tty: bool = True) -> int:
        self.lines.clear()
        self.prompter.answers = list(answers)
        return ep.run_qa_setup(self.ports(tty), qa=self.qa, local=self.local)

    def make_local_ready(self, with_keys: bool = True, with_lines: bool = True) -> None:
        paths = lrb.local_paths(self.local)
        self.local.mkdir(parents=True)
        text = lrb.SETTINGS_TEMPLATE if with_lines else "MANIJERO_ACTIVE_CAMPAIGN=2026\n"
        paths.settings.write_text(text, encoding="utf-8")
        release = paths.releases / "releases" / "0123456789abcdef"
        release.mkdir(parents=True)
        (paths.releases / "current").symlink_to(Path("releases") / release.name)
        if with_keys:
            ep.ensure_local_credentials(self.local)

    @property
    def token_path(self) -> Path:
        return ep.credential_paths(self.qa, ep.QA_CLIENT_ID).token

    @property
    def clients_path(self) -> Path:
        return ep.credential_paths(self.qa, ep.QA_CLIENT_ID).clients


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def snapshot(root: Path) -> Dict[str, tuple]:
    entries: Dict[str, tuple] = {}
    if not root.exists():
        return entries
    for current, directories, names in os.walk(root):
        for name in directories + names:
            path = Path(current) / name
            data = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else ""
            entries[str(path.relative_to(root))] = (data, mode(path) if not path.is_symlink() else 0, path.lstat().st_mtime_ns)
    return entries


# --- Template ------------------------------------------------------------------------------


def test_template_has_only_allowlisted_keys_placeholder_host_and_no_secret() -> None:
    text = ep.TEMPLATE_PATH.read_text(encoding="utf-8")
    keys = [line.split("=", 1)[0] for line in text.splitlines() if line and not line.startswith("#")]

    assert sorted(keys) == sorted(ep.QA_KEYS)
    assert "MANIJERO_ENVIRONMENT=qa" in text and "MANIJERO_DEPLOYMENT_PROFILE=pilot" in text
    assert "https://qa.manijero.invalid" in text
    assert "token_sha256" not in text
    assert not any(len(word) >= 32 and word.isalnum() for word in text.replace("=", " ").split())
    assert all(".invalid" in line or "http" not in line for line in text.splitlines())


# --- QA setup ------------------------------------------------------------------------------


def test_qa_setup_creates_settings_keys_and_release_folder(rig: Rig) -> None:
    assert rig.qa_setup() == 0, rig.output

    assert mode(rig.qa / "settings.env") == 0o644
    assert mode(rig.qa / "credentials") == 0o700
    assert mode(rig.token_path) == 0o600 and mode(rig.clients_path) == 0o600
    assert (rig.qa / "knowledge-releases").is_dir() and not list((rig.qa / "knowledge-releases").iterdir())
    token = rig.token_path.read_text(encoding="utf-8")
    assert len(token) >= 32
    document = json.loads(rig.clients_path.read_text(encoding="utf-8"))
    assert document["clients"] == [
        {"client_id": "qa-test-device", "token_sha256": token_sha256(token), "requests_per_minute": 20, "enabled": True}
    ]
    assert load_clients_file(rig.clients_path)
    assert token not in rig.output and token_sha256(token) not in rig.output
    for path in rig.qa.rglob("*"):
        if path.is_file() and path != rig.token_path:
            assert token not in path.read_text(encoding="utf-8")
    assert "placeholder" in rig.output and "No server was contacted" in rig.output
    assert rig.lines[-1] == "Result: QA is prepared on this computer. Nothing was deployed."
    settings = ep.read_profile_settings("qa", rig.qa)
    assert settings.deployment_profile == "pilot" and settings.environment == "qa"
    assert settings.clients_file == rig.clients_path and settings.release_root == rig.qa / "knowledge-releases"
    assert settings.placeholder_url


def test_qa_setup_rerun_changes_nothing(rig: Rig) -> None:
    assert rig.qa_setup() == 0
    before = snapshot(rig.qa)

    assert rig.qa_setup() == 0

    assert snapshot(rig.qa) == before
    assert rig.lines[-1] == "Result: QA was already prepared; nothing was changed."
    assert rig.lines[0].startswith("OK  QA:")
    assert not rig.prompter.questions


def _break_missing_token(rig: Rig) -> None:
    rig.token_path.unlink()


def _break_missing_clients(rig: Rig) -> None:
    rig.clients_path.unlink()


def _break_open_token(rig: Rig) -> None:
    os.chmod(rig.token_path, 0o644)


def _break_digest(rig: Rig) -> None:
    rig.token_path.write_text("x" * 48, encoding="utf-8")


INCONSISTENT = [_break_missing_token, _break_missing_clients, _break_open_token, _break_digest]


@pytest.mark.parametrize("break_it", INCONSISTENT, ids=lambda fn: fn.__name__)
def test_incomplete_keys_without_a_terminal_change_nothing(rig: Rig, break_it) -> None:
    rig.qa_setup()
    break_it(rig)
    before = snapshot(rig.qa)

    assert rig.qa_setup(tty=False) == 1

    assert snapshot(rig.qa) == before
    assert "incomplete" in rig.output and "Terminal window" in rig.output
    assert rig.status() == 1 and "PROBLEM  QA" in rig.output


@pytest.mark.parametrize("break_it", INCONSISTENT, ids=lambda fn: fn.__name__)
def test_incomplete_keys_declined_change_nothing(rig: Rig, break_it) -> None:
    rig.qa_setup()
    break_it(rig)
    before = snapshot(rig.qa)

    assert rig.qa_setup("no") == 1

    assert snapshot(rig.qa) == before
    assert rig.prompter.questions == [ep.RECOVERY_QUESTION]


@pytest.mark.parametrize("break_it", INCONSISTENT, ids=lambda fn: fn.__name__)
def test_incomplete_keys_recover_on_yes_and_the_old_digest_is_gone(rig: Rig, break_it) -> None:
    rig.qa_setup()
    old_clients = rig.clients_path.read_text(encoding="utf-8")
    old_digest = json.loads(old_clients)["clients"][0]["token_sha256"]
    break_it(rig)

    assert rig.qa_setup("yes") == 0, rig.output

    assert rig.lines[-1] == "Result: new QA access keys were made. Nothing was deployed."
    assert ep.check_credentials(ep.credential_paths(rig.qa, ep.QA_CLIENT_ID), ep.QA_CLIENT_ID) is None
    assert old_digest not in rig.clients_path.read_text(encoding="utf-8")
    assert mode(rig.token_path) == 0o600 and mode(rig.clients_path) == 0o600
    assert rig.token_path.read_text(encoding="utf-8") not in rig.output
    assert rig.qa_setup() == 0 and rig.lines[-1].endswith("nothing was changed.")


def test_homes_inside_the_checkout_are_refused_before_any_write(rig: Rig) -> None:
    inside = REPO_ROOT / "build" / "qa-home-should-not-exist"
    rig.qa = inside

    assert rig.qa_setup() == 1

    assert not inside.exists()
    assert "inside the Manijero folder" in rig.output

    rig.qa = rig.tmp / "qa"
    rig.local = REPO_ROOT / "build" / "local-home-should-not-exist"
    assert rig.qa_setup() == 1 and not rig.qa.exists()


def test_a_qa_settings_file_that_is_refused_blocks_setup(rig: Rig) -> None:
    rig.qa.mkdir(parents=True)
    (rig.qa / "settings.env").write_text("MANIJERO_ACTIVE_CAMPAIGN=2026\n", encoding="utf-8")
    before = snapshot(rig.qa)

    assert rig.qa_setup() == 1

    assert snapshot(rig.qa) == before
    assert "never treated as local" in rig.output


# --- The settings reader -------------------------------------------------------------------


def write_qa(rig: Rig, **overrides: Optional[str]) -> Path:
    values: Dict[str, Optional[str]] = {
        "MANIJERO_ENVIRONMENT": "qa",
        "MANIJERO_DEPLOYMENT_PROFILE": "pilot",
        "MANIJERO_ACTIVE_CAMPAIGN": "2026",
        "MANIJERO_PUBLIC_URL": "https://qa.manijero.invalid",
        "MANIJERO_PILOT_CLIENTS_FILE": str(rig.qa / "credentials" / "pilot-clients.json"),
        "MANIJERO_KNOWLEDGE_RELEASE_ROOT": str(rig.qa / "knowledge-releases"),
    }
    values.update(overrides)
    rig.qa.mkdir(parents=True, exist_ok=True)
    path = rig.qa / "settings.env"
    path.write_text("".join("{}={}\n".format(k, v) for k, v in values.items() if v is not None), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "overrides, code, fragment",
    [
        ({"MANIJERO_ENVIRONMENT": None}, "key_missing", "MANIJERO_ENVIRONMENT=qa"),
        ({"MANIJERO_DEPLOYMENT_PROFILE": None}, "key_missing", "MANIJERO_DEPLOYMENT_PROFILE=pilot"),
        ({"MANIJERO_ENVIRONMENT": "local"}, "environment_mismatch", "line 1"),
        ({"MANIJERO_DEPLOYMENT_PROFILE": "development"}, "profile_mismatch", "MANIJERO_DEPLOYMENT_PROFILE=pilot"),
        ({"MANIJERO_ACTIVE_CAMPAIGN": "26"}, "line_invalid", "four-digit"),
        ({"MANIJERO_PUBLIC_URL": "http://qa.example.invalid"}, "url_invalid", "https://"),
        ({"MANIJERO_PILOT_CLIENTS_FILE": "credentials/pilot-clients.json"}, "path_relative", "line 5"),
        ({"MANIJERO_KNOWLEDGE_RELEASE_ROOT": str(REPO_ROOT / "knowledge-releases")}, "path_in_checkout", "outside"),
        ({"MANIJERO_OTHER": "1"}, "key_unknown", "not a setting"),
    ],
)
def test_a_qa_file_that_does_not_say_it_is_non_local_is_refused(rig: Rig, overrides, code, fragment) -> None:
    path = write_qa(rig, **overrides)

    with pytest.raises(ep.ProfileSettingsError) as caught:
        ep.read_profile_settings("qa", rig.qa)

    assert caught.value.code == code
    assert str(path) in caught.value.sentence and fragment in caught.value.sentence
    assert "never treated as local" in caught.value.sentence or code not in ("key_missing", "environment_mismatch", "profile_mismatch")


def test_the_profile_sentence_matches_the_spec_wording(rig: Rig) -> None:
    write_qa(rig, MANIJERO_DEPLOYMENT_PROFILE="development")

    with pytest.raises(ep.ProfileSettingsError) as caught:
        ep.read_profile_settings("qa", rig.qa)

    assert "this file is for QA, so it must say MANIJERO_DEPLOYMENT_PROFILE=pilot; it is never treated as local" in caught.value.sentence
    assert "line 2" in caught.value.sentence


def test_a_repeated_key_is_refused(rig: Rig) -> None:
    path = write_qa(rig)
    path.write_text(path.read_text(encoding="utf-8") + "MANIJERO_ACTIVE_CAMPAIGN=2027\n", encoding="utf-8")

    with pytest.raises(ep.ProfileSettingsError) as caught:
        ep.read_profile_settings("qa", rig.qa)

    assert caught.value.code == "key_repeated" and "line 7" in caught.value.sentence


def test_a_qa_release_root_that_touches_the_local_one_is_refused(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(lrb.LOCAL_HOME_ENV, str(rig.local))
    local_releases = lrb.local_paths(rig.local).releases
    for root in (local_releases, local_releases / "inner", rig.local):
        write_qa(rig, MANIJERO_KNOWLEDGE_RELEASE_ROOT=str(root))
        with pytest.raises(ep.ProfileSettingsError) as caught:
            ep.read_profile_settings("qa", rig.qa)
        assert caught.value.code == "release_root_overlaps_local"


def test_a_missing_qa_file_is_refused_and_never_defaulted(rig: Rig) -> None:
    with pytest.raises(ep.ProfileSettingsError) as caught:
        ep.read_profile_settings("qa", rig.qa)

    assert caught.value.code == "settings_missing" and "--qa-settings-setup" in caught.value.sentence


def test_prod_is_never_readable(rig: Rig) -> None:
    (rig.tmp / "manijero" / "prod").mkdir(parents=True)
    (rig.tmp / "manijero" / "prod" / "settings.env").write_text("MANIJERO_ENVIRONMENT=prod\n", encoding="utf-8")

    with pytest.raises(ep.ProfileSettingsError) as caught:
        ep.read_profile_settings("prod")

    assert caught.value.code == "prod_not_configured"


def test_local_settings_need_both_lines_and_keep_local_values(rig: Rig) -> None:
    rig.make_local_ready(with_lines=False)
    with pytest.raises(ep.ProfileSettingsError) as caught:
        ep.read_profile_settings("local", rig.local)
    assert caught.value.code == "key_missing"

    lrb.append_environment_lines(lrb.local_paths(rig.local).settings)
    settings = ep.read_profile_settings("local", rig.local)
    assert (settings.environment, settings.deployment_profile) == ("local", "development")
    assert settings.release_root == lrb.local_paths(rig.local).releases


# --- Local credentials ---------------------------------------------------------------------


def test_local_credentials_are_created_with_modes_and_left_alone_on_rerun(rig: Rig, capsys) -> None:
    first = ep.ensure_local_credentials(rig.local)

    paths = ep.credential_paths(rig.local, ep.LOCAL_CLIENT_ID)
    assert first.created
    assert mode(paths.directory) == 0o700 and mode(paths.token) == 0o600 and mode(paths.clients) == 0o600
    assert len(paths.token.read_text(encoding="utf-8")) >= 32
    document = json.loads(paths.clients.read_text(encoding="utf-8"))
    assert [c["client_id"] for c in document["clients"]] == ["local-test-device"]
    assert document["clients"][0]["requests_per_minute"] == 20
    before = snapshot(rig.local)

    second = ep.ensure_local_credentials(rig.local)

    assert not second.created and not second.tightened
    assert snapshot(rig.local) == before


def test_an_existing_local_token_is_kept_while_the_clients_file_is_rebuilt(rig: Rig) -> None:
    ep.ensure_local_credentials(rig.local)
    paths = ep.credential_paths(rig.local, ep.LOCAL_CLIENT_ID)
    token_bytes = paths.token.read_bytes()
    for damage in (lambda: paths.clients.unlink(), lambda: paths.clients.write_text("not json", encoding="utf-8")):
        damage()
        done = ep.ensure_local_credentials(rig.local)
        assert done.created
        assert paths.token.read_bytes() == token_bytes
        assert ep.check_credentials(paths, ep.LOCAL_CLIENT_ID) is None
        assert mode(paths.clients) == 0o600


def test_a_mismatched_local_clients_file_is_rebuilt_from_the_existing_token(rig: Rig) -> None:
    ep.ensure_local_credentials(rig.local)
    paths = ep.credential_paths(rig.local, ep.LOCAL_CLIENT_ID)
    token_bytes = paths.token.read_bytes()
    ep.upsert_client(paths.clients, client_id=ep.LOCAL_CLIENT_ID, token="y" * 40, requests_per_minute=20)
    assert ep.check_credentials(paths, ep.LOCAL_CLIENT_ID) == "digest_mismatch"

    ep.ensure_local_credentials(rig.local)

    assert paths.token.read_bytes() == token_bytes
    assert ep.check_credentials(paths, ep.LOCAL_CLIENT_ID) is None


def test_a_missing_local_token_gets_a_new_one_that_replaces_the_client_entry(rig: Rig) -> None:
    ep.ensure_local_credentials(rig.local)
    paths = ep.credential_paths(rig.local, ep.LOCAL_CLIENT_ID)
    old_digest = json.loads(paths.clients.read_text(encoding="utf-8"))["clients"][0]["token_sha256"]
    paths.token.unlink()

    done = ep.ensure_local_credentials(rig.local)

    assert done.created
    document = json.loads(paths.clients.read_text(encoding="utf-8"))
    assert len(document["clients"]) == 1 and document["clients"][0]["token_sha256"] != old_digest
    assert ep.check_credentials(paths, ep.LOCAL_CLIENT_ID) is None


def test_open_local_credential_files_are_tightened_and_named(rig: Rig) -> None:
    ep.ensure_local_credentials(rig.local)
    paths = ep.credential_paths(rig.local, ep.LOCAL_CLIENT_ID)
    os.chmod(paths.token, 0o644)
    os.chmod(paths.clients, 0o640)

    done = ep.ensure_local_credentials(rig.local)

    assert set(done.tightened) == {paths.token.name, paths.clients.name}
    assert mode(paths.token) == 0o600 and mode(paths.clients) == 0o600


# --- Status --------------------------------------------------------------------------------


def test_status_on_a_fresh_computer(rig: Rig) -> None:
    code = rig.status()

    assert code == 1
    assert rig.lines[0].startswith("NOT SET UP  local") and "./scripts/init.sh --local-rag-setup" in rig.lines[0]
    assert rig.lines[1].startswith("NOT SET UP  QA") and "./scripts/init.sh --qa-settings-setup" in rig.lines[1]
    assert rig.lines[2] == "NOT SET UP  prod: not configured; prod is not planned yet."
    assert rig.lines[3] == "Result: the local environment is not set up yet. Run ./scripts/init.sh --local-rag-setup."
    assert len(rig.lines) == 4
    assert not rig.tmp.joinpath("manijero").exists()


def test_status_with_local_ready_and_qa_prepared(rig: Rig) -> None:
    rig.make_local_ready()
    before_local = snapshot(rig.local)

    assert rig.status() == 0
    assert rig.lines[0].startswith("OK  local (default): ")
    for fragment in ("profile development", "campaign 2026", "0123456789abcdef", "access keys ready (not checked by the local service)"):
        assert fragment in rig.lines[0]
    assert rig.lines[1].startswith("NOT SET UP  QA")
    assert rig.lines[-1] == "Result: the local environment is ready."

    assert rig.qa_setup() == 0
    assert rig.status() == 0
    assert rig.lines[1].startswith("OK  QA:") and "placeholder" in rig.lines[1]
    assert rig.lines[-1] == "Result: the local environment is ready. QA is prepared on this computer but has no server yet."
    assert snapshot(rig.local) == before_local


def test_status_never_shows_a_token_or_digest(rig: Rig) -> None:
    rig.make_local_ready()
    rig.qa_setup()
    rig.status()
    secrets_seen = [rig.token_path.read_text(encoding="utf-8")]
    secrets_seen.append(ep.credential_paths(rig.local, ep.LOCAL_CLIENT_ID).token.read_text(encoding="utf-8"))
    secrets_seen += [token_sha256(token) for token in secrets_seen]

    assert not any(secret in rig.output for secret in secrets_seen)


def test_status_local_without_a_release_needs_attention(rig: Rig) -> None:
    rig.make_local_ready()
    (lrb.local_paths(rig.local).releases / "current").unlink()

    assert rig.status() == 1
    assert rig.lines[0].startswith("ATTENTION  local: no knowledge release yet") and "--local-rag-setup" in rig.lines[0]


def test_status_local_without_keys_needs_attention(rig: Rig) -> None:
    rig.make_local_ready(with_keys=False)

    assert rig.status() == 1
    assert rig.lines[0].startswith("ATTENTION  local: the local access keys are missing or incomplete")


def test_status_old_style_local_file_needs_attention(rig: Rig) -> None:
    rig.make_local_ready(with_lines=False)

    assert rig.status() == 1
    assert rig.lines[0].startswith("ATTENTION  local: the settings file does not say it is for the local environment")
    assert "--local-rag-setup" in rig.lines[0]


def test_status_reports_a_qa_problem_and_exits_1(rig: Rig) -> None:
    rig.make_local_ready()
    write_qa(rig, MANIJERO_DEPLOYMENT_PROFILE=None)

    assert rig.status() == 1
    assert rig.lines[1].startswith("PROBLEM  QA") and "never treated as local" in rig.lines[1]


def test_status_ignores_a_prod_folder_and_writes_nothing(rig: Rig) -> None:
    rig.make_local_ready()
    prod = rig.tmp / "manijero" / "prod"
    prod.mkdir()
    (prod / "settings.env").write_text("garbage that must never be read", encoding="utf-8")
    before = snapshot(rig.tmp)

    rig.status()

    assert rig.lines[2] == ep.PROD_LINE
    assert snapshot(rig.tmp) == before
