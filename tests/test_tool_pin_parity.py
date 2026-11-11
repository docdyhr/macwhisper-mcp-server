"""Exact tool pins agree across every file that pins them.

Dependabot's pip updater moves `requirements*.txt` and `pyproject.toml`, but never the
ruff-pre-commit hook `rev:` (this repo has no pre-commit ecosystem configured), so a
ruff bump PR fails here until the hook moves too. Each helper asserts it found exactly
one concrete pin, so a site that is renamed, duplicated or loosened to a range or
wildcard fails loudly instead of dropping out of the comparison.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUFF_HOOK_REPO = "https://github.com/astral-sh/ruff-pre-commit"

# A concrete PEP 440 version after `==`: no wildcard, no `===`, then only an optional
# environment marker or comment.
_VERSION = r"([0-9][0-9A-Za-z.+!_-]*)"


def _exact_pin(requirements: list[str], name: str) -> str:
    """Return the version `name` is pinned to with `==`; fail unless exactly one such pin."""
    pattern = re.compile(rf"^{re.escape(name)}\s*==\s*{_VERSION}\s*(?:[;#].*)?$", re.IGNORECASE)
    hits = [m.group(1) for line in requirements if (m := pattern.match(line.strip()))]
    assert len(hits) == 1, (
        f"expected one exact '{name}==<version>' pin, found {hits} in {requirements}"
    )
    return hits[0]


def _requirement_lines(path: Path) -> list[str]:
    """Requirement lines of one file. `-r`/`-c` includes are not followed: keep pins here."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ln.strip() and not ln.lstrip().startswith(("#", "-"))]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _precommit_revs(config_text: str, repo_url: str) -> list[str]:
    """Versions of every `repos:` entry for `repo_url`, in either key order.

    Accepts a quoted URL, a `.git` suffix, a `v` prefix, and the
    `pre-commit autoupdate --freeze` form (`rev: <sha>  # frozen: vX.Y.Z`).
    """
    revs = []
    for block in re.split(r"(?m)^\s*-\s+(?=(?:repo|rev):)", config_text):
        repo = re.search(r"(?m)^\s*repo:\s*['\"]?(\S+?)(?:\.git)?['\"]?\s*(?:#.*)?$", block)
        if not repo or repo.group(1) != repo_url:
            continue
        rev = re.search(
            r"(?m)^\s*rev:\s*['\"]?([^\s'\"#]+)['\"]?\s*(?:#\s*frozen:\s*(\S+))?", block
        )
        assert rev, f"the {repo_url} entry has no 'rev:'"
        revs.append((rev.group(2) or rev.group(1)).removeprefix("v"))
    return revs


def _precommit_rev(repo_url: str) -> str:
    text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    revs = _precommit_revs(text, repo_url)
    assert len(revs) == 1, f"expected one {repo_url} entry in .pre-commit-config.yaml, got {revs}"
    return revs[0]


def test_ruff_pinned_identically_in_every_site():
    sites = {
        "requirements-dev.txt": _exact_pin(
            _requirement_lines(ROOT / "requirements-dev.txt"), "ruff"
        ),
        "pyproject.toml [project.optional-dependencies] dev": _exact_pin(
            _pyproject()["project"]["optional-dependencies"]["dev"], "ruff"
        ),
        ".pre-commit-config.yaml ruff-pre-commit rev": _precommit_rev(RUFF_HOOK_REPO),
    }
    assert len(set(sites.values())) == 1, f"ruff pins disagree: {sites}"


def test_fastmcp_pinned_identically_in_every_site():
    """CLAUDE.md invariant 5: requirements.txt and pyproject.toml pin the same fastmcp."""
    sites = {
        "requirements.txt": _exact_pin(_requirement_lines(ROOT / "requirements.txt"), "fastmcp"),
        "pyproject.toml [project] dependencies": _exact_pin(
            _pyproject()["project"]["dependencies"], "fastmcp"
        ),
    }
    assert len(set(sites.values())) == 1, f"fastmcp pins disagree: {sites}"


def test_pin_helpers_on_synthetic_inputs():
    """The helpers' own contract, independent of the live files."""
    assert _exact_pin(["ruff==0.17.4"], "ruff") == "0.17.4"
    assert _exact_pin(['ruff == 0.17.4 ; python_version >= "3.13"'], "ruff") == "0.17.4"
    for loose in (["ruff==0.17.*"], ["ruff===0.17.4"], ["ruff>=0.17"], ["ruff-lsp==0.1.0"]):
        try:
            _exact_pin(loose, "ruff")
        except AssertionError:
            continue
        raise AssertionError(f"{loose} was accepted as an exact ruff pin")

    url = RUFF_HOOK_REPO
    plain = f"repos:\n  - repo: {url}\n    rev: v0.17.4\n    hooks:\n      - id: ruff\n"
    quoted = f'repos:\n  - repo: "{url}.git"\n    rev: "v0.17.4"\n'
    reordered = f"repos:\n  - rev: v0.17.4\n    repo: {url}\n"
    frozen = f"repos:\n  - repo: {url}\n    rev: {'a' * 40}  # frozen: v0.17.4\n"
    other = "repos:\n  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v6.0.0\n"
    for text in (plain, quoted, reordered, frozen, other + plain):
        assert _precommit_revs(text, url) == ["0.17.4"], text
    assert _precommit_revs(plain + f"  - repo: {url}\n    rev: v0.18.0\n", url) == [
        "0.17.4",
        "0.18.0",
    ]
    assert _precommit_revs(other, url) == []
