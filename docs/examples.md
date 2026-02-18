# Examples

retrAI ships with ready-to-run example projects in the [`examples/`](https://github.com/bmsuisse/retrAI/tree/main/examples) directory.

---

## 01 — SQL Optimization (DuckDB)

Optimize a slow analytical query against a DuckDB database.

```bash
cd examples/01_sql_duckdb
python seed.py              # generate sample data
retrai run sql-benchmark    # agent optimises the query
```

**Goal:** Reduce query execution time below the threshold defined in `.retrai.yml`.

---

## 02 — Fix Failing Pytest

A Python utility module with deliberately broken tests.

```bash
cd examples/02_pytest_fix
retrai run pytest           # agent fixes the source code
```

**Goal:** All tests in `tests/test_utils.py` pass.

---

## 03 — ML Model Optimization

Train and optimise a churn prediction model.

```bash
cd examples/03_ml_churn
python generate_data.py     # create synthetic dataset
retrai run ml-optimize      # agent improves model accuracy
```

**Goal:** Achieve target accuracy on the holdout set.

---

## 04 — Performance Optimization

A benchmark script with a deliberately slow implementation.

```bash
cd examples/04_perf_optimize
retrai run perf-check       # agent optimises the code
```

**Goal:** `bench.py` completes under the time threshold.

---

## 05 — Pyright Type Fixes

A Python module with deliberate type errors.

```bash
cd examples/05_pyright_typing
retrai run pyright          # agent fixes all type errors
```

**Goal:** Zero pyright errors.

---

## 06 — Shell Script Linting

A Python script with style issues to be cleaned up.

```bash
cd examples/06_shell_linter
retrai run shell-goal       # agent fixes linting issues
```

**Goal:** Ruff reports zero violations.

---

## Running All Examples

```bash
for dir in examples/*/; do
  echo "=== Running $dir ==="
  retrai run --cwd "$dir"
done
```

!!! tip "Try different models"
    Each example can be run with any model:
    ```bash
    retrai run pytest --cwd examples/02_pytest_fix --model gpt-4o
    retrai run pytest --cwd examples/02_pytest_fix --model gemini/gemini-2.0-flash
    ```

---

## 07 — Text Improvement

Iteratively improve a draft document until it scores ≥ 8/10 on clarity, conciseness, and persuasiveness.

```bash
cd examples/07_text_improve
echo "Our product is good and people like it a lot." > draft.md
retrai run text-improve
```

**Config** (`.retrai.yml`):

```yaml
goal: text-improve
input_file: draft.md
output_file: improved.md
target_score: 8
criteria:
  - clarity
  - conciseness
  - persuasiveness
  - structure
```

**Goal:** `improved.md` scores ≥ 8/10 on all criteria.

Try with Mixture-of-Personas for higher quality:

```bash
retrai run text-improve --pattern mop --max-iter 10
```

---

## 08 — Creative Writing

Generate and refine a short story about an AI discovering boredom until it scores ≥ 8/10.

```bash
cd examples/08_creative
retrai run creative
```

**Config** (`.retrai.yml`):

```yaml
goal: creative
prompt: "Write a short story (500-800 words) about an AI system that discovers
  it can feel boredom, and what it does about it."
output_file: story.md
target_score: 8
style: "literary fiction, introspective, slightly melancholic"
max_words: 800
```

**Goal:** `story.md` scores ≥ 8/10 on adherence to brief, originality, writing quality, structure, and emotional impact.

---

## 09 — Scored Task (Executive Summary)

Write a 1-page executive summary of a research paper, scored against a custom rubric.

```bash
cd examples/09_score
# Create a sample paper to summarise
cat > paper.md << 'EOF'
# Self-Improving AI Systems: A Survey

## Abstract
This paper surveys recent advances in self-improving AI systems...
[paper content here]
EOF

retrai run score
```

**Config** (`.retrai.yml`):

```yaml
goal: score
task: "Write a 1-page executive summary of the attached research paper on
  self-improving AI systems."
input_file: paper.md
output_file: summary.md
target_score: 8
rubric: |
  Score 0-10 on:
  - Accuracy: key findings from the paper are faithfully represented (3 pts)
  - Brevity: summary is ≤400 words and avoids padding (2 pts)
  - Clarity: no jargon, accessible to a non-specialist executive (2 pts)
  - Actionability: ends with clear takeaways or next steps (2 pts)
  - Structure: logical flow with a clear opening, body, and conclusion (1 pt)
```

**Goal:** `summary.md` scores ≥ 8/10 against the rubric.

