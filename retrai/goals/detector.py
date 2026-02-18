"""Auto-detect the appropriate goal for a project directory."""

from __future__ import annotations

import json
from pathlib import Path


def detect_goal(cwd: str) -> str | None:
    """Scan project files and return the best matching goal name.

    Detection priority (first match wins):
    1. .retrai.yml present → "shell-goal" (user already configured it)
    2. pyproject.toml / setup.cfg with pytest → "pytest"
    3. pyproject.toml with pyright only → "pyright"
    4. Cargo.toml → "cargo-test"
    5. go.mod → "go-test"
    6. package.json + bun.lock → "bun-test"
    7. package.json + jest/vitest in deps → "npm-test"
    8. Makefile with test target → "make-test"
    9. None (caller must handle)
    """
    root = Path(cwd)

    # 1. User has a .retrai.yml — they explicitly configured shell-goal
    if (root / ".retrai.yml").exists():
        return "shell-goal"

    # 2. Python project with pytest
    if _has_pytest(root):
        return "pytest"

    # 3. Python project with pyright (but no pytest)
    if _has_pyright(root):
        return "pyright"

    # 4. Rust project
    if (root / "Cargo.toml").exists():
        return "cargo-test"

    # 5. Go project
    if (root / "go.mod").exists():
        return "go-test"

    # 6. JavaScript with bun
    if (root / "package.json").exists() and (root / "bun.lock").exists():
        return "bun-test"

    # 7. JavaScript with Jest / Vitest via npm
    if (root / "package.json").exists():
        goal = _detect_npm_goal(root)
        if goal:
            return goal

    # 8. Makefile with a test target
    if _has_make_test_target(root):
        return "make-test"

    return None


def detect_research_goal(description: str) -> bool:
    """Return True if the description hints at a research task."""
    research_keywords = {
        "research", "investigate", "study", "scientific",
        "literature review", "hypothesis", "experiment",
        "analyze data", "statistical analysis", "pubmed",
        "arxiv", "dataset", "correlation", "p-value",
    }
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in research_keywords)


def _has_pytest(root: Path) -> bool:
    """Return True if the project uses pytest."""
    pyproject = root / "pyproject.toml"
    setup_cfg = root / "setup.cfg"
    pytest_ini = root / "pytest.ini"
    conftest = root / "conftest.py"

    if pytest_ini.exists() or conftest.exists():
        return True

    if pyproject.exists():
        content = pyproject.read_text(errors="replace")
        if "[tool.pytest" in content or "pytest" in content.lower():
            return True

    if setup_cfg.exists():
        content = setup_cfg.read_text(errors="replace")
        if "[tool:pytest]" in content:
            return True

    # Check for tests/ directory
    if (root / "tests").is_dir() or (root / "test").is_dir():
        return True

    return False


def _has_pyright(root: Path) -> bool:
    """Return True if the project has pyright configured."""
    if (root / "pyrightconfig.json").exists():
        return True
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(errors="replace")
        if "[tool.pyright]" in content:
            return True
    return False


def _detect_npm_goal(root: Path) -> str | None:
    """Detect npm/jest/vitest from package.json."""
    try:
        pkg = json.loads((root / "package.json").read_text())
    except (json.JSONDecodeError, OSError):
        return None

    all_deps: dict = {}
    all_deps.update(pkg.get("dependencies", {}))
    all_deps.update(pkg.get("devDependencies", {}))
    scripts: dict = pkg.get("scripts", {})

    if "jest" in all_deps or "vitest" in all_deps:
        return "npm-test"

    if "test" in scripts:
        test_script = scripts["test"].lower()
        if "jest" in test_script or "vitest" in test_script or "mocha" in test_script:
            return "npm-test"

    return None


def _has_make_test_target(root: Path) -> bool:
    """Return True if the Makefile has a 'test' target."""
    makefile = root / "Makefile"
    if not makefile.exists():
        return False
    content = makefile.read_text(errors="replace")
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("test:") or stripped.startswith("test "):
            return True
    return False
