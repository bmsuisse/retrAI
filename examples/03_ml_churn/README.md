# 03 — ML Model Optimization (Churn Prediction)

The agent iteratively trains and tunes classifiers to reach **F1 ≥ 0.88** on customer churn.

## Setup

```bash
python generate_data.py
```

## Run

```bash
retrai ml churn.csv churned --metric f1 --target-value 0.88 --cwd .
# or simply:
retrai run --cwd .
```

The agent has access to `ml_train`, `data_analysis`, and `python_exec` tools.
It will try different algorithms, tune hyperparameters, and apply feature engineering.
