"""Data analysis tool — statistical analysis on CSV/JSON data."""

from __future__ import annotations

import json
import logging
import textwrap

from retrai.tools.python_exec import python_exec

logger = logging.getLogger(__name__)


async def data_analysis(
    file_path: str,
    cwd: str,
    analysis_type: str = "summary",
) -> str:
    """Analyze a CSV or JSON data file in the sandbox.

    Args:
        file_path: Path to the data file (relative to cwd).
        cwd: Working directory.
        analysis_type: One of "summary", "correlations", "quality", "distribution".

    Returns:
        JSON string with analysis results.
    """
    analysis_type = analysis_type.lower().strip()

    if analysis_type == "summary":
        code = _build_summary_code(file_path)
    elif analysis_type == "correlations":
        code = _build_correlation_code(file_path)
    elif analysis_type == "quality":
        code = _build_quality_code(file_path)
    elif analysis_type == "distribution":
        code = _build_distribution_code(file_path)
    else:
        return json.dumps({
            "error": f"Unknown analysis_type '{analysis_type}'. "
                     "Use: summary, correlations, quality, distribution",
        })

    result = await python_exec(
        code=code,
        cwd=cwd,
        packages=["pandas"],
        timeout=60.0,
    )

    if result.timed_out:
        return json.dumps({"error": "Analysis timed out (60s limit)"})

    if result.returncode != 0:
        return json.dumps({
            "error": f"Analysis failed (exit {result.returncode})",
            "stderr": result.stderr[:2000],
        })

    # Parse the JSON output from the sandbox
    stdout = result.stdout.strip()
    try:
        # The sandbox prints JSON to stdout
        parsed = json.loads(stdout)
        return json.dumps(parsed, indent=2, default=str)
    except json.JSONDecodeError:
        return json.dumps({
            "analysis_type": analysis_type,
            "raw_output": stdout[:4000],
        })


def _build_summary_code(file_path: str) -> str:
    """Build Python code for summary statistics."""
    return textwrap.dedent(f"""\
        import json
        import pandas as pd

        path = {file_path!r}
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        elif path.endswith(".json") or path.endswith(".jsonl"):
            df = pd.read_json(path, lines=path.endswith(".jsonl"))
        elif path.endswith(".xlsx") or path.endswith(".xls"):
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)

        result = {{
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {{col: str(dtype) for col, dtype in df.dtypes.items()}},
            "missing": {{col: int(v) for col, v in df.isnull().sum().items() if v > 0}},
            "missing_pct": {{
                col: round(v / len(df) * 100, 1)
                for col, v in df.isnull().sum().items() if v > 0
            }},
        }}

        # Numeric summary
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            desc = df[numeric_cols].describe()
            result["numeric_summary"] = json.loads(desc.to_json())

        # Categorical summary
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        if cat_cols:
            cat_info = {{}}
            for col in cat_cols[:10]:
                vc = df[col].value_counts().head(5)
                cat_info[col] = {{
                    "unique": int(df[col].nunique()),
                    "top_values": {{str(k): int(v) for k, v in vc.items()}},
                }}
            result["categorical_summary"] = cat_info

        print(json.dumps(result, default=str))
    """)


def _build_correlation_code(file_path: str) -> str:
    """Build Python code for correlation analysis."""
    return textwrap.dedent(f"""\
        import json
        import pandas as pd

        path = {file_path!r}
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        elif path.endswith(".json") or path.endswith(".jsonl"):
            df = pd.read_json(path, lines=path.endswith(".jsonl"))
        else:
            df = pd.read_csv(path)

        numeric_df = df.select_dtypes(include="number")
        if numeric_df.empty:
            print(json.dumps({{"error": "No numeric columns found"}}))
        else:
            corr = numeric_df.corr()

            # Find strong correlations (|r| > 0.5, excluding self)
            strong = []
            for i in range(len(corr.columns)):
                for j in range(i + 1, len(corr.columns)):
                    r = corr.iloc[i, j]
                    if abs(r) > 0.5:
                        strong.append({{
                            "col1": corr.columns[i],
                            "col2": corr.columns[j],
                            "correlation": round(float(r), 4),
                        }})

            strong.sort(key=lambda x: abs(x["correlation"]), reverse=True)

            result = {{
                "correlation_matrix": json.loads(corr.to_json()),
                "strong_correlations": strong[:20],
                "num_columns": len(numeric_df.columns),
            }}
            print(json.dumps(result, default=str))
    """)


