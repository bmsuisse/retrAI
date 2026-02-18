# Non-Coding Goals

retrAI isn't just for fixing tests. The same **iterate-until-solved** loop works for any task that produces text — improving a document, writing a story, summarising a paper, or anything else you can describe with a rubric.

Three LLM-scored goals ship out of the box:

| Goal | Best for |
|---|---|
| [`text-improve`](#text-improve) | Iteratively polish an existing document |
| [`creative`](#creative) | Generate and refine creative content from a brief |
| [`score`](#score) | Any task with a custom rubric — the most flexible option |

All three share the same loop:

```
agent writes/rewrites output → LLM judge scores it → feedback drives next iteration
```

---

## How the LLM-as-Judge Works

After each iteration the goal calls a second LLM (the *judge*) with:

- The agent's output
- The task description / rubric
- Any style or constraint notes

The judge returns a **score 0–10** and **2–3 sentences of feedback**. The agent reads this feedback in the next iteration and revises accordingly.

!!! tip "Choosing a target score"
    `target_score: 8` is a good default. Scores of 9–10 require genuinely excellent output and will take more iterations. Start at 7–8 and raise if results feel too easy.

---

## `text-improve`

Iteratively improve an existing text file until it scores ≥ `target_score`.

### Configuration

```yaml
goal: text-improve
input_file: draft.md          # source text to read and improve
output_file: improved.md      # where the agent writes the result (defaults to input_file)
target_score: 8               # 0–10, default 8
criteria:                     # optional rubric items (default: clarity, conciseness, quality)
  - clarity
  - conciseness
  - persuasiveness
  - structure
```

### Quick start

```bash
# Create your draft
echo "Our product is good and people like it." > draft.md

# Create config
cat > .retrai.yml << 'EOF'
goal: text-improve
input_file: draft.md
output_file: improved.md
target_score: 8
criteria:
  - clarity
  - persuasiveness
  - professional tone
EOF

# Run the agent
retrai run text-improve
```

### Example: Improve a README

```yaml
# .retrai.yml
goal: text-improve
input_file: README.md
output_file: README.md        # overwrite in place
target_score: 8
criteria:
  - clarity
  - completeness
  - developer-friendliness
  - conciseness
```

```bash
retrai run text-improve --model gpt-4o --max-iter 10
```

### Example: Polish a blog post

```yaml
goal: text-improve
input_file: posts/draft-ai-agents.md
output_file: posts/ai-agents.md
target_score: 9
criteria:
  - engaging opening hook
  - clear argument structure
  - concrete examples
  - strong conclusion
  - appropriate length (800-1200 words)
```

### Example: Improve a cover letter

```yaml
goal: text-improve
input_file: cover_letter_draft.md
output_file: cover_letter.md
target_score: 8
criteria:
  - tailored to the role
  - highlights relevant experience
  - confident but not arrogant tone
  - concise (under 400 words)
```

### How the agent works

1. Reads `input_file` (or `output_file` if it already exists from a previous iteration)
2. Identifies weaknesses based on the criteria
3. Rewrites the text and saves to `output_file`
4. The goal scores the output and provides specific feedback
5. Repeats until `target_score` is reached

---

## `creative`

Generate and refine creative content from a brief until it scores ≥ `target_score`.

### Configuration

```yaml
goal: creative
prompt: "Write a short story about..."   # the creative brief (required)
output_file: story.md                    # where the agent writes the content
target_score: 8                          # 0–10, default 8
style: "literary fiction, melancholic"   # optional style guidance
max_words: 800                           # optional word count limit
```

### Quick start

```bash
cat > .retrai.yml << 'EOF'
goal: creative
prompt: "Write a short story (500-800 words) about an AI that discovers it can feel boredom."
output_file: story.md
target_score: 8
style: "literary fiction, introspective, slightly melancholic"
max_words: 800
EOF

retrai run creative
```

### Example: Write a poem

```yaml
goal: creative
prompt: |
  Write a poem about the passage of time as experienced by a lighthouse keeper.
  The poem should have 4 stanzas of 4 lines each, with an ABAB rhyme scheme.
output_file: poem.md
target_score: 8
style: "contemplative, imagery-rich, classical"
```

### Example: Write a product description

```yaml
goal: creative
prompt: |
  Write a compelling product description for a pair of noise-cancelling headphones
  aimed at remote workers. Highlight: focus, comfort, battery life.
  Tone: professional but warm. Length: 150-200 words.
output_file: product_desc.md
target_score: 8
```

### Example: Write a children's story

```yaml
goal: creative
prompt: |
  Write a children's story (ages 5-8) about a small cloud who is afraid of thunder.
  The cloud learns to be brave with help from a friendly bird.
  Include a clear moral about courage.
output_file: story.md
target_score: 8
style: "warm, simple vocabulary, gentle humour"
max_words: 600
```

### Example: Write a technical blog post

```yaml
goal: creative
prompt: |
  Write a technical blog post explaining how vector databases work,
  aimed at senior software engineers who haven't used them before.
  Include: what problem they solve, how they differ from SQL/NoSQL,
  a concrete use case, and a simple code example in Python.
output_file: vector_db_post.md
target_score: 8
style: "clear, technically accurate, engaging, not condescending"
max_words: 1200
```

### Scoring criteria

The judge evaluates creative content on:

- **Adherence to brief** — does it match what was asked?
- **Originality and creativity** — fresh ideas, unexpected angles
- **Quality of writing** — voice, style, language precision
- **Structure and flow** — satisfying arc or progression
- **Emotional impact / engagement** — does it land?

---

## `score`

The most flexible goal. Produce any text output and score it against a custom rubric.

### Configuration

```yaml
goal: score
task: "Natural language description of what to produce"  # required
input_file: context.md    # optional: context file the agent can read
output_file: output.md    # where the agent writes its result
target_score: 8           # 0–10, default 8
rubric: |                 # optional: custom scoring criteria
  Score 0-10 on:
  - Accuracy (3 pts): key facts are correct
  - Brevity (2 pts): under 400 words
  - Clarity (2 pts): no jargon
  - Actionability (3 pts): clear next steps
```

### Quick start

```bash
cat > .retrai.yml << 'EOF'
goal: score
task: "Write a 1-page executive summary of the attached research paper."
input_file: paper.md
output_file: summary.md
target_score: 8
rubric: |
  Score 0-10 on:
  - Accuracy: key findings faithfully represented (3 pts)
  - Brevity: ≤400 words, no padding (2 pts)
  - Clarity: accessible to a non-specialist executive (2 pts)
  - Actionability: ends with clear takeaways (2 pts)
  - Structure: clear opening, body, conclusion (1 pt)
EOF

retrai run score
```

### Example: Translate and evaluate quality

```yaml
goal: score
task: "Translate the attached English text into formal German."
input_file: original_en.md
output_file: translated_de.md
target_score: 8
rubric: |
  Score 0-10 on:
  - Accuracy: meaning preserved faithfully (4 pts)
  - Formality: appropriate register for business context (3 pts)
  - Fluency: reads naturally to a native German speaker (3 pts)
```

### Example: Write a business plan section

```yaml
goal: score
task: |
  Write the Market Analysis section of a business plan for a B2B SaaS
  company selling AI-powered inventory management to mid-market retailers.
  Include: market size, key trends, competitive landscape, target segment.
output_file: market_analysis.md
target_score: 8
rubric: |
  Score 0-10 on:
  - Market size: credible TAM/SAM/SOM with sources (3 pts)
  - Trends: 3+ relevant industry trends with evidence (2 pts)
  - Competition: names real competitors, honest differentiation (2 pts)
  - Target segment: specific, actionable ICP definition (2 pts)
  - Length: 600-900 words (1 pt)
```

### Example: Code documentation

```yaml
goal: score
task: |
  Write comprehensive docstrings and module-level documentation
  for the Python module in input.py. Follow Google docstring style.
input_file: input.py
output_file: documented.py
target_score: 9
rubric: |
  Score 0-10 on:
  - Coverage: every public function/class has a docstring (3 pts)
  - Accuracy: docstrings match actual behaviour (3 pts)
  - Style: Google docstring format with Args/Returns/Raises (2 pts)
  - Module docstring: explains purpose, usage, and key exports (2 pts)
```

### Example: Meeting minutes

```yaml
goal: score
task: |
  Write structured meeting minutes from the transcript below.
  Include: attendees, decisions made, action items with owners and deadlines.
input_file: transcript.md
output_file: minutes.md
target_score: 8
rubric: |
  Score 0-10 on:
  - Completeness: all decisions captured (3 pts)
  - Action items: each has owner and deadline (3 pts)
  - Clarity: unambiguous, scannable format (2 pts)
  - Brevity: no filler, under 500 words (2 pts)
```

### Example: Evaluate without input file

```yaml
goal: score
task: |
  Research and write a 500-word overview of the current state of
  quantum computing, suitable for a technology newsletter.
  Focus on practical near-term applications.
output_file: quantum_overview.md
target_score: 8
rubric: |
  Score 0-10 on:
  - Accuracy: factually correct, no hype (3 pts)
  - Relevance: focuses on near-term practical applications (3 pts)
  - Accessibility: clear to a non-physicist (2 pts)
  - Length: 450-550 words (2 pts)
```

---

## Agent Patterns

All three goals work with any `--pattern`:

=== "default"

    Standard single-agent loop. Best for most tasks.

    ```bash
    retrai run text-improve --pattern default
    ```

=== "mop"

    Mixture-of-Personas: the planner generates plans from multiple expert
    viewpoints (e.g. editor, critic, reader) and merges them before acting.
    Often produces higher-quality output in fewer iterations.

    ```bash
    retrai run creative --pattern mop
    ```

=== "swarm"

    Decomposes the goal into sub-tasks and runs parallel worker agents.
    Useful for large documents or multi-part tasks.

    ```bash
    retrai run score --pattern swarm
    ```

---

## Tips for Great Results

### Write a specific rubric

Vague rubrics produce vague feedback. Compare:

=== "❌ Vague"
    ```yaml
    rubric: "Score on quality and correctness."
    ```

=== "✅ Specific"
    ```yaml
    rubric: |
      Score 0-10 on:
      - Accuracy: all key facts from the source are preserved (3 pts)
      - Brevity: under 300 words with no padding (2 pts)
      - Clarity: no jargon, readable by a non-expert (3 pts)
      - Structure: clear intro, body, conclusion (2 pts)
    ```

### Set a realistic target score

| Score | Meaning |
|---|---|
| 6 | Acceptable first draft |
| 7 | Good, minor issues remain |
| 8 | Strong, ready for review |
| 9 | Excellent, near-publication quality |
| 10 | Exceptional (rarely achievable in few iterations) |

### Use `--max-iter` generously

LLM-scored goals often need 3–6 iterations to reach score 8. Set `--max-iter 15` or higher for complex tasks.

```bash
retrai run creative --max-iter 15 --model claude-sonnet-4-6
```

### Combine with `pipeline`

Chain a creative goal with a text-improve pass:

```bash
retrai pipeline "creative,text-improve" --cwd ./my-project
```

Or use `retrai pipeline` to run multiple goals in sequence:

```bash
retrai pipeline "score,text-improve" --cwd ./report-project
```
