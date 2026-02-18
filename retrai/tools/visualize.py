"""Visualization tool — generate charts from data files via sandbox."""

from __future__ import annotations

import json
import logging
import textwrap
from pathlib import Path
from time import strftime

from retrai.tools.python_exec import python_exec

logger = logging.getLogger(__name__)

VALID_CHART_TYPES = frozenset(
    {
        "scatter",
        "bar",
        "histogram",
        "heatmap",
        "boxplot",
        "line",
        "correlation_matrix",
    }
)


async def visualize(
    file_path: str,
    chart_type: str,
    cwd: str,
    x_column: str | None = None,
    y_column: str | None = None,
    title: str | None = None,
    output_path: str | None = None,
    style: str = "seaborn-v0_8-darkgrid",
) -> str:
    """Generate a chart from a data file and save as PNG.

    Args:
        file_path: Path to CSV/JSON/Excel data file.
        chart_type: One of scatter, bar, histogram, heatmap,
                    boxplot, line, correlation_matrix.
        cwd: Working directory.
        x_column: Column for x-axis (required for scatter, bar, line).
        y_column: Column for y-axis (required for scatter, line).
        title: Chart title (auto-generated if omitted).
        output_path: Where to save PNG (defaults to .retrai/charts/).
        style: Matplotlib style (default seaborn-v0_8-darkgrid).

    Returns:
        JSON string with chart metadata and output path.
    """
    chart_type = chart_type.lower().strip()

    if chart_type not in VALID_CHART_TYPES:
        return json.dumps(
            {
                "error": (
                    f"Unknown chart type '{chart_type}'. "
                    f"Valid: {', '.join(sorted(VALID_CHART_TYPES))}"
                ),
            }
        )

    # Build default output path
    if not output_path:
        ts = strftime("%Y%m%d_%H%M%S")
        charts_dir = str(Path(cwd) / ".retrai" / "charts")
        output_path = f"{charts_dir}/{ts}_{chart_type}.png"

    code = _build_chart_code(
        file_path=file_path,
        chart_type=chart_type,
        x_column=x_column,
        y_column=y_column,
        title=title,
        output_path=output_path,
        style=style,
    )

    result = await python_exec(
        code=code,
        cwd=cwd,
        packages=["matplotlib", "seaborn", "pandas", "numpy"],
        timeout=60.0,
    )

    if result.timed_out:
        return json.dumps({"error": "Chart generation timed out (60s)"})

    if result.returncode != 0:
        return json.dumps(
            {
                "error": f"Chart generation failed (exit {result.returncode})",
                "stderr": result.stderr[:2000],
            }
        )

    stdout = result.stdout.strip()
    try:
        parsed = json.loads(stdout)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        return json.dumps(
            {
                "chart_type": chart_type,
                "output_path": output_path,
                "raw_output": stdout[:2000],
            }
        )


def _build_chart_code(
    file_path: str,
    chart_type: str,
    x_column: str | None,
    y_column: str | None,
    title: str | None,
    output_path: str,
    style: str,
) -> str:
    """Build Python code to generate the requested chart."""

    # Data loading preamble (handles CSV, JSON, Excel)
    data_load = textwrap.dedent(f"""\
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import seaborn as sns
        import numpy as np
        import json
        from pathlib import Path

        # Load data
        fpath = {file_path!r}
        if fpath.endswith('.csv'):
            df = pd.read_csv(fpath)
        elif fpath.endswith('.json') or fpath.endswith('.jsonl'):
            df = pd.read_json(fpath)
        elif fpath.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(fpath)
        else:
            df = pd.read_csv(fpath)  # Default to CSV

        # Ensure output directory exists
        out_path = {output_path!r}
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        # Apply style
        try:
            plt.style.use({style!r})
        except OSError:
            plt.style.use('ggplot')

        fig, ax = plt.subplots(figsize=(10, 6))
    """)

    auto_title = title or f"{chart_type.replace('_', ' ').title()}"

    chart_code: dict[str, str] = {
        "scatter": textwrap.dedent(f"""\
            x_col = {x_column!r} or df.columns[0]
            y_col = {y_column!r} or df.columns[1]
            sns.scatterplot(data=df, x=x_col, y=y_col, ax=ax, alpha=0.7)
            ax.set_title({auto_title!r})
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            cols_used = [x_col, y_col]
        """),
        "bar": textwrap.dedent(f"""\
            x_col = {x_column!r} or df.columns[0]
            y_col = {y_column!r}
            if y_col:
                sns.barplot(data=df, x=x_col, y=y_col, ax=ax)
            else:
                df[x_col].value_counts().head(20).plot.bar(ax=ax)
            ax.set_title({auto_title!r})
            plt.xticks(rotation=45, ha='right')
            cols_used = [x_col] + ([y_col] if y_col else [])
        """),
        "histogram": textwrap.dedent(f"""\
            col = {x_column!r} or df.select_dtypes(
                include='number'
            ).columns[0]
            sns.histplot(data=df, x=col, kde=True, ax=ax, bins=30)
            ax.set_title({auto_title!r})
            ax.set_xlabel(col)
            cols_used = [col]
        """),
        "heatmap": textwrap.dedent(f"""\
            numeric = df.select_dtypes(include='number')
            corr = numeric.corr()
            sns.heatmap(
                corr, annot=True, fmt='.2f', cmap='RdBu_r',
                center=0, square=True, ax=ax,
            )
            ax.set_title({auto_title!r})
            cols_used = list(numeric.columns)
        """),
        "boxplot": textwrap.dedent(f"""\
            col = {x_column!r}
            group = {y_column!r}
            if col and group:
                sns.boxplot(data=df, x=group, y=col, ax=ax)
            elif col:
                sns.boxplot(data=df, y=col, ax=ax)
            else:
                numeric_cols = df.select_dtypes(
                    include='number'
                ).columns[:8]
                df[numeric_cols].plot.box(ax=ax)
            ax.set_title({auto_title!r})
            plt.xticks(rotation=45, ha='right')
            cols_used = [c for c in [col, group] if c]
            if not cols_used:
                cols_used = list(
                    df.select_dtypes(include='number').columns[:8]
                )
        """),
        "line": textwrap.dedent(f"""\
            x_col = {x_column!r} or df.columns[0]
            y_col = {y_column!r} or df.select_dtypes(
                include='number'
            ).columns[0]
            sns.lineplot(data=df, x=x_col, y=y_col, ax=ax)
            ax.set_title({auto_title!r})
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            cols_used = [x_col, y_col]
        """),
        "correlation_matrix": textwrap.dedent(f"""\
            numeric = df.select_dtypes(include='number')
            corr = numeric.corr()
            mask = np.triu(np.ones_like(corr, dtype=bool))
            sns.heatmap(
                corr, mask=mask, annot=True, fmt='.2f',
                cmap='coolwarm', center=0, square=True, ax=ax,
                linewidths=0.5,
            )
            ax.set_title({auto_title!r})
            cols_used = list(numeric.columns)
        """),
    }

    code = chart_code.get(chart_type, "cols_used = []")

    return (
        data_load
        + code
        + textwrap.dedent(f"""\

        plt.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        result = {{
            "chart_type": {chart_type!r},
            "output_path": out_path,
            "columns_used": cols_used,
            "rows": len(df),
            "title": {auto_title!r},
        }}
        print(json.dumps(result))
    """)
    )
