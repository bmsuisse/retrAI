"""Planning agent: generates an AI eval harness from a natural-language description."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


async def generate_eval_harness(
    description: str,
    cwd: str,
    model_name: str = "claude-sonnet-4-6",
) -> Path:
    """Generate a pytest eval harness for the given description.

    Reads project context (file listing + key files), calls the LLM once,
    writes the harness to .retrai/eval_harness.py, saves metadata to
    .retrai/ai_eval_config.json, and returns the harness path.
    """
    root = Path(cwd)
    retrai_dir = root / ".retrai"
    retrai_dir.mkdir(parents=True, exist_ok=True)

    context = _build_project_context(root)
    prompt = _build_planner_prompt(description, context)

    harness_code = await _call_llm(prompt, model_name)

    harness_path = retrai_dir / "eval_harness.py"
    harness_path.write_text(harness_code)

    meta = {
        "description": description,
        "harness_file": str(harness_path.relative_to(root)),
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model_name,
    }
    (retrai_dir / "ai_eval_config.json").write_text(json.dumps(meta, indent=2))

    return harness_path


def _build_project_context(root: Path) -> str:
    """Build a compact project context string for the planner prompt."""
    lines: list[str] = []

    # File listing (top 2 levels, skip noise)
    lines.append("## Project files")
    skip = {".git", "__pycache__", "node_modules", ".venv", "dist", "build", ".retrai"}
    for item in sorted(root.iterdir()):
        if item.name in skip:
            continue
        if item.is_dir():
            lines.append(f"  {item.name}/")
            for sub in sorted(item.iterdir())[:20]:
                if sub.name not in skip and not sub.name.startswith("."):
                    lines.append(f"    {sub.name}")
        else:
            lines.append(f"  {item.name}")

    # Read key config files
    key_files = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "README.md",
    ]
    for fname in key_files:
        p = root / fname
        if p.exists():
            content = p.read_text(errors="replace")[:2000]
            lines.append(f"\n## {fname}\n```\n{content}\n```")

    # Read main source files (Python: up to 5 .py files, first 150 lines each)
    py_files = sorted(root.rglob("*.py"))
    py_files = [
        f
        for f in py_files
        if not any(part in skip for part in f.parts)
        and "test" not in f.name.lower()
        and "__" not in f.name
    ]
    for pf in py_files[:5]:
        rel = pf.relative_to(root)
        content_lines = pf.read_text(errors="replace").splitlines()[:150]
        content = "\n".join(content_lines)
        lines.append(f"\n## {rel}\n```python\n{content}\n```")

    return "\n".join(lines)


def _build_planner_prompt(description: str, context: str) -> str:
    return f"""You are an expert software testing agent. Your job is to write a pytest test file
that verifies the following requirement:

**REQUIREMENT**: {description}

Here is the project context:

{context}

---

Write a complete, runnable pytest file that:
1. Tests ONLY the specific requirement above — no extra tests
2. Imports from the actual project source files (use relative imports or package imports)
3. Has clear test function names that describe what is being checked
4. Includes any necessary fixtures or helpers
5. Uses `assert` statements with helpful failure messages
6. Is self-contained — does not require manual setup beyond `pip install -e .` or equivalent

Respond with ONLY the Python source code for the test file, no markdown fences, no explanation.
Start directly with the imports or docstring.
"""


async def _call_llm(prompt: str, model_name: str) -> str:
    """Call the LLM and return the generated harness code."""
    from langchain_core.messages import HumanMessage

    from retrai.llm.factory import get_llm

    llm = get_llm(model_name, temperature=0.2)
    response = await llm.ainvoke([HumanMessage(content=prompt)])

    content = str(response.content)

    # Strip markdown code fences if the model wrapped the output
    if content.startswith("```python"):
        content = content[len("```python") :].lstrip("\n")
    elif content.startswith("```"):
        content = content[3:].lstrip("\n")
    if content.endswith("```"):
        content = content[:-3].rstrip()

    # Ensure file ends with newline
    if not content.endswith("\n"):
        content += "\n"

    return content
