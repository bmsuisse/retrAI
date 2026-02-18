"""ML model training tool — train sklearn models in the sandbox."""

from __future__ import annotations

import json
import logging
import textwrap
from typing import Any

from retrai.tools.python_exec import python_exec

logger = logging.getLogger(__name__)

# Supported model types and their sklearn/xgboost/lightgbm import paths
MODEL_REGISTRY: dict[str, dict[str, str]] = {
    # Classification & regression
    "logistic_regression": {
        "module": "sklearn.linear_model",
        "class": "LogisticRegression",
        "task": "classification",
    },
    "random_forest": {
        "module": "sklearn.ensemble",
        "class": "RandomForestClassifier",
        "task": "classification",
    },
    "random_forest_regressor": {
        "module": "sklearn.ensemble",
        "class": "RandomForestRegressor",
        "task": "regression",
    },
    "gradient_boosting": {
        "module": "sklearn.ensemble",
        "class": "GradientBoostingClassifier",
        "task": "classification",
    },
    "gradient_boosting_regressor": {
        "module": "sklearn.ensemble",
        "class": "GradientBoostingRegressor",
        "task": "regression",
    },
    "svm": {
        "module": "sklearn.svm",
        "class": "SVC",
        "task": "classification",
        "extra_params": "probability=True",
    },
    "svr": {
        "module": "sklearn.svm",
        "class": "SVR",
        "task": "regression",
    },
    "knn": {
        "module": "sklearn.neighbors",
        "class": "KNeighborsClassifier",
        "task": "classification",
    },
    "knn_regressor": {
        "module": "sklearn.neighbors",
        "class": "KNeighborsRegressor",
        "task": "regression",
    },
    "decision_tree": {
        "module": "sklearn.tree",
        "class": "DecisionTreeClassifier",
        "task": "classification",
    },
    "decision_tree_regressor": {
        "module": "sklearn.tree",
        "class": "DecisionTreeRegressor",
        "task": "regression",
    },
    "ada_boost": {
        "module": "sklearn.ensemble",
        "class": "AdaBoostClassifier",
        "task": "classification",
    },
    "extra_trees": {
        "module": "sklearn.ensemble",
        "class": "ExtraTreesClassifier",
        "task": "classification",
    },
    "ridge": {
        "module": "sklearn.linear_model",
        "class": "Ridge",
        "task": "regression",
    },
    "lasso": {
        "module": "sklearn.linear_model",
        "class": "Lasso",
        "task": "regression",
    },
    "elastic_net": {
        "module": "sklearn.linear_model",
        "class": "ElasticNet",
        "task": "regression",
    },
    "xgboost": {
        "module": "xgboost",
        "class": "XGBClassifier",
        "task": "classification",
        "package": "xgboost",
    },
    "xgboost_regressor": {
        "module": "xgboost",
        "class": "XGBRegressor",
        "task": "regression",
        "package": "xgboost",
    },
    "lightgbm": {
        "module": "lightgbm",
        "class": "LGBMClassifier",
        "task": "classification",
        "package": "lightgbm",
    },
    "lightgbm_regressor": {
        "module": "lightgbm",
        "class": "LGBMRegressor",
        "task": "regression",
        "package": "lightgbm",
    },
}

VALID_CLASSIFICATION_METRICS = {"auc", "f1", "accuracy", "precision", "recall"}
VALID_REGRESSION_METRICS = {"r2", "rmse", "mae", "mse"}
VALID_METRICS = VALID_CLASSIFICATION_METRICS | VALID_REGRESSION_METRICS


