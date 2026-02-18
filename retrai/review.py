"""AI-powered code review of git diffs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReviewFinding:
    """A single finding from the code review."""

    category: str  # "bug" | "issue" | "suggestion" | "praise"
    severity: str  # "critical" | "warning" | "info"
    file: str
    line: int | None
    message: str
    suggestion: str = ""

    @property
    def icon(self) -> str:
        return {
            "bug": "🐛",
            "issue": "⚠️",
            "suggestion": "💡",
            "praise": "✅",
        }.get(self.category, "•")


@dataclass
class ReviewResult:
    """Complete code review result."""

    findings: list[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    score: int = 0  # 0-100 quality score
    model_name: str = ""

    @property
    def bugs(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.category == "bug"]

    @property
    def issues(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.category == "issue"]

    @property
    def suggestions(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.category == "suggestion"]

    @property
    def praises(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.category == "praise"]


async def run_review(
    cwd: str,
    model_name: str = "claude-sonnet-4-6",
    staged: bool = False,
) -> ReviewResult:
    """Run an AI-powered code review on the current diff.

    Args:
        cwd: Project directory.
        model_name: LLM model to use.
        staged: If True, review only staged changes.

    Returns:
        ReviewResult with categorized findings.
    """
    from langchain_core.messages import HumanMessage

    from retrai.llm.factory import get_llm
    from retrai.tools.git_diff import git_diff

    diff_text = await git_diff(cwd=cwd, staged=staged)
    if not diff_text.strip():
        return ReviewResult(
            summary="No changes to review.",
            score=100,
            model_name=model_name,
        )

    prompt = f"""You are a senior software engineer performing a code review.
Review the following diff and provide structured feedback.

## Diff
```diff
{diff_text[:8000]}
```

## Instructions
Analyze the changes for:
1. **Bugs**: Logic errors, null pointer issues, race conditions, security flaws
2. **Issues**: Bad patterns, performance problems, missing error handling
3. **Suggestions**: Improvements, better naming, refactoring opportunities
4. **Praise**: Well-written code, good patterns, smart solutions

Respond with a JSON object:
```json
{{
  "summary": "Brief overall assessment (1-2 sentences)",
  "score": 85,
  "findings": [
    {{
      "category": "bug",
      "severity": "critical",
      "file": "src/auth.py",
      "line": 42,
      "message": "SQL injection vulnerability in user query",
      "suggestion": "Use parameterized queries instead"
    }}
  ]
}}
```

Rules:
- Score 0-100 (100 = perfect, 70+ = good, <50 = needs work)
- Be specific about file names and line numbers when possible
- Include at least one praise if anything is done well
- severity: "critical" | "warning" | "info"
- Line can be null if it applies to the whole file

Respond with ONLY the JSON object."""

    try:
        llm = get_llm(model_name, temperature=0.1)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = str(response.content).strip()

        # Strip markdown fences
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)

        findings = []
        for f in data.get("findings", []):
            findings.append(
                ReviewFinding(
                    category=f.get("category", "issue"),
                    severity=f.get("severity", "info"),
                    file=f.get("file", ""),
                    line=f.get("line"),
                    message=f.get("message", ""),
                    suggestion=f.get("suggestion", ""),
                )
            )

        return ReviewResult(
            findings=findings,
            summary=data.get("summary", "Review complete."),
            score=int(data.get("score", 50)),
            model_name=model_name,
        )

    except Exception as e:
        logger.error("Code review failed: %s", e)
        return ReviewResult(
            summary=f"Review failed: {e}",
            score=0,
            model_name=model_name,
        )


def format_review_markdown(result: ReviewResult) -> str:
    """Format ReviewResult as a markdown report."""
    lines = [
        "# Code Review Report",
        "",
        f"**Score**: {result.score}/100",
        f"**Model**: {result.model_name}",
        "",
        "## Summary",
        f"{result.summary}",
        "",
    ]

    for category, title in [
        ("bug", "🐛 Bugs"),
        ("issue", "⚠️ Issues"),
        ("suggestion", "💡 Suggestions"),
        ("praise", "✅ Praise"),
    ]:
        items = [f for f in result.findings if f.category == category]
        if items:
            lines.append(f"## {title}")
            lines.append("")
            for f in items:
                loc = f"{f.file}"
                if f.line:
                    loc += f":{f.line}"
                lines.append(f"### `{loc}` [{f.severity}]")
                lines.append(f"{f.message}")
                if f.suggestion:
                    lines.append("")
                    lines.append(f"> 💡 {f.suggestion}")
                lines.append("")

    return "\n".join(lines)
