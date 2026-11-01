"""The shared Java resolution in ``scripts/java-env.sh`` (used by every ``./scripts/init.sh`` path
that runs ``./gradlew`` or ``java``), with fake JDKs in temporary folders.

Each run gets a temporary ``HOME``, a ``PATH`` holding only the few tools the resolution needs
(plus an optional fake ``java``), and ``MANIJERO_JAVA_HOME_TOOL`` pointing at a fake or missing
``java_home``, so no real JDK, home folder, or ``/usr/libexec/java_home`` is ever consulted.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
JAVA_ENV = REPO_ROOT / "scripts" / "java-env.sh"
INIT = REPO_ROOT / "scripts" / "init.sh"
BASH = shutil.which("bash") or "/bin/bash"
TOOLS = ("awk", "sed", "head", "sort", "tail", "cut", "dirname", "readlink", "cat", "uname")
STUB_MESSAGE = "The operation couldn't be completed. Unable to locate a Java Runtime."
MISSING = "Java was not found on this computer. Install Temurin 21 from https://adoptium.net, then run this command again."


def fake_jdk(home: Path, version: Optional[str] = "21.0.5") -> Path:
    """A JDK home whose bin/java runs and reports this home as java.home."""

    (home / "bin").mkdir(parents=True)
    java = home / "bin" / "java"
    java.write_text(
        "#!/bin/sh\n"
        'case "$1" in -XshowSettings*) echo "    java.home = {home}" >&2 ;; esac\n'
        'echo "openjdk version \\"{version}\\"" >&2\n'
        "exit 0\n".format(home=home, version=version or "?"),
        encoding="utf-8",
    )
    java.chmod(0o755)
    if version is not None:
        (home / "release").write_text('JAVA_VERSION="{}"\nIMPLEMENTOR="Eclipse Adoptium"\n'.format(version), encoding="utf-8")
    return home


def stub_java(directory: Path) -> Path:
    """Apple's /usr/bin/java placeholder: it exists, but only prints a message and fails."""

    directory.mkdir(parents=True, exist_ok=True)
    java = directory / "java"
    java.write_text("#!/bin/sh\necho \"{}\" >&2\nexit 1\n".format(STUB_MESSAGE), encoding="utf-8")
    java.chmod(0o755)
    return java


class Box:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.tools = tmp_path / "tools"
        self.tools.mkdir()
        for name in TOOLS:
            found = shutil.which(name)
            assert found, name
            (self.tools / name).symlink_to(found)
        self.path_dirs = [self.tools]
        self.java_home_tool = tmp_path / "no-java_home"
        self.java_home: Optional[Path] = None

    @property
    def jdks(self) -> Path:
        return self.home / ".gradle" / "jdks"

    def tool(self, answer: Optional[Path]) -> None:
        """A fake /usr/libexec/java_home: prints ``answer`` for ``-v 21``, or fails like macOS."""

        self.java_home_tool = self.tmp / "java_home"
        body = 'echo "{}"; exit 0'.format(answer) if answer else 'echo "Unable to find any JVMs matching version \\"21\\"." >&2; exit 1'
        self.java_home_tool.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        self.java_home_tool.chmod(0o755)

    def environment(self) -> Dict[str, str]:
        env = {
            "HOME": str(self.home),
            "PATH": ":".join(str(d) for d in self.path_dirs),
            "MANIJERO_JAVA_HOME_TOOL": str(self.java_home_tool),
        }
        if self.java_home is not None:
            env["JAVA_HOME"] = str(self.java_home)
        return env

    def resolve(self) -> subprocess.CompletedProcess:
        script = 'source "$1"; if manijero_resolve_java; then printf "%s\\n%s\\n" "$JAVA_HOME" "$PATH"; else echo NONE; [[ -z "${JAVA_HOME+x}" ]] && echo UNSET; fi'
        return subprocess.run(
            [BASH, "-c", script, "resolve", str(JAVA_ENV)],
            env=self.environment(), capture_output=True, text=True, timeout=60, check=False,
        )

    def chosen(self) -> str:
        completed = self.resolve()
        assert completed.returncode == 0, completed.stderr
        assert STUB_MESSAGE not in completed.stdout + completed.stderr
        java_home, path = completed.stdout.splitlines()
        assert path.split(":")[0] == java_home + "/bin"
        return java_home


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def test_a_working_java_home_comes_first(box: Box) -> None:
    box.java_home = fake_jdk(box.tmp / "env-jdk", "17.0.9")
    box.tool(fake_jdk(box.tmp / "system-21"))
    fake_jdk(box.jdks / "jdk-21.0.5")

    assert box.chosen() == str(box.java_home)