async def ml_train(
    data_file: str,
    target_column: str,
    cwd: str,
    model_type: str = "random_forest",
    task_type: str | None = None,
    hyperparams: dict[str, Any] | None = None,
    test_size: float = 0.2,
    feature_columns: list[str] | None = None,
    scoring_metric: str = "auc",
    cross_validate: bool = True,
    cv_folds: int = 5,
) -> str:
    """Train a sklearn-compatible ML model in the sandbox.

    Args:
        data_file: Path to CSV/JSON dataset (relative to cwd).
        target_column: Column name to predict.
        cwd: Working directory.
        model_type: Model to train (see MODEL_REGISTRY keys).
        task_type: "classification" or "regression" (auto-detected).
        hyperparams: Dict of kwargs for the estimator constructor.
        test_size: Fraction for train/test split (default 0.2).
        feature_columns: Subset of columns to use as features.
        scoring_metric: Primary metric: auc, f1, accuracy, etc.
        cross_validate: Whether to run k-fold CV (default True).
        cv_folds: Number of CV folds (default 5).

    Returns:
        JSON string with model metrics, feature importance, etc.
    """
    model_type = model_type.lower().strip()
    scoring_metric = scoring_metric.lower().strip()

    # Validate model type
    if model_type not in MODEL_REGISTRY:
        return json.dumps({
            "error": f"Unknown model_type '{model_type}'. "
                     f"Available: {', '.join(sorted(MODEL_REGISTRY.keys()))}",
        })

    # Validate scoring metric
    if scoring_metric not in VALID_METRICS:
        return json.dumps({
            "error": f"Unknown scoring_metric '{scoring_metric}'. "
                     f"Available: {', '.join(sorted(VALID_METRICS))}",
        })

    model_info = MODEL_REGISTRY[model_type]

    # Determine packages to install
    packages = ["scikit-learn", "pandas", "numpy"]
    extra_pkg = model_info.get("package")
    if extra_pkg:
        packages.append(extra_pkg)

    code = _build_training_code(
        data_file=data_file,
        target_column=target_column,
        model_info=model_info,
        task_type=task_type,
        hyperparams=hyperparams or {},
        test_size=test_size,
        feature_columns=feature_columns,
        scoring_metric=scoring_metric,
        cross_validate=cross_validate,
        cv_folds=cv_folds,
    )

    result = await python_exec(
        code=code,
        cwd=cwd,
        packages=packages,
        timeout=120.0,
    )

    if result.timed_out:
        return json.dumps({"error": "Training timed out (120s limit)"})

    if result.returncode != 0:
        return json.dumps({
            "error": f"Training failed (exit {result.returncode})",
            "stderr": result.stderr[:3000],
        })

    stdout = result.stdout.strip()
    try:
        parsed = json.loads(stdout)
        return json.dumps(parsed, indent=2, default=str)
    except json.JSONDecodeError:
        return json.dumps({
            "model_type": model_type,
            "raw_output": stdout[:5000],
        })


