"""Tests for the Code Review module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from retrai.review import (
    ReviewFinding,
    ReviewResult,
    format_review_markdown,
    run_review,
)

# ---------------------------------------------------------------------------
# ReviewFinding
# ---------------------------------------------------------------------------


class TestReviewFinding:
    def test_icon_bug(self):
        f = ReviewFinding("bug", "critical", "src/auth.py", 42, "SQL injection")
        assert f.icon == "🐛"

    def test_icon_suggestion(self):
        f = ReviewFinding("suggestion", "info", "utils.py", None, "Rename var")
        assert f.icon == "💡"

    def test_icon_praise(self):
        f = ReviewFinding("praise", "info", "core.py", 10, "Good pattern")
        assert f.icon == "✅"

    def test_icon_issue(self):
        f = ReviewFinding("issue", "warning", "api.py", 5, "Missing error handling")
        assert f.icon == "⚠️"


# ---------------------------------------------------------------------------
# ReviewResult
# ---------------------------------------------------------------------------


class TestReviewResult:
    def test_empty(self):
        r = ReviewResult()
        assert r.bugs == []
        assert r.issues == []
        assert r.suggestions == []
        assert r.praises == []

    def test_categorized(self):
        r = ReviewResult(
            findings=[
                ReviewFinding("bug", "critical", "a.py", 1, "Bug 1"),
                ReviewFinding("bug", "warning", "b.py", 2, "Bug 2"),
                ReviewFinding("issue", "warning", "c.py", 3, "Issue 1"),
                ReviewFinding("suggestion", "info", "d.py", 4, "Suggestion 1"),
                ReviewFinding("praise", "info", "e.py", 5, "Praise 1"),
            ],
            score=75,
        )
        assert len(r.bugs) == 2
        assert len(r.issues) == 1
        assert len(r.suggestions) == 1
        assert len(r.praises) == 1


# ---------------------------------------------------------------------------
# format_review_markdown
# ---------------------------------------------------------------------------


class TestFormatReview:
    def test_empty_review(self):
        r = ReviewResult(summary="No issues", score=100, model_name="test")
        md = format_review_markdown(r)
        assert "Code Review Report" in md
        assert "100" in md
        assert "No issues" in md

    def test_with_findings(self):
        r = ReviewResult(
            findings=[
                ReviewFinding(
                    "bug",
                    "critical",
                    "auth.py",
                    42,
                    "SQL injection",
                    "Use parameterized queries",
                ),
            ],
            summary="Found a critical bug",
            score=30,
            model_name="test-model",
        )
        md = format_review_markdown(r)
        assert "auth.py:42" in md
        assert "SQL injection" in md
        assert "parameterized queries" in md
        assert "30" in md


# ---------------------------------------------------------------------------
# run_review (mocked LLM)
# ---------------------------------------------------------------------------


class TestRunReview:
    @pytest.mark.asyncio
    async def test_no_changes(self):
        with patch("retrai.tools.git_diff.git_diff", new_callable=AsyncMock) as mock_diff:
            mock_diff.return_value = ""
            result = await run_review(cwd="/tmp", model_name="test")
            assert result.score == 100
            assert "No changes" in result.summary

    @pytest.mark.asyncio
    async def test_llm_review(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content='{"summary": "Looks good", "score": 85, "findings": '
            '[{"category": "praise", "severity": "info", "file": "main.py", '
            '"line": 1, "message": "Clean code"}]}'
        )

        with (
            patch("retrai.tools.git_diff.git_diff", new_callable=AsyncMock) as mock_diff,
            patch("retrai.llm.factory.get_llm", return_value=mock_llm),
        ):
            mock_diff.return_value = "diff --git a/main.py\n+hello"
            result = await run_review(cwd="/tmp", model_name="test")
            assert result.score == 85
            assert len(result.findings) == 1
            assert result.findings[0].category == "praise"
