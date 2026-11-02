"""Per-environment settings, access keys, and knowledge release roots (local, QA, prod).

Operator-only and stdlib-plus-``app`` at import time; the answer service never imports this
module. It is the one place later environment features read an environment's settings:

* ``local`` is the default for development: ``MANIJERO_ENVIRONMENT=local`` with deployment
  profile ``development``, under ``~/manijero/local``;
* ``qa`` is prepared on this computer only: ``MANIJERO_ENVIRONMENT=qa`` with deployment profile
  ``pilot``, under ``~/manijero/qa``; nothing is deployed and no server is contacted;
* ``prod`` is unconfigured: nothing here creates, reads, or accepts a prod file.

A settings file always names its environment and its deployment profile. A QA file that does not
say so is refused with a plain sentence; nothing is ever defaulted to local or to ``development``.
Access keys are generated here into the environment's own home (outside the checkout, mode
``0600``); a token is never printed, logged, or put in a repository file, and the clients file
holds digests only. Every message is a fixed English sentence with no secret value.

External effects go through injected ports (:class:`Ports`) so tests use fakes.
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Protocol, Tuple
from urllib.parse import urlsplit

from app import knowledge_release as kr
from app import local_rag_bootstrap as boot
from app.pilot_config import PilotConfigError, token_sha256, validate_clients_document
from app.pilot_ops import MIN_CLIENT_TOKEN_LENGTH, PilotOperationError, upsert_client

REPOSITORY_ROOT = boot.REPOSITORY_ROOT

STATUS_COMMAND = "./scripts/init.sh --environments-status"
QA_SETUP_COMMAND = "./scripts/init.sh --qa-settings-setup"
LOCAL_SETUP_COMMAND = boot.SETUP_COMMAND

QA_HOME_ENV = "MANIJERO_QA_HOME"  # tests only
LOCAL = "local"
QA = "qa"
PROD = "prod"

ENVIRONMENT_KEY = boot.ENVIRONMENT_KEY
PROFILE_KEY = boot.PROFILE_KEY
CAMPAIGN_KEY = boot.CAMPAIGN_KEY
PUBLIC_URL_KEY = "MANIJERO_PUBLIC_URL"
CLIENTS_FILE_KEY = "MANIJERO_PILOT_CLIENTS_FILE"
RELEASE_ROOT_KEY = "MANIJERO_KNOWLEDGE_RELEASE_ROOT"
QA_KEYS = (ENVIRONMENT_KEY, PROFILE_KEY, CAMPAIGN_KEY, PUBLIC_URL_KEY, CLIENTS_FILE_KEY, RELEASE_ROOT_KEY)
QA_PROFILE = "pilot"

SETTINGS_NAME = "settings.env"
CREDENTIALS_DIR = "credentials"
RELEASES_NAME = "knowledge-releases"
CLIENTS_NAME = "pilot-clients.json"
LOCAL_CLIENT_ID = "local-test-device"
QA_CLIENT_ID = "qa-test-device"
REQUESTS_PER_MINUTE = 20
PLACEHOLDER_SUFFIX = ".invalid"
TEMPLATE_PATH = REPOSITORY_ROOT / "backend" / "deploy" / "environments" / "qa.settings.env.example"
HOME_MARKER = "@QA_HOME@"
TOKEN_BYTES = 48  # token_urlsafe(48) is 64 characters

PRIVATE_FILE = 0o600
PRIVATE_DIR = 0o700
SETTINGS_MODE = 0o644
GROUP_OTHER = 0o077

PROD_LINE = "NOT SET UP  prod: not configured; prod is not planned yet."
NO_RELEASE = "no_release"


# --- Errors -------------------------------------------------------------------------------


class ProfileSettingsError(Exception):
    """A settings file is refused: a fixed ``code`` and one plain ``sentence``."""

    def __init__(self, code: str, sentence: str) -> None:
        super().__init__(sentence)
        self.code = code
        self.sentence = sentence


# --- Homes --------------------------------------------------------------------------------


def local_home() -> Path:
    return boot.default_home()


def qa_home() -> Path:
    configured = os.environ.get(QA_HOME_ENV, "").strip()
    return Path(configured).expanduser() if configured else Path.home() / "manijero" / QA


def inside(path: Path, other: Path) -> bool:
    """Whether ``path`` is ``other`` or lies inside it (symlinks resolved)."""

    candidate = Path(os.path.realpath(path))
    root = Path(os.path.realpath(other))
    return candidate == root or root in candidate.parents


def overlaps(first: Path, second: Path) -> bool:
    return inside(first, second) or inside(second, first)


@dataclass(frozen=True)
class ProfileSettings:
    """A validated settings file; every field was checked by :func:`read_profile_settings`."""

    name: str
    path: Path
    environment: str
    deployment_profile: str
    campaign: str
    release_root: Path
    clients_file: Path
    public_url: Optional[str] = None

    @property
    def placeholder_url(self) -> bool:
        if not self.public_url:
            return False
        host = urlsplit(self.public_url).hostname or ""
        return host.endswith(PLACEHOLDER_SUFFIX)


# --- Reading settings ---------------------------------------------------------------------


def read_profile_settings(name: str, home: Optional[Path] = None) -> ProfileSettings:
    """Read and validate one environment's settings; never defaults a file to local.

    Raises :class:`ProfileSettingsError` with one of the codes ``prod_not_configured``,
    ``unknown_environment``, ``settings_missing``, ``settings_unreadable``, ``line_invalid``,
    ``key_unknown``, ``key_repeated``, ``key_missing``, ``environment_mismatch``,
    ``profile_mismatch``, ``campaign_invalid``, ``url_invalid``, ``path_relative``,
    ``path_in_checkout``, ``release_root_overlaps_local``, ``local_settings_invalid``.
    """

    if name == PROD:
        raise ProfileSettingsError(
            "prod_not_configured", "The prod environment is not configured; prod is not planned yet."
        )
    if name == LOCAL:
        return _read_local(home)
    if name == QA:
        return _read_qa(home)
    raise ProfileSettingsError("unknown_environment", "There is no environment called {}.".format(name))


def _read_local(home: Optional[Path]) -> ProfileSettings:
    paths = boot.local_paths(home if home is not None else local_home())
    try:
        settings = boot.read_settings(paths.settings)
    except boot.SettingsError as error:
        raise ProfileSettingsError("local_settings_invalid", error.message) from None
    if settings is None:
        raise ProfileSettingsError(
            "settings_missing",
            "The local settings file {} does not exist. Run {}.".format(paths.settings, LOCAL_SETUP_COMMAND),
        )
    for key, value, present in (
        (ENVIRONMENT_KEY, boot.LOCAL_ENVIRONMENT, settings.environment),
        (PROFILE_KEY, boot.LOCAL_PROFILE, settings.deployment_profile),
    ):
        if present is None:
            raise ProfileSettingsError(
                "key_missing",
                "The settings file {} does not say it is for the local environment. Run {}, which adds "
                "the line {}={}.".format(paths.settings, LOCAL_SETUP_COMMAND, key, value),
            )
    return ProfileSettings(
        name=LOCAL,
        path=paths.settings,
        environment=boot.LOCAL_ENVIRONMENT,
        deployment_profile=boot.LOCAL_PROFILE,
        campaign=settings.active_campaign,
        release_root=paths.releases,
        clients_file=paths.home / CREDENTIALS_DIR / CLIENTS_NAME,
    )


def _qa_line_error(path: Path, number: int, problem: str) -> ProfileSettingsError:
    return ProfileSettingsError(
        "line_invalid",
        "The settings file {} has a problem on line {}: {}. Fix that line, then run the same command "
        "again.".format(path, number, problem),
    )


def _qa_must_say(path: Path, number: Optional[int], key: str, value: str, code: str) -> ProfileSettingsError:
    reason = "this file is for QA, so it must say {}={}; it is never treated as local".format(key, value)
    if number is None:
        return ProfileSettingsError(
            code,
            "The settings file {} is missing the line {}={}: {}. Add that line, then run the same "
            "command again.".format(path, key, value, reason),
        )
    return ProfileSettingsError(
        code,
        "The settings file {} has a problem on line {}: {}. Fix that line, then run the same command "
        "again.".format(path, number, reason),
    )


def _read_qa(home: Optional[Path]) -> ProfileSettings:
    root = Path(home) if home is not None else qa_home()
    path = root / SETTINGS_NAME
    if not path.exists():
        raise ProfileSettingsError(
            "settings_missing",
            "The QA settings file {} does not exist. Run {}.".format(path, QA_SETUP_COMMAND),
        )
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        raise ProfileSettingsError(
            "settings_unreadable",
            "The settings file {} cannot be read. Make sure it is a plain text file, then run the same "
            "command again.".format(path),
        ) from None
    values: Dict[str, str] = {}
    numbers: Dict[str, int] = {}
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise _qa_line_error(path, number, "it must look like NAME=value")
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in QA_KEYS:
            raise ProfileSettingsError(
                "key_unknown",
                "The settings file {} has a problem on line {}: it is not a setting this tool knows. Fix "
                "that line, then run the same command again.".format(path, number),
            )
        if key in values:
            raise ProfileSettingsError(
                "key_repeated",
                "The settings file {} has a problem on line {}: this setting appears twice. Fix that line, "
                "then run the same command again.".format(path, number),
            )
        values[key] = boot._unquote(value)
        numbers[key] = number

    if ENVIRONMENT_KEY not in values:
        raise _qa_must_say(path, None, ENVIRONMENT_KEY, QA, "key_missing")
    if values[ENVIRONMENT_KEY] != QA:
        raise _qa_must_say(path, numbers[ENVIRONMENT_KEY], ENVIRONMENT_KEY, QA, "environment_mismatch")
    if PROFILE_KEY not in values:
        raise _qa_must_say(path, None, PROFILE_KEY, QA_PROFILE, "key_missing")
    if values[PROFILE_KEY] != QA_PROFILE:
        raise _qa_must_say(path, numbers[PROFILE_KEY], PROFILE_KEY, QA_PROFILE, "profile_mismatch")
    for key in (CAMPAIGN_KEY, PUBLIC_URL_KEY, CLIENTS_FILE_KEY, RELEASE_ROOT_KEY):
        if key not in values:
            raise ProfileSettingsError(
                "key_missing",
                "The settings file {} does not set {}. Add that line, or run {} to see what is missing."
                .format(path, key, STATUS_COMMAND),
            )

    campaign = values[CAMPAIGN_KEY]
    if len(campaign) != 4 or not campaign.isdigit():
        raise _qa_line_error(path, numbers[CAMPAIGN_KEY], "the campaign must be a four-digit year, for example 2026")
    url = values[PUBLIC_URL_KEY]
    if not _valid_https_url(url):
        raise ProfileSettingsError(
            "url_invalid",
            "The settings file {} has a problem on line {}: the address must start with https:// and name a "
            "host. Fix that line, then run the same command again.".format(path, numbers[PUBLIC_URL_KEY]),
        )
    clients_file = _checked_path(path, numbers, values, CLIENTS_FILE_KEY)
    release_root = _checked_path(path, numbers, values, RELEASE_ROOT_KEY)
    local_releases = boot.local_paths(local_home()).releases
    if overlaps(release_root, local_releases):
        raise ProfileSettingsError(
            "release_root_overlaps_local",
            "The settings file {} has a problem on line {}: QA must have its own knowledge release folder, "
            "not the local one. Fix that line, then run the same command again.".format(
                path, numbers[RELEASE_ROOT_KEY]
            ),
        )
    return ProfileSettings(
        name=QA,
        path=path,
        environment=QA,
        deployment_profile=QA_PROFILE,
        campaign=campaign,
        release_root=release_root,
        clients_file=clients_file,
        public_url=url,
    )


def _valid_https_url(value: str) -> bool:
    if not value or any(character.isspace() for character in value):
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme == "https" and bool(parts.hostname)
    except ValueError:
        return False


def _checked_path(path: Path, numbers: Mapping[str, int], values: Mapping[str, str], key: str) -> Path:
    candidate = Path(values[key])
    if not candidate.is_absolute():
        raise ProfileSettingsError(
            "path_relative",
            "The settings file {} has a problem on line {}: the folder or file must be a full path that "
            "starts with /. Fix that line, then run the same command again.".format(path, numbers[key]),
        )
    if inside(candidate, REPOSITORY_ROOT):
        raise ProfileSettingsError(
            "path_in_checkout",
            "The settings file {} has a problem on line {}: it must point outside the Manijero folder so "
            "nothing secret can be committed. Fix that line, then run the same command again.".format(
                path, numbers[key]
            ),
        )
    return candidate


# --- Access keys --------------------------------------------------------------------------


@dataclass(frozen=True)
class CredentialPaths:
    directory: Path
    token: Path
    clients: Path


def credential_paths(home: Path, client_id: str) -> CredentialPaths:
    directory = Path(home) / CREDENTIALS_DIR
    return CredentialPaths(directory, directory / "{}.token".format(client_id), directory / CLIENTS_NAME)


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def read_token(path: Path) -> Optional[str]:
    """The token in ``path`` (surrounding whitespace removed), or ``None`` when unusable."""

    try:
        token = Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return token if len(token) >= MIN_CLIENT_TOKEN_LENGTH else None


def check_credentials(paths: CredentialPaths, client_id: str) -> Optional[str]:
    """``None`` when the pair is complete and consistent; otherwise a fixed reason code.

    Reads only. Reasons: ``absent`` (neither file exists), ``token_missing``,
    ``clients_missing``, ``token_open``, ``clients_open``, ``token_unreadable``,
    ``clients_invalid``, ``digest_mismatch``.
    """

    token_exists = paths.token.exists()
    clients_exists = paths.clients.exists()
    if not token_exists and not clients_exists:
        return "absent"
    if not token_exists:
        return "token_missing"
    if not clients_exists:
        return "clients_missing"
    try:
        token_mode, clients_mode = _mode(paths.token), _mode(paths.clients)
    except OSError:
        return "token_unreadable"
    if token_mode & GROUP_OTHER:
        return "token_open"
    if clients_mode & GROUP_OTHER:
        return "clients_open"
    token = read_token(paths.token)
    if token is None:
        return "token_unreadable"
    try:
        document = json.loads(paths.clients.read_text(encoding="utf-8"))
        clients = validate_clients_document(document)
    except (OSError, ValueError, PilotConfigError):
        return "clients_invalid"
    digest = token_sha256(token)
    if not any(client.client_id == client_id and client.token_sha256 == digest for client in clients):
        return "digest_mismatch"
    return None


def _make_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, PRIVATE_DIR)


def _new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _write_new_token(path: Path, token: str) -> None:
    """Create the token file with ``O_EXCL`` and mode ``0600``; never overwrites."""

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(token)
    os.chmod(path, PRIVATE_FILE)


def _replace_token(path: Path, token: str) -> None:
    """Replace the token file atomically (private temporary file, then rename)."""

    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".token-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
        os.chmod(temporary, PRIVATE_FILE)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _replace_clients(path: Path, client_id: str, token: str) -> None:
    """Write a fresh clients file (this one client, digest only) and rename it into place."""

    temporary = path.parent / ".{}.new".format(path.name)
    if temporary.exists():
        temporary.unlink()
    try:
        upsert_client(temporary, client_id=client_id, token=token, requests_per_minute=REQUESTS_PER_MINUTE)
        os.chmod(temporary, PRIVATE_FILE)
        os.replace(temporary, path)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def make_new_credentials(home: Path, client_id: str) -> None:
    """Make a fresh token and clients file, replacing both (used by QA setup and recovery)."""

    paths = credential_paths(home, client_id)
    _make_directory(paths.directory)
    token = _new_token()
    _replace_token(paths.token, token)
    _replace_clients(paths.clients, client_id, token)


@dataclass(frozen=True)
class CredentialWork:
    created: bool = False
    tightened: Tuple[str, ...] = field(default=())


def ensure_local_credentials(home: Path) -> CredentialWork:
    """Make the local access keys if needed; never overwrite an existing token.

    A missing or mismatched clients file is rebuilt from the existing token's digest; a missing
    token gets a new one whose digest replaces that client's entry; a group/other bit on either
    file is removed and named. A consistent pair is left untouched.
    """

    paths = credential_paths(home, LOCAL_CLIENT_ID)
    created = False
    tightened: List[str] = []
    if not paths.directory.is_dir():
        created = True
    _make_directory(paths.directory)

    for target in (paths.token, paths.clients):
        if target.exists() and _mode(target) & GROUP_OTHER:
            os.chmod(target, PRIVATE_FILE)
            tightened.append(target.name)

    token = read_token(paths.token) if paths.token.exists() else None
    if token is None:
        token = _new_token()
        if paths.token.exists():
            _replace_token(paths.token, token)  # an empty or too-short token is unusable
        else:
            _write_new_token(paths.token, token)
        created = True
    if check_credentials(paths, LOCAL_CLIENT_ID) is not None:
        _upsert_local_client(paths.clients, token)
        created = True
    return CredentialWork(created=created, tightened=tuple(tightened))


def _upsert_local_client(clients: Path, token: str) -> None:
    try:
        upsert_client(clients, client_id=LOCAL_CLIENT_ID, token=token, requests_per_minute=REQUESTS_PER_MINUTE)
    except PilotOperationError as error:
        if error.code != "clients_invalid":
            raise
        clients.unlink()
        upsert_client(clients, client_id=LOCAL_CLIENT_ID, token=token, requests_per_minute=REQUESTS_PER_MINUTE)
    os.chmod(clients, PRIVATE_FILE)


# --- Ports --------------------------------------------------------------------------------


class Prompter(Protocol):
    def ask(self, question: str) -> Optional[str]: ...


@dataclass
class Ports:
    """Output, the prompter, and whether a terminal is attached; tests pass fakes."""

    out: Callable[[str], None]
    prompter: Prompter
    tty: bool


# --- Status -------------------------------------------------------------------------------

OK = "OK"
ATTENTION = "ATTENTION"
PROBLEM = "PROBLEM"
NOT_SET_UP = "NOT SET UP"


@dataclass(frozen=True)
class EnvironmentLine:
    state: str
    text: str

    @property
    def render(self) -> str:
        return "{}  {}".format(self.state, self.text)


def _local_line(home: Path) -> EnvironmentLine:
    paths = boot.local_paths(home)
    if not paths.settings.exists():
        return EnvironmentLine(
            NOT_SET_UP,
            "local: no settings file yet. Run {}.".format(LOCAL_SETUP_COMMAND),
        )
    try:
        settings = boot.read_settings(paths.settings)
    except boot.SettingsError as error:
        return EnvironmentLine(PROBLEM, "local: {}".format(error.message))
    if settings is None or not settings.names_environment:
        return EnvironmentLine(
            ATTENTION,
            "local: the settings file does not say it is for the local environment. Run {}.".format(
                LOCAL_SETUP_COMMAND
            ),
        )
    try:
        release = kr.current_release_id(paths.releases)
    except kr.ReleaseError:
        return EnvironmentLine(
            ATTENTION, "local: the knowledge release is damaged. Run {}.".format(LOCAL_SETUP_COMMAND)
        )
    if release is None:
        return EnvironmentLine(
            ATTENTION, "local: no knowledge release yet. Run {}.".format(LOCAL_SETUP_COMMAND)
        )
    if check_credentials(credential_paths(home, LOCAL_CLIENT_ID), LOCAL_CLIENT_ID) is not None:
        return EnvironmentLine(
            ATTENTION,
            "local: the local access keys are missing or incomplete. Run {}.".format(LOCAL_SETUP_COMMAND),
        )
    return EnvironmentLine(
        OK,
        "local (default): {}; profile {}; campaign {}; release {}; access keys ready (not checked by the "
        "local service).".format(paths.settings, boot.LOCAL_PROFILE, settings.active_campaign, release),
    )


def _qa_line(home: Path) -> EnvironmentLine:
    settings_path = home / SETTINGS_NAME
    paths = credential_paths(home, QA_CLIENT_ID)
    if not settings_path.exists():
        if not paths.directory.exists():
            return EnvironmentLine(
                NOT_SET_UP, "QA: not prepared on this computer. Run {}.".format(QA_SETUP_COMMAND)
            )
        return EnvironmentLine(
            PROBLEM, "QA: the settings file {} is missing. Run {}.".format(settings_path, QA_SETUP_COMMAND)
        )
    try:
        settings = read_profile_settings(QA, home)
    except ProfileSettingsError as error:
        return EnvironmentLine(PROBLEM, "QA: {}".format(error.sentence))
    if check_credentials(paths, QA_CLIENT_ID) is not None:
        return EnvironmentLine(
            PROBLEM,
            "QA: the QA access keys are missing or incomplete. Run {}.".format(QA_SETUP_COMMAND),
        )
    address = settings.public_url or ""
    if settings.placeholder_url:
        address += " (a placeholder until the QA server is chosen)"
    return EnvironmentLine(
        OK,
        "QA: {}; profile {}; campaign {}; address {}; knowledge releases in {}; access keys ready.".format(
            settings.path, settings.deployment_profile, settings.campaign, address, settings.release_root
        ),
    )


def run_status(ports: Ports, local: Optional[Path] = None, qa: Optional[Path] = None) -> int:
    """Print the local, QA, and prod lines and one result line; reads only."""

    local_line = _local_line(local if local is not None else local_home())
    qa_line = _qa_line(qa if qa is not None else qa_home())
    for line in (local_line.render, qa_line.render, PROD_LINE):
        ports.out(line)
    if local_line.state == NOT_SET_UP:
        ports.out(
            "Result: the local environment is not set up yet. Run {}.".format(LOCAL_SETUP_COMMAND)
        )
        return 1
    if local_line.state != OK:
        ports.out("Result: the local environment needs attention. Run {}.".format(LOCAL_SETUP_COMMAND))
        return 1
    if qa_line.state == PROBLEM:
        ports.out(
            "Result: the local environment is ready, but QA has a problem. Do what the QA line says."
        )
        return 1
    suffix = " QA is prepared on this computer but has no server yet." if qa_line.state == OK else ""
    ports.out("Result: the local environment is ready.{}".format(suffix))
    return 0


# --- QA setup -----------------------------------------------------------------------------

RECOVERY_QUESTION = "Make new QA access keys? Type yes and press Enter: "
_INCOMPLETE_REASON = {
    "token_missing": "the token file is missing",
    "clients_missing": "the clients file is missing",
    "token_open": "the token file can be read by other users",
    "clients_open": "the clients file can be read by other users",
    "token_unreadable": "the token file cannot be read",
    "clients_invalid": "the clients file cannot be read",
    "digest_mismatch": "the token does not match the clients file",
}


def render_template(home: Path) -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8").replace(HOME_MARKER, str(home))


def _create_settings(path: Path, home: Path) -> bool:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, SETTINGS_MODE)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(render_template(home))
    os.chmod(path, SETTINGS_MODE)
    return True


def run_qa_setup(ports: Ports, qa: Optional[Path] = None, local: Optional[Path] = None) -> int:
    """Prepare QA on this computer: settings, release folder, access keys; deploys nothing."""

    out = ports.out
    home = Path(qa) if qa is not None else qa_home()
    for folder in (home, Path(local) if local is not None else local_home()):
        if inside(folder, REPOSITORY_ROOT):
            out(
                "The folder {} is inside the Manijero folder, where a secret could be committed. Use a "
                "folder outside it.".format(folder)
            )
            out("Result: QA was not prepared. Nothing was changed.")
            return 1

    settings_path = home / SETTINGS_NAME
    paths = credential_paths(home, QA_CLIENT_ID)
    if settings_path.exists():
        try:
            read_profile_settings(QA, home)
        except ProfileSettingsError as error:
            out(error.sentence)
            out("Result: QA was not changed. Fix the line named above, then run {} again.".format(QA_SETUP_COMMAND))
            return 1

    reason = check_credentials(paths, QA_CLIENT_ID)
    replace_keys = False
    if reason not in (None, "absent"):
        out(
            "The QA access keys are incomplete ({}). New keys replace both files, and any copy of the old "
            "QA token stops working.".format(_INCOMPLETE_REASON[reason])
        )
        if not ports.tty:
            out("Run {} in a Terminal window to make new QA access keys. Nothing was changed.".format(QA_SETUP_COMMAND))
            out("Result: QA was not changed.")
            return 1
        answer = ports.prompter.ask(RECOVERY_QUESTION)
        if answer is None or answer.strip().lower() not in ("yes", "y"):
            out("Nothing was changed.")
            out("Result: QA was not changed.")
            return 1
        replace_keys = True

    made: List[str] = []
    if _create_settings_if_missing(settings_path, home):
        made.append("the settings file {}".format(settings_path))
    releases = home / RELEASES_NAME
    if not releases.is_dir():
        releases.mkdir(parents=True, exist_ok=True)
        made.append("the empty knowledge release folder {}".format(releases))
    if replace_keys or reason == "absent":
        make_new_credentials(home, QA_CLIENT_ID)
        made.append("the QA access keys in {}".format(paths.directory))

    settings = read_profile_settings(QA, home)
    if not made:
        out(_qa_line(home).render)
        out("Result: QA was already prepared; nothing was changed.")
        return 0
    for item in made:
        out("Made {}.".format(item))
    if settings.placeholder_url:
        out(
            "The QA address {} is a placeholder until the QA server is chosen. No server was contacted.".format(
                settings.public_url
            )
        )
    else:
        out("No server was contacted.")
    if replace_keys:
        out("Result: new QA access keys were made. Nothing was deployed.")
    else:
        out("Result: QA is prepared on this computer. Nothing was deployed.")
    return 0


def _create_settings_if_missing(path: Path, home: Path) -> bool:
    home.mkdir(parents=True, exist_ok=True)
    return _create_settings(path, home)
