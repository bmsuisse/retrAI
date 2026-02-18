"""Tests for ML training tool and ML optimization goal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retrai.goals.ml_goal import MlOptimizeGoal
from retrai.tools.ml_train import (
    MODEL_REGISTRY,
    VALID_METRICS,
    _build_training_code,
    ml_train,
)

# ── ml_train validation ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ml_train_invalid_model_type() -> None:
    result = await ml_train(
        data_file="data.csv",
        target_column="target",
        cwd="/tmp",
        model_type="invalid_model",
    )
    data = json.loads(result)
    assert "error" in data
    assert "Unknown model_type" in data["error"]


@pytest.mark.asyncio
async def test_ml_train_invalid_metric() -> None:
    result = await ml_train(
        data_file="data.csv",
        target_column="target",
        cwd="/tmp",
        scoring_metric="invalid_metric",
    )
    data = json.loads(result)
    assert "error" in data
    assert "Unknown scoring_metric" in data["error"]


# ── _build_training_code ─────────────────────────────────────────────────────


def test_build_training_code_classification() -> None:
    model_info = MODEL_REGISTRY["random_forest"]
    code = _build_training_code(
        data_file="data.csv",
        target_column="target",
        model_info=model_info,
        task_type="classification",
        hyperparams={"n_estimators": 100, "max_depth": 10},
        test_size=0.2,
        feature_columns=None,
        scoring_metric="auc",
        cross_validate=True,
        cv_folds=5,
    )
    assert "RandomForestClassifier" in code
    assert "n_estimators=100" in code
    assert "max_depth=10" in code
    assert "roc_auc_score" in code
    assert "cross_val_score" in code


def test_build_training_code_regression() -> None:
    model_info = MODEL_REGISTRY["ridge"]
    code = _build_training_code(
        data_file="data.csv",
        target_column="price",
        model_info=model_info,
        task_type="regression",
        hyperparams={"alpha": 1.0},
        test_size=0.3,
        feature_columns=["f1", "f2"],
        scoring_metric="r2",
        cross_validate=False,
        cv_folds=3,
    )
    assert "Ridge" in code
    assert "alpha=1.0" in code
    assert "r2_score" in code
    assert "['f1', 'f2']" in code


def test_build_training_code_svm_has_probability() -> None:
    """SVM should always include probability=True."""
    model_info = MODEL_REGISTRY["svm"]
    code = _build_training_code(
        data_file="data.csv",
        target_column="target",
        model_info=model_info,
        task_type=None,
        hyperparams={},
        test_size=0.2,
        feature_columns=None,
        scoring_metric="auc",
        cross_validate=True,
        cv_folds=5,
    )
    assert "SVC" in code
    assert "probability=True" in code


def test_build_training_code_xgboost() -> None:
    model_info = MODEL_REGISTRY["xgboost"]
    code = _build_training_code(
        data_file="data.csv",
        target_column="label",
        model_info=model_info,
        task_type="classification",
        hyperparams={"n_estimators": 200, "learning_rate": 0.1},
        test_size=0.2,
        feature_columns=None,
        scoring_metric="f1",
        cross_validate=True,
        cv_folds=5,
    )
    assert "from xgboost import XGBClassifier" in code
    assert "n_estimators=200" in code
    assert "learning_rate=0.1" in code


def test_build_training_code_feature_columns() -> None:
    model_info = MODEL_REGISTRY["logistic_regression"]
    code = _build_training_code(
        data_file="data.csv",
        target_column="target",
        model_info=model_info,
        task_type=None,
        hyperparams={},
        test_size=0.2,
        feature_columns=["age", "income", "score"],
        scoring_metric="accuracy",
        cross_validate=True,
        cv_folds=5,
    )
    assert "['age', 'income', 'score']" in code


# ── MODEL_REGISTRY ───────────────────────────────────────────────────────────


def test_model_registry_has_key_models() -> None:
    expected = [
        "logistic_regression",
        "random_forest",
        "gradient_boosting",
        "svm",
        "knn",
        "decision_tree",
        "xgboost",
        "lightgbm",
        "ridge",
        "lasso",
    ]
    for name in expected:
        assert name in MODEL_REGISTRY, f"Missing: {name}"


def test_all_models_have_required_keys() -> None:
    for name, info in MODEL_REGISTRY.items():
        assert "module" in info, f"{name} missing 'module'"
        assert "class" in info, f"{name} missing 'class'"
        assert "task" in info, f"{name} missing 'task'"
        assert info["task"] in (
            "classification",
            "regression",
        ), f"{name} has invalid task: {info['task']}"


def test_valid_metrics_complete() -> None:
    assert "auc" in VALID_METRICS
    assert "f1" in VALID_METRICS
    assert "accuracy" in VALID_METRICS
    assert "r2" in VALID_METRICS
    assert "rmse" in VALID_METRICS
    assert "mae" in VALID_METRICS


# ── MlOptimizeGoal ───────────────────────────────────────────────────────────


class TestMlOptimizeGoal:
    """Tests for the ML optimization goal."""

    def setup_method(self) -> None:
        self.goal = MlOptimizeGoal()

    @pytest.mark.asyncio
    async def test_no_config(self, tmp_path: Path) -> None:
        state: dict = {
            "messages": [],
            "tool_results": [],
            "iteration": 0,
        }
        result = await self.goal.check(state, str(tmp_path))
        assert not result.achieved
        assert "No data_file" in result.reason

    @pytest.mark.asyncio
    async def test_no_training_yet(self, tmp_path: Path) -> None:
        config_path = tmp_path / ".retrai.yml"
        config_path.write_text(
            "goal: ml-optimize\n"
            "data_file: data.csv\n"
            "target_column: churn\n"
            "target_metric: auc\n"
            "target_value: 0.90\n"
        )
        state: dict = {
            "messages": [],
            "tool_results": [],
            "iteration": 0,
        }
        result = await self.goal.check(state, str(tmp_path))
        assert not result.achieved
        assert "No model trained" in result.reason

    @pytest.mark.asyncio
    async def test_metric_below_target(
        self,
        tmp_path: Path,
    ) -> None:
        config_path = tmp_path / ".retrai.yml"
        config_path.write_text(
            "goal: ml-optimize\n"
            "data_file: data.csv\n"
            "target_column: churn\n"
            "target_metric: auc\n"
            "target_value: 0.90\n"
        )
        tool_result = {
            "name": "ml_train",
            "content": json.dumps(
                {
                    "metrics": {"auc": 0.82, "f1": 0.75},
                }
            ),
        }
        state: dict = {
            "messages": [],
            "tool_results": [tool_result],
            "iteration": 1,
        }
        result = await self.goal.check(state, str(tmp_path))
        assert not result.achieved
        assert "0.82" in result.reason
        assert result.details
        assert result.details["gap"] == pytest.approx(0.08)

    @pytest.mark.asyncio
    async def test_metric_meets_target(
        self,
        tmp_path: Path,
    ) -> None:
        config_path = tmp_path / ".retrai.yml"
        config_path.write_text(
            "goal: ml-optimize\n"
            "data_file: data.csv\n"
            "target_column: churn\n"
            "target_metric: auc\n"
            "target_value: 0.90\n"
        )
        tool_result = {
            "name": "ml_train",
            "content": json.dumps(
                {
                    "metrics": {"auc": 0.92, "f1": 0.88},
                }
            ),
        }
        state: dict = {
            "messages": [],
            "tool_results": [tool_result],
            "iteration": 2,
        }
        result = await self.goal.check(state, str(tmp_path))
        assert result.achieved
        assert "Target reached" in result.reason
        assert "0.92" in result.reason

    @pytest.mark.asyncio
    async def test_picks_best_score(
        self,
        tmp_path: Path,
    ) -> None:
        config_path = tmp_path / ".retrai.yml"
        config_path.write_text(
            "goal: ml-optimize\n"
            "data_file: data.csv\n"
            "target_column: churn\n"
            "target_metric: auc\n"
            "target_value: 0.90\n"
        )
        results = [
            {
                "name": "ml_train",
                "content": json.dumps(
                    {
                        "metrics": {"auc": 0.70},
                    }
                ),
            },
            {
                "name": "ml_train",
                "content": json.dumps(
                    {
                        "metrics": {"auc": 0.91},
                    }
                ),
            },
            {
                "name": "ml_train",
                "content": json.dumps(
                    {
                        "metrics": {"auc": 0.85},
                    }
                ),
            },
        ]
        state: dict = {
            "messages": [],
            "tool_results": results,
            "iteration": 3,
        }
        result = await self.goal.check(state, str(tmp_path))
        assert result.achieved
        assert result.details
        assert result.details["best_score"] == pytest.approx(0.91)

    def test_system_prompt_contains_instructions(
        self,
        tmp_path: Path,
    ) -> None:
        config_path = tmp_path / ".retrai.yml"
        config_path.write_text(
            "goal: ml-optimize\n"
            "data_file: data.csv\n"
            "target_column: churn\n"
            "target_metric: auc\n"
            "target_value: 0.95\n"
        )
        prompt = self.goal.system_prompt(str(tmp_path))
        assert "data.csv" in prompt
        assert "churn" in prompt
        assert "AUC" in prompt
        assert "0.95" in prompt
        assert "ml_train" in prompt
        assert "random_forest" in prompt


# ── Goal Registry ────────────────────────────────────────────────────────────


def test_ml_optimize_in_registry() -> None:
    from retrai.goals.registry import get_goal, list_goals

    assert "ml-optimize" in list_goals()
    goal = get_goal("ml-optimize")
    assert isinstance(goal, MlOptimizeGoal)
