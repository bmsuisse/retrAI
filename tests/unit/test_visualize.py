"""Tests for retrai.tools.visualize."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from retrai.tools.visualize import VALID_CHART_TYPES, _build_chart_code, visualize

# ---------------------------------------------------------------------------
# _build_chart_code tests
# ---------------------------------------------------------------------------

class TestBuildChartCode:
    """Test code generation for each chart type."""

    @pytest.mark.parametrize("chart_type", sorted(VALID_CHART_TYPES))
    def test_generates_code_for_all_chart_types(self, chart_type: str) -> None:
        code = _build_chart_code(
            file_path="/data/test.csv",
            chart_type=chart_type,
            x_column="col_a",
            y_column="col_b",
            title="Test Chart",
            output_path="/tmp/chart.png",
            style="ggplot",
        )
        assert "import pandas" in code
        assert "import matplotlib" in code
        assert "import seaborn" in code
        assert "savefig" in code
        assert "json.dumps" in code

    def test_includes_file_path(self) -> None:
        code = _build_chart_code(
            file_path="/data/sample.csv",
            chart_type="scatter",
            x_column=None,
            y_column=None,
            title=None,
            output_path="/out/chart.png",
            style="ggplot",
        )
        assert "/data/sample.csv" in code

    def test_includes_output_path(self) -> None:
        code = _build_chart_code(
            file_path="/x.csv",
            chart_type="histogram",
            x_column="age",
            y_column=None,
            title="Age Distribution",
            output_path="/plots/age_hist.png",
            style="ggplot",
        )
        assert "/plots/age_hist.png" in code

    def test_scatter_uses_columns(self) -> None:
        code = _build_chart_code(
            file_path="/x.csv",
            chart_type="scatter",
            x_column="height",
            y_column="weight",
            title="H vs W",
            output_path="/out.png",
            style="ggplot",
        )
        assert "scatterplot" in code

    def test_heatmap_uses_correlation(self) -> None:
        code = _build_chart_code(
            file_path="/x.csv",
            chart_type="heatmap",
            x_column=None,
            y_column=None,
            title="Heatmap",
            output_path="/out.png",
            style="ggplot",
        )
        assert "heatmap" in code
        assert "corr()" in code

    def test_correlation_matrix_uses_mask(self) -> None:
        code = _build_chart_code(
            file_path="/x.csv",
            chart_type="correlation_matrix",
            x_column=None,
            y_column=None,
            title="Corr",
            output_path="/out.png",
            style="ggplot",
        )
        assert "triu" in code
        assert "heatmap" in code


# ---------------------------------------------------------------------------
# visualize() async tests
# ---------------------------------------------------------------------------

class TestVisualize:
    """Test the async visualize() function."""

    @pytest.mark.asyncio
    async def test_invalid_chart_type_returns_error(self) -> None:
        result = await visualize(
            file_path="/data.csv",
            chart_type="pie_3d",
            cwd="/project",
        )
        parsed = json.loads(result)
        assert "error" in parsed
        assert "pie_3d" in parsed["error"]

    @pytest.mark.asyncio
    async def test_valid_chart_type_calls_python_exec(self) -> None:
        mock_result = MagicMock()
        mock_result.timed_out = False
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "chart_type": "scatter",
            "output_path": "/out/chart.png",
            "columns_used": ["x", "y"],
            "rows": 100,
            "title": "Test",
        })

        with patch(
            "retrai.tools.visualize.python_exec",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            result = await visualize(
                file_path="/data.csv",
                chart_type="scatter",
                cwd="/project",
                x_column="x",
                y_column="y",
                title="Test",
            )
            mock_exec.assert_called_once()
            parsed = json.loads(result)
            assert parsed["chart_type"] == "scatter"
            assert parsed["rows"] == 100

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self) -> None:
        mock_result = MagicMock()
        mock_result.timed_out = True

        with patch(
            "retrai.tools.visualize.python_exec",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await visualize(
                file_path="/data.csv",
                chart_type="bar",
                cwd="/project",
            )
            parsed = json.loads(result)
            assert "timed out" in parsed["error"]

    @pytest.mark.asyncio
    async def test_nonzero_exit_returns_error(self) -> None:
        mock_result = MagicMock()
        mock_result.timed_out = False
        mock_result.returncode = 1
        mock_result.stderr = "ModuleNotFoundError: No module named 'pandas'"

        with patch(
            "retrai.tools.visualize.python_exec",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await visualize(
                file_path="/data.csv",
                chart_type="histogram",
                cwd="/project",
            )
            parsed = json.loads(result)
            assert "error" in parsed
            assert "exit 1" in parsed["error"]

    @pytest.mark.asyncio
    async def test_default_output_path_generated(self) -> None:
        mock_result = MagicMock()
        mock_result.timed_out = False
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"chart_type": "line"})

        with patch(
            "retrai.tools.visualize.python_exec",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            await visualize(
                file_path="/data.csv",
                chart_type="line",
                cwd="/project",
            )
            # Check that code was called with a default path
            call_kwargs = mock_exec.call_args
            code = call_kwargs.kwargs.get("code", call_kwargs[1].get("code", ""))
            assert ".retrai/charts/" in code

    @pytest.mark.asyncio
    async def test_custom_output_path_used(self) -> None:
        mock_result = MagicMock()
        mock_result.timed_out = False
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"chart_type": "boxplot"})

        with patch(
            "retrai.tools.visualize.python_exec",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            await visualize(
                file_path="/data.csv",
                chart_type="boxplot",
                cwd="/project",
                output_path="/custom/my_chart.png",
            )
            call_kwargs = mock_exec.call_args
            code = call_kwargs.kwargs.get("code", call_kwargs[1].get("code", ""))
            assert "/custom/my_chart.png" in code

    @pytest.mark.asyncio
    async def test_all_valid_chart_types_constant(self) -> None:
        assert "scatter" in VALID_CHART_TYPES
        assert "bar" in VALID_CHART_TYPES
        assert "histogram" in VALID_CHART_TYPES
        assert "heatmap" in VALID_CHART_TYPES
        assert "boxplot" in VALID_CHART_TYPES
        assert "line" in VALID_CHART_TYPES
        assert "correlation_matrix" in VALID_CHART_TYPES
        assert len(VALID_CHART_TYPES) == 7