def test_a_broken_java_home_falls_back_to_java_home_v21(box: Box) -> None:
    box.java_home = box.tmp / "broken"
    stub_java(box.java_home / "bin")
    system = fake_jdk(box.tmp / "Temurin-21.jdk" / "Contents" / "Home")
    box.tool(system)
    fake_jdk(box.jdks / "jdk-21.0.9")

    assert box.chosen() == str(system)


def test_a_failing_java_home_tool_falls_back_to_a_working_java_on_path(box: Box) -> None:
    box.tool(None)
    on_path = fake_jdk(box.tmp / "path-jdk")
    box.path_dirs.insert(0, on_path / "bin")
    fake_jdk(box.jdks / "jdk-21.0.9")

    assert box.chosen() == str(on_path)


def test_a_java_home_answer_without_a_working_java_is_skipped(box: Box) -> None:
    box.tool(box.tmp / "nowhere")
    gradle = fake_jdk(box.jdks / "jdk-21.0.3")

    assert box.chosen() == str(gradle)


def test_the_placeholder_on_path_is_rejected_and_the_newest_gradle_jdk21_is_chosen_by_version(box: Box) -> None:
    box.tool(None)
    box.path_dirs.insert(0, stub_java(box.tmp / "usr-bin").parent)
    # 21.0.10 is newer than 21.0.9 by version even though it sorts first as text, and the older
    # JDKs are touched last so a date-based pick would be wrong.
    newest = fake_jdk(box.jdks / "eclipse_adoptium-21-aarch64-os_x.2" / "jdk-21.0.10+7" / "Contents" / "Home", "21.0.10")
    nine = fake_jdk(box.jdks / "jdk-21.0.9", "21.0.9")  # flat layout
    two = fake_jdk(box.jdks / "jdk-21.0.2.jdk" / "Contents" / "Home", "21.0.2")  # one-level bundle
    fake_jdk(box.jdks / "jdk-17.0.9", "17.0.9")
    fake_jdk(box.jdks / "jdk-22", "22")
    fake_jdk(box.jdks / "no-release", None)
    for later in (nine, two):
        os.utime(later / "bin" / "java")
        os.utime(later)

    assert box.chosen() == str(newest)


def test_the_bundle_layout_is_used_when_it_is_the_only_jdk21(box: Box) -> None:
    bundle = fake_jdk(box.jdks / "jdk-21.0.4.jdk" / "Contents" / "Home")

    assert box.chosen() == str(bundle)


def test_gradle_user_home_is_honoured(box: Box) -> None:
    other = box.tmp / "gradle-home"
    jdk = fake_jdk(other / "jdks" / "jdk-21.0.1")
    fake_jdk(box.jdks / "jdk-21.0.9")
    completed = subprocess.run(
        [BASH, "-c", 'source "$1"; manijero_resolve_java && echo "$JAVA_HOME"', "resolve", str(JAVA_ENV)],
        env={**box.environment(), "GRADLE_USER_HOME": str(other)}, capture_output=True, text=True, timeout=60, check=False,
    )
    assert completed.stdout.strip() == str(jdk)


def test_nothing_found_unsets_java_home_and_prints_nothing(box: Box) -> None:
    box.java_home = box.tmp / "broken"
    stub_java(box.java_home / "bin")
    box.tool(None)
    box.path_dirs.insert(0, stub_java(box.tmp / "usr-bin").parent)
    fake_jdk(box.jdks / "jdk-17.0.9", "17.0.9")

    completed = box.resolve()

    assert completed.stdout.splitlines() == ["NONE", "UNSET"]
    assert completed.stderr == ""


def test_init_says_how_to_install_java_when_none_is_found(box: Box) -> None:
    box.tool(None)
    box.path_dirs.insert(0, stub_java(box.tmp / "usr-bin").parent)

    completed = subprocess.run(
        [BASH, str(INIT), "--check"],
        cwd=box.tmp,  # init.sh writes local.properties to the current folder only when it is missing
        env={**box.environment(), "ANDROID_HOME": str(box.tmp / "sdk")},
        capture_output=True, text=True, timeout=60, check=False,
    )

    assert completed.returncode == 1
    lines = [line for line in completed.stdout.splitlines() if not line.startswith("Created local.properties")]
    assert lines == [
        MISSING,
        "Result: nothing was run. Install Temurin 21 from https://adoptium.net, then run this command again.",
    ]
    assert STUB_MESSAGE not in completed.stdout + completed.stderr