def _build_training_code(
    data_file: str,
    target_column: str,
    model_info: dict[str, str],
    task_type: str | None,
    hyperparams: dict[str, Any],
    test_size: float,
    feature_columns: list[str] | None,
    scoring_metric: str,
    cross_validate: bool,
    cv_folds: int,
) -> str:
    """Build the Python code that runs inside the sandbox."""
    module = model_info["module"]
    cls_name = model_info["class"]
    default_task = model_info["task"]
    extra_params = model_info.get("extra_params", "")

    hp_str = ", ".join(f"{k}={v!r}" for k, v in hyperparams.items())
    if extra_params and hp_str:
        hp_str = f"{extra_params}, {hp_str}"
    elif extra_params:
        hp_str = extra_params

    feature_cols_repr = repr(feature_columns) if feature_columns else "None"
    task_type_repr = repr(task_type) if task_type else "None"

    return textwrap.dedent(f"""\
        import json
        import time
        import warnings
        warnings.filterwarnings("ignore")

        import numpy as np
        import pandas as pd
        from {module} import {cls_name}
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import LabelEncoder, StandardScaler
        from sklearn.metrics import (
            roc_auc_score, f1_score, accuracy_score, precision_score,
            recall_score, r2_score, mean_squared_error, mean_absolute_error,
        )

        start = time.monotonic()

        # ── Load data ──
        path = {data_file!r}
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        elif path.endswith(".json") or path.endswith(".jsonl"):
            df = pd.read_json(path, lines=path.endswith(".jsonl"))
        elif path.endswith(".xlsx") or path.endswith(".xls"):
            df = pd.read_excel(path)
        elif path.endswith(".parquet"):
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)

        target_col = {target_column!r}
        feature_cols = {feature_cols_repr}
        task_override = {task_type_repr}

        # ── Determine task type ──
        if task_override:
            task_type = task_override
        else:
            n_unique = df[target_col].nunique()
            if n_unique <= 20 or df[target_col].dtype == "object":
                task_type = "classification"
            else:
                task_type = "{default_task}"

        # ── Prepare features ──
        if feature_cols:
            X = df[feature_cols].copy()
        else:
            X = df.drop(columns=[target_col]).copy()

        y = df[target_col].copy()

        # Encode target if categorical
        label_enc = None
        if y.dtype == "object" or y.dtype.name == "category":
            label_enc = LabelEncoder()
            y = pd.Series(label_enc.fit_transform(y), name=target_col)

        # Handle categorical features
        cat_cols = X.select_dtypes(include=["object", "category"]).columns.tolist()
        for col in cat_cols:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))

        # Handle missing values
        for col in X.columns:
            if X[col].isnull().any():
                if X[col].dtype in ["float64", "int64"]:
                    X[col] = X[col].fillna(X[col].median())
                else:
                    X[col] = X[col].fillna(X[col].mode().iloc[0] if len(X[col].mode()) > 0 else 0)

        if y.isnull().any():
            mask = ~y.isnull()
            X = X[mask]
            y = y[mask]

        # ── Train/test split ──
        strat = y if task_type == "classification" else None
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size={test_size}, random_state=42,
            stratify=strat,
        )

        # ── Scale features ──
        scaler = StandardScaler()
        X_train_scaled = pd.DataFrame(
            scaler.fit_transform(X_train), columns=X_train.columns,
        )
        X_test_scaled = pd.DataFrame(
            scaler.transform(X_test), columns=X_test.columns,
        )

        # ── Train model ──
        model = {cls_name}({hp_str})
        model.fit(X_train_scaled, y_train)

        # ── Compute metrics ──
        metrics = {{}}
        y_pred = model.predict(X_test_scaled)

        if task_type == "classification":
            metrics["accuracy"] = round(
                float(accuracy_score(y_test, y_pred)), 4,
            )
            n_classes = len(np.unique(y))
            avg = "binary" if n_classes == 2 else "weighted"

            metrics["f1"] = round(float(
                f1_score(y_test, y_pred, average=avg, zero_division=0),
            ), 4)
            metrics["precision"] = round(float(
                precision_score(y_test, y_pred, average=avg, zero_division=0),
            ), 4)
            metrics["recall"] = round(float(
                recall_score(y_test, y_pred, average=avg, zero_division=0),
            ), 4)

            # AUC
            try:
                if hasattr(model, "predict_proba"):
                    y_prob = model.predict_proba(X_test_scaled)
                    if n_classes == 2:
                        auc_val = roc_auc_score(y_test, y_prob[:, 1])
                    else:
                        auc_val = roc_auc_score(
                            y_test, y_prob,
                            multi_class="ovr", average="weighted",
                        )
                    metrics["auc"] = round(float(auc_val), 4)
                elif hasattr(model, "decision_function"):
                    y_scores = model.decision_function(X_test_scaled)
                    if n_classes == 2:
                        auc_val = roc_auc_score(y_test, y_scores)
                        metrics["auc"] = round(float(auc_val), 4)
            except Exception:
                metrics["auc"] = None
        else:
            metrics["r2"] = round(float(r2_score(y_test, y_pred)), 4)
            metrics["rmse"] = round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 4)
            metrics["mae"] = round(float(mean_absolute_error(y_test, y_pred)), 4)
            metrics["mse"] = round(float(mean_squared_error(y_test, y_pred)), 4)

        # ── Cross-validation ──
        cv_result = None
        if {cross_validate!r}:
            try:
                if task_type == "classification":
                    sm = {scoring_metric!r}
                    scoring = "roc_auc" if sm == "auc" else sm
                    if scoring == "roc_auc" and n_classes > 2:
                        scoring = "roc_auc_ovr_weighted"
                else:
                    score_map = {{
                        "r2": "r2",
                        "rmse": "neg_root_mean_squared_error",
                        "mae": "neg_mean_absolute_error",
                        "mse": "neg_mean_squared_error",
                    }}
                    scoring = score_map.get({scoring_metric!r}, "r2")

                scores = cross_val_score(
                    model, X_train_scaled, y_train,
                    cv={cv_folds}, scoring=scoring,
                )
                cv_result = {{
                    "metric": {scoring_metric!r},
                    "mean": round(float(np.mean(scores)), 4),
                    "std": round(float(np.std(scores)), 4),
                    "folds": [round(float(s), 4) for s in scores],
                }}
            except Exception as e:
                cv_result = {{"error": str(e)}}

        # ── Feature importance ──
        feature_importance = {{}}
        try:
            if hasattr(model, "feature_importances_"):
                imp = model.feature_importances_
                for fname, fval in sorted(zip(X.columns, imp), key=lambda x: -x[1]):
                    feature_importance[fname] = round(float(fval), 4)
            elif hasattr(model, "coef_"):
                coef = model.coef_.flatten() if model.coef_.ndim > 1 else model.coef_
                for fname, fval in sorted(zip(X.columns, np.abs(coef)), key=lambda x: -x[1]):
                    feature_importance[fname] = round(float(fval), 4)
        except Exception:
            pass

        elapsed = time.monotonic() - start

        output = {{
            "model_type": {cls_name!r},
            "task_type": task_type,
            "scoring_metric": {scoring_metric!r},
            "metrics": metrics,
            "cv_scores": cv_result,
            "feature_importance": feature_importance,
            "hyperparams_used": {hyperparams!r},
            "training_time_seconds": round(elapsed, 2),
            "n_samples": len(df),
            "n_features": len(X.columns),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "feature_names": list(X.columns),
            "target_column": target_col,
        }}

        print(json.dumps(output, default=str))
    """)
