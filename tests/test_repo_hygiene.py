"""
Section A band 4 — repo hygiene (T3/T15).

File-content assertions: cheap, fail-if-reverted guards against database
files sneaking back into git, weak Flower credentials, and prod running in
dev mode.
"""

from __future__ import annotations

import os
import subprocess

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(relpath: str) -> str:
    with open(os.path.join(REPO_ROOT, relpath)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# T3 — no tracked database files; .gitignore covers them
# ---------------------------------------------------------------------------

class TestT3NoTrackedDatabases:
    def test_gitignore_covers_db_patterns(self):
        gitignore = _read(".gitignore")
        for pattern in ("*.db", "*.sqlite", "*.sqlite3", "*.db-journal"):
            assert pattern in gitignore, f".gitignore missing {pattern}"

    def test_no_db_files_tracked(self):
        try:
            out = subprocess.run(
                ["git", "ls-files"], capture_output=True, text=True,
                cwd=REPO_ROOT, timeout=30,
            ).stdout
        except Exception:
            pytest.skip("git unavailable")
        tracked = [
            line for line in out.splitlines()
            if line.endswith((".db", ".sqlite", ".sqlite3", ".db-journal"))
        ]
        assert tracked == [], f"database files tracked in git: {tracked}"


# ---------------------------------------------------------------------------
# T15 — prod env markers + no weak Flower default
# ---------------------------------------------------------------------------

class TestT15ProdPosture:
    def test_render_sets_environment_production(self):
        render = _read("render.yaml")
        assert 'value: "production"' in render
        # The web service must also pin DEBUG off explicitly.
        assert "- key: DEBUG" in render
        assert 'value: "false"' in render

    def test_flower_has_no_weak_default(self):
        compose = _read("docker-compose.yml")
        # No default-value substitution for the credentials (a comment may
        # mention the old value; the ${VAR:-default} FORM must be gone).
        assert ":-ospra123" not in compose
        assert ":-admin" not in compose
        # Fails-loudly form: :?error if unset.
        assert "FLOWER_USER:?" in compose
        assert "FLOWER_PASSWORD:?" in compose
