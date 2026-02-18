"""ML optimization goal — iteratively improve model metrics."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from retrai.goals.base import GoalBase, GoalResult

logger = logging.getLogger(__name__)

_CONFIG_FILE = ".retrai.yml"


def _load_config(cwd: str) -> dict:
    path = Path(cwd) / _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


class MlOptimizeGoal(GoalBase):
    """Optimize an ML model until a target metric is reached.

    `.retrai.yml`:

    ```yaml
    goal: ml-optimize
    data_file: data.csv
    target_column: churn
    target_metric: auc
    target_value: 0.90
    task_type: classification  # optional
    ```

    The agent trains models iteratively, trying different algorithms,
    hyperparameters, and feature engineering until the target metric
    is achieved.
    """

    name = "ml-optimize"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        target_metric = cfg.get("target_metric", "auc").lower()
        target_value = float(cfg.get("target_value", 0.85))
        data_file = cfg.get("data_file", "")

        if not data_file:
            return GoalResult(
                achieved=False,
                reason="No data_file specified in .retrai.yml",
                details={"config": cfg},
            )

        # Parse the latest ml_train result from tool outputs
        best_score = self._extract_best_metric(state, target_metric)

        if best_score is None:
            iteration = state.get("iteration", 0)
            if iteration < 1:
                return GoalResult(
                    achieved=False,
                    reason=(
                        "No model trained yet. Use the ml_train tool to train "
                        "a model and check the metrics."
                    ),
                    details={"target_metric": target_metric, "target_value": target_value},
                )
            return GoalResult(
                achieved=False,
                reason=(
                    f"No {target_metric} score found in recent tool outputs. "
                    "Train a model using ml_train to produce metrics."
                ),
                details={"target_metric": target_metric, "target_value": target_value},
            )

        if best_score >= target_value:
            return GoalResult(
                achieved=True,
                reason=(
                    f"Target reached! {target_metric.upper()} = {best_score:.4f} "
                    f"≥ {target_value} 🎯"
                ),
                details={
                    "best_score": best_score,
                    "target_metric": target_metric,
                    "target_value": target_value,
                },
            )

        gap = target_value - best_score
        return GoalResult(
            achieved=False,
            reason=(
                f"Best {target_metric.upper()} so far: {best_score:.4f} "
                f"(target: {target_value}, gap: {gap:.4f}). "
                "Try a different model, tune hyperparameters, or add "
                "feature engineering."
            ),
            details={
                "best_score": best_score,
                "target_metric": target_metric,
                "target_value": target_value,
                "gap": gap,
            },
        )

    def _extract_best_metric(
        self,
        state: dict,
        metric_name: str,
    ) -> float | None:
        """Extract the best metric value from tool results in the state."""
        best: float | None = None

        # Search through tool results for ml_train outputs
        tool_results = state.get("tool_results", [])
        for tr in tool_results:
            if tr.get("name") != "ml_train":
                continue
            content = tr.get("content", "")
            try:
                data = json.loads(content)
                metrics = data.get("metrics", {})
                value = metrics.get(metric_name)
                if value is not None:
                    score = float(value)
                    if best is None or score > best:
                        best = score
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        # Also search through messages for tool results
        messages = state.get("messages", [])
        for msg in messages:
            content = getattr(msg, "content", "")
            name = getattr(msg, "name", "")
            if name != "ml_train":
                continue
            if not isinstance(content, str):
                continue
            try:
                data = json.loads(content)
                metrics = data.get("metrics", {})
                value = metrics.get(metric_name)
                if value is not None:
                    score = float(value)
                    if best is None or score > best:
                        best = score
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        return best

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        data_file = cfg.get("data_file", "<data_file>")
        target_col = cfg.get("target_column", "<target>")
        target_metric = cfg.get("target_metric", "auc").upper()
        target_value = cfg.get("target_value", 0.85)
        task_type = cfg.get("task_type", "auto-detect")
        custom = cfg.get("system_prompt", "")

        base = (
            f"## Goal: ML Model Optimization\n\n"
            f"Optimize a machine learning model on `{data_file}` "
            f"(target column: `{target_col}`) to achieve "
            f"**{target_metric} ≥ {target_value}**.\n\n"
            f"Task type: {task_type}\n\n"
            "**Strategy**:\n"
            "1. Start by analyzing the data with `data_analysis` to "
            "understand features, correlations, and quality.\n"
            "2. Train a baseline model with `ml_train` (e.g. logistic_regression).\n"
            "3. Review the metrics and feature importance.\n"
            "4. Iterate: try different models, tune hyperparameters, and "
            "apply feature engineering.\n"
            "5. Log each experiment with `experiment_log` for comparison.\n\n"
            "**Available models** (use with `ml_train`):\n"
            "- Classification: `logistic_regression`, `random_forest`, "
            "`gradient_boosting`, `svm`, `knn`, `decision_tree`, "
            "`ada_boost`, `extra_trees`, `xgboost`, `lightgbm`\n"
            "- Regression: `random_forest_regressor`, "
            "`gradient_boosting_regressor`, `svr`, `knn_regressor`, "
            "`ridge`, `lasso`, `elastic_net`, `xgboost_regressor`, "
            "`lightgbm_regressor`\n\n"
            "**Optimization tactics**:\n"
            "- Start simple (logistic regression), then go complex\n"
            "- Tune key hyperparams: n_estimators, max_depth, learning_rate, C\n"
            "- Try feature engineering via `python_exec`: interactions, "
            "polynomials, binning, encoding\n"
            "- Check for class imbalance and use class_weight='balanced'\n"
            "- Compare cross-validation scores to avoid overfitting\n"
            "- Use `experiment_log` to track what you've tried\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base