def _build_quality_code(file_path: str) -> str:
    """Build Python code for data quality report."""
    return textwrap.dedent(f"""\
        import json
        import pandas as pd

        path = {file_path!r}
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        elif path.endswith(".json") or path.endswith(".jsonl"):
            df = pd.read_json(path, lines=path.endswith(".jsonl"))
        else:
            df = pd.read_csv(path)

        result = {{
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            "duplicate_rows": int(df.duplicated().sum()),
            "complete_rows": int(df.dropna().shape[0]),
            "completeness_pct": (
                round(df.dropna().shape[0] / len(df) * 100, 1)
                if len(df) > 0 else 0
            ),
        }}

        # Per-column quality
        col_quality = {{}}
        for col in df.columns:
            info = {{
                "dtype": str(df[col].dtype),
                "missing": int(df[col].isnull().sum()),
                "missing_pct": (
                    round(df[col].isnull().sum() / len(df) * 100, 1)
                    if len(df) > 0 else 0
                ),
                "unique": int(df[col].nunique()),
                "unique_pct": (
                    round(df[col].nunique() / len(df) * 100, 1)
                    if len(df) > 0 else 0
                ),
            }}
            if df[col].dtype in ["float64", "int64"]:
                info["zeros"] = int((df[col] == 0).sum())
                info["negatives"] = int((df[col] < 0).sum())
            col_quality[col] = info

        result["columns"] = col_quality

        # Issues detected
        issues = []
        for col, info in col_quality.items():
            if info["missing_pct"] > 50:
                issues.append(f"{{col}}: {{info['missing_pct']}}% missing")
            if info["unique"] == 1:
                issues.append(f"{{col}}: constant value (only 1 unique)")
            if info["unique_pct"] == 100 and len(df) > 10:
                issues.append(f"{{col}}: all unique (possible ID column)")

        if result["duplicate_rows"] > 0:
            issues.append(f"{{result['duplicate_rows']}} duplicate rows found")

        result["issues"] = issues

        print(json.dumps(result, default=str))
    """)


def _build_distribution_code(file_path: str) -> str:
    """Build Python code for value distribution analysis."""
    return textwrap.dedent(f"""\
        import json
        import pandas as pd

        path = {file_path!r}
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        elif path.endswith(".json") or path.endswith(".jsonl"):
            df = pd.read_json(path, lines=path.endswith(".jsonl"))
        else:
            df = pd.read_csv(path)

        result = {{"columns": {{}}}}

        for col in df.columns[:20]:
            col_info = {{"dtype": str(df[col].dtype)}}

            if df[col].dtype in ["float64", "int64"]:
                not_null = not df[col].isnull().all()
                col_info["min"] = float(df[col].min()) if not_null else None
                col_info["max"] = float(df[col].max()) if not_null else None
                col_info["mean"] = (
                    round(float(df[col].mean()), 4) if not_null else None
                )
                col_info["median"] = (
                    float(df[col].median()) if not_null else None
                )
                col_info["std"] = (
                    round(float(df[col].std()), 4) if not_null else None
                )
                col_info["skewness"] = (
                    round(float(df[col].skew()), 4) if not_null else None
                )

                # Histogram bins
                try:
                    counts, edges = pd.cut(df[col].dropna(), bins=10, retbins=True)
                    hist = counts.value_counts().sort_index()
                    col_info["histogram"] = [
                        {{"range": str(interval), "count": int(count)}}
                        for interval, count in hist.items()
                    ]
                except Exception:
                    pass
            else:
                vc = df[col].value_counts().head(15)
                col_info["top_values"] = {{str(k): int(v) for k, v in vc.items()}}
                col_info["unique_count"] = int(df[col].nunique())

            result["columns"][col] = col_info

        print(json.dumps(result, default=str))
    """)
