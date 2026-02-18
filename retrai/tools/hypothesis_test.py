"""Hypothesis testing tool — statistical tests via sandbox."""

from __future__ import annotations

import json
import logging
import textwrap

from retrai.tools.python_exec import python_exec

logger = logging.getLogger(__name__)


async def hypothesis_test(
    test_type: str,
    cwd: str,
    data1: list[float] | None = None,
    data2: list[float] | None = None,
    data_file: str | None = None,
    column1: str | None = None,
    column2: str | None = None,
    alpha: float = 0.05,
) -> str:
    """Run a statistical hypothesis test.

    Args:
        test_type: One of "ttest", "ttest_paired", "ttest_1samp",
                   "chi2", "mann_whitney", "anova", "shapiro", "pearson".
        cwd: Working directory.
        data1: First data sample (list of numbers).
        data2: Second data sample (list of numbers, for two-sample tests).
        data_file: Path to CSV file (alternative to inline data).
        column1: Column name from CSV for first sample.
        column2: Column name from CSV for second sample.
        alpha: Significance level (default 0.05).

    Returns:
        JSON string with test results including statistic, p-value,
        effect size, and interpretation.
    """
    test_type = test_type.lower().strip()

    valid_tests = {
        "ttest", "ttest_paired", "ttest_1samp",
        "chi2", "mann_whitney", "anova",
        "shapiro", "pearson",
    }
    if test_type not in valid_tests:
        return json.dumps({
            "error": f"Unknown test '{test_type}'. Valid: {', '.join(sorted(valid_tests))}",
        })

    code = _build_test_code(
        test_type=test_type,
        data1=data1,
        data2=data2,
        data_file=data_file,
        column1=column1,
        column2=column2,
        alpha=alpha,
    )

    result = await python_exec(
        code=code,
        cwd=cwd,
        packages=["scipy", "pandas", "numpy"],
        timeout=60.0,
    )

    if result.timed_out:
        return json.dumps({"error": "Test timed out (60s limit)"})

    if result.returncode != 0:
        return json.dumps({
            "error": f"Test failed (exit {result.returncode})",
            "stderr": result.stderr[:2000],
        })

    stdout = result.stdout.strip()
    try:
        parsed = json.loads(stdout)
        return json.dumps(parsed, indent=2, default=str)
    except json.JSONDecodeError:
        return json.dumps({
            "test_type": test_type,
            "raw_output": stdout[:4000],
        })


