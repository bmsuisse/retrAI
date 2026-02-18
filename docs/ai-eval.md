# AI-Generated Eval Harness

The AI eval harness feature lets you describe what you want to achieve in plain English — and retrAI writes the test harness for you.

## The Problem It Solves

Sometimes you want the agent to improve code but there's no pre-existing test suite. For example:

- "Optimize this SQL query to run in < 50ms"
- "Make the sorting function handle duplicates"
- "Ensure the API returns a JSON `data` wrapper"

These aren't bugs in existing tests — they're new requirements. With `generate-eval`, you describe the requirement and get a pytest harness that captures it.

---

## Two-Phase Architecture

```
Phase 1: Planning Agent
  Input: natural language description + project files
  Output: .retrai/eval_harness.py

Phase 2: Implementation Agent
  Input: eval harness + project source
  Goal: make pytest .retrai/eval_harness.py pass
```

### Phase 1 — Planning Agent

`retrai generate-eval` calls the LLM once with:
- Your description
- The project file listing
- Key config files (pyproject.toml, package.json, etc.)
- Up to 5 main source files

The LLM writes a complete, runnable pytest file that tests your requirement.

### Phase 2 — Implementation Agent

`retrai run ai-eval` runs the standard agent loop, but:
- `AiEvalGoal.check()` runs `pytest .retrai/eval_harness.py`
- `AiEvalGoal.system_prompt()` includes your original description so the agent understands *why*
- The agent reads the harness, understands what it tests, then fixes the source code

---

## Usage

```bash
# Step 1: Generate the harness
retrai generate-eval "make the bubble_sort function in sorting.py handle empty lists"

# This creates .retrai/eval_harness.py and prints it for review.

# Step 2: Run the agent
retrai run ai-eval

# Use a different model
retrai generate-eval "optimize DB query" --model claude-opus-4-6
retrai run ai-eval --model claude-opus-4-6 --max-iter 30
```

---

## What Gets Created

```
.retrai/
├── eval_harness.py      The generated pytest test file
└── ai_eval_config.json  Metadata: description, model, timestamp
```

Example `.retrai/ai_eval_config.json`:
```json
{
  "description": "make bubble_sort handle empty lists",
  "harness_file": ".retrai/eval_harness.py",
  "generated_at": "2026-02-17T12:00:00+00:00",
  "model": "claude-sonnet-4-6"
}
```

---

## Tips

- **Review the harness** before running the agent — make sure it tests what you intended
- **Be specific** in your description: "make sort() handle lists with None values" is better than "fix sort"
- **Iterative refinement**: if the generated harness isn't right, just re-run `generate-eval` with a clearer description
- **Don't modify the harness** while the agent is running — `AiEvalGoal` explicitly tells the agent not to touch it