def _build_test_code(
    test_type: str,
    data1: list[float] | None,
    data2: list[float] | None,
    data_file: str | None,
    column1: str | None,
    column2: str | None,
    alpha: float,
) -> str:
    """Build Python code for the specified test."""

    # Data loading preamble
    if data_file and column1:
        data_load = textwrap.dedent(f"""\
            import pandas as pd
            df = pd.read_csv({data_file!r})
            data1 = df[{column1!r}].dropna().tolist()
        """)
        if column2:
            data_load += f"data2 = df[{column2!r}].dropna().tolist()\n"
        else:
            data_load += "data2 = None\n"
    else:
        data_load = f"data1 = {data1!r}\ndata2 = {data2!r}\n"

    tests_code: dict[str, str] = {
        "ttest": textwrap.dedent("""\
            from scipy import stats
            stat, p = stats.ttest_ind(data1, data2, equal_var=False)

            # Cohen's d effect size
            import numpy as np
            n1, n2 = len(data1), len(data2)
            s1, s2 = np.std(data1, ddof=1), np.std(data2, ddof=1)
            pooled_std = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
            cohens_d = (np.mean(data1) - np.mean(data2)) / pooled_std if pooled_std > 0 else 0

            if abs(cohens_d) < 0.2:
                effect_mag = "negligible"
            elif abs(cohens_d) < 0.5:
                effect_mag = "small"
            elif abs(cohens_d) < 0.8:
                effect_mag = "medium"
            else:
                effect_mag = "large"

            result.update({
                "test": "Welch's t-test (two-sample, unequal variance)",
                "statistic": float(stat),
                "p_value": float(p),
                "effect_size": round(float(cohens_d), 4),
                "effect_magnitude": effect_mag,
                "mean_group1": round(float(np.mean(data1)), 4),
                "mean_group2": round(float(np.mean(data2)), 4),
                "n_group1": n1,
                "n_group2": n2,
            })
        """),
        "ttest_paired": textwrap.dedent("""\
            from scipy import stats
            import numpy as np
            stat, p = stats.ttest_rel(data1, data2)
            diff = [a - b for a, b in zip(data1, data2)]
            cohens_d = np.mean(diff) / np.std(diff, ddof=1) if np.std(diff, ddof=1) > 0 else 0

            result.update({
                "test": "Paired t-test",
                "statistic": float(stat),
                "p_value": float(p),
                "effect_size": round(float(cohens_d), 4),
                "mean_difference": round(float(np.mean(diff)), 4),
                "n_pairs": len(data1),
            })
        """),
        "ttest_1samp": textwrap.dedent("""\
            from scipy import stats
            import numpy as np
            pop_mean = data2[0] if data2 and len(data2) > 0 else 0
            stat, p = stats.ttest_1samp(data1, pop_mean)
            std1 = np.std(data1, ddof=1)
            cohens_d = (np.mean(data1) - pop_mean) / std1 if std1 > 0 else 0

            result.update({
                "test": f"One-sample t-test (H0: μ = {pop_mean})",
                "statistic": float(stat),
                "p_value": float(p),
                "effect_size": round(float(cohens_d), 4),
                "sample_mean": round(float(np.mean(data1)), 4),
                "pop_mean": float(pop_mean),
                "n": len(data1),
            })
        """),
        "chi2": textwrap.dedent("""\
            from scipy import stats
            import numpy as np
            observed = np.array([data1, data2]) if data2 else np.array(data1).reshape(-1, 2)
            chi2, p, dof, expected = stats.chi2_contingency(observed)
            n = observed.sum()
            cramers_v = np.sqrt(chi2 / (n * (min(observed.shape) - 1))) if n > 0 else 0

            result.update({
                "test": "Chi-squared test of independence",
                "statistic": float(chi2),
                "p_value": float(p),
                "degrees_of_freedom": int(dof),
                "effect_size": round(float(cramers_v), 4),
                "effect_type": "Cramér's V",
            })
        """),
        "mann_whitney": textwrap.dedent("""\
            from scipy import stats
            import numpy as np
            stat, p = stats.mannwhitneyu(data1, data2, alternative="two-sided")
            n1, n2 = len(data1), len(data2)
            r = 1 - (2 * stat) / (n1 * n2)  # rank-biserial correlation

            result.update({
                "test": "Mann-Whitney U test",
                "statistic": float(stat),
                "p_value": float(p),
                "effect_size": round(float(r), 4),
                "effect_type": "rank-biserial correlation",
                "n_group1": n1,
                "n_group2": n2,
            })
        """),
        "anova": textwrap.dedent("""\
            from scipy import stats
            import numpy as np
            # data1 and data2 are the first two groups; split data1 by groups if needed
            groups = [data1]
            if data2:
                groups.append(data2)
            stat, p = stats.f_oneway(*groups)

            # Eta-squared effect size
            all_data = [x for g in groups for x in g]
            grand_mean = np.mean(all_data)
            ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in groups)
            ss_total = sum((x - grand_mean)**2 for x in all_data)
            eta_sq = ss_between / ss_total if ss_total > 0 else 0

            result.update({
                "test": "One-way ANOVA",
                "statistic": float(stat),
                "p_value": float(p),
                "effect_size": round(float(eta_sq), 4),
                "effect_type": "eta-squared",
                "n_groups": len(groups),
                "group_sizes": [len(g) for g in groups],
            })
        """),
        "shapiro": textwrap.dedent("""\
            from scipy import stats
            stat, p = stats.shapiro(data1)
            result.update({
                "test": "Shapiro-Wilk normality test",
                "statistic": float(stat),
                "p_value": float(p),
                "n": len(data1),
                "interpretation_note": "H0: data is normally distributed",
            })
        """),
        "pearson": textwrap.dedent("""\
            from scipy import stats
            stat, p = stats.pearsonr(data1, data2)
            if abs(stat) < 0.1:
                mag = "negligible"
            elif abs(stat) < 0.3:
                mag = "weak"
            elif abs(stat) < 0.7:
                mag = "moderate"
            else:
                mag = "strong"
            result.update({
                "test": "Pearson correlation",
                "statistic": round(float(stat), 4),
                "p_value": float(p),
                "correlation_strength": mag,
                "n": len(data1),
            })
        """),
    }

    test_code = tests_code.get(test_type, 'result["error"] = "Unknown test"')
    alpha_val = alpha

    return textwrap.dedent(f"""\
        import json
        {data_load}
        alpha = {alpha_val}
        result = {{"alpha": alpha}}

        {test_code}

        # Add interpretation
        p = result.get("p_value")
        if p is not None:
            result["significant"] = p < alpha
            if p < alpha:
                result["interpretation"] = (
                    f"SIGNIFICANT (p={{p:.4f}} < {{alpha}}): "
                    "Reject the null hypothesis."
                )
            else:
                result["interpretation"] = (
                    f"NOT SIGNIFICANT (p={{p:.4f}} >= {{alpha}}): "
                    "Fail to reject the null hypothesis."
                )

        print(json.dumps(result, default=str))
    """)
