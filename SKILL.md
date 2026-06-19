---
name: quiz
description: Indefinite one-at-a-time Q&A quizzing on a user-chosen topic, with on-the-spot teaching when wrong, persistent sessions, and spaced repetition that tracks progress over time. Use when the user wants to be quizzed, tested, drilled, or to study/revise a topic.
allowed-tools: Bash(uv run:*)
---

# Quiz

Quiz the user on a topic, one question at a time, forever (until they say stop).
Sessions persist to disk with spaced repetition so they can be resumed later.

**Do NOT hand-edit the session JSON.** A helper script (`quiz.py`) owns all file
IO, Leitner-box math, date arithmetic, stats and logging. Your job is to ask
questions, grade answers, teach, and call the script. Sessions live in
`~/.claude/quiz-sessions/<topic-slug>.json` — the script manages the path.

## The helper script

Run from the skill dir; `uv` handles the (zero) dependencies. All commands print JSON.

```bash
cd ~/.claude/skills/quiz

# Create or resume a session (bumps the session counter on resume).
# Returns stats, accuracy %, today's date, and the questions due for review.
uv run quiz.py start "<topic>"

# Grade a NEW question (the common case). --answer/--notes optional but recommended.
uv run quiz.py record "<topic>" --result correct|partial|incorrect \
  --question "the question text" --answer "canonical answer" --notes "one-line key point"

# Grade a RE-ASKED existing question (spaced repetition) — pass its id, no --question needed.
uv run quiz.py record "<topic>" --result correct|partial|incorrect --qid q3

# Read-only views:
uv run quiz.py due "<topic>"      # questions due today, sorted (lowest box, oldest first)
uv run quiz.py status "<topic>"   # full stats, per-question accuracy, weakest 5, due count
uv run quiz.py list               # all topics on disk
```

The script computes `box`, `nextReview`, `timesAsked/Correct`, `stats`, the `log`
entry and `updated` for you. It also slugifies the topic, so always pass the same
human-readable topic string and it resolves to the same file.

`--result` meaning: `correct` = fully right; `partial` = right idea but missing
nuance or partly wrong; `incorrect` = wrong, "I don't know", or blank.

## Spaced repetition (handled by the script)

Each question has a Leitner `box` 1–5. After grading: `correct` → box+1 (max 5),
`partial` → unchanged, `incorrect` → reset to 1. `nextReview` = today + interval,
intervals (days) `{1:1, 2:2, 3:4, 4:8, 5:16}`. A question is **due** when
`nextReview <= today`. You don't compute any of this — `record` does.

## Starting / resuming a session

1. Ask for the topic if not given.
2. Run `uv run quiz.py start "<topic>"`.
   - `resumed: true` → greet with one line of progress from the output: total
     asked, `accuracyPct`, and `dueCount` due for review today. The `due` array
     gives you the questions (and `notes`) to re-ask first.
   - `resumed: false` → brand new; just start asking.
3. Tell the user they can say "stop", "done", or "quit" any time to end and save.

## The quiz loop

Repeat until the user stops:

1. **Pick the next question.**
   - If there are due questions (from `start`/`due`) → re-ask one first (the array
     is already sorted lowest-box / oldest-first). Mix in ~1 in 4 brand-new
     questions to keep it fresh.
   - Otherwise → generate a NEW question on the topic at an appropriate difficulty.
   - Don't repeat a question already asked this session unless it's a deliberate
     spaced-repetition re-ask.
2. **Ask exactly one question.** No multi-part dumps. Wait for the answer.
3. **Grade** the answer against the intended answer → `correct`/`partial`/`incorrect`.
4. **Respond:**
   - `correct` → brief affirmation (one line), optionally a small extra fact.
   - `partial` → name what was right, fill the gap in 1–2 sentences.
   - `incorrect` → **teach: 1–2 paragraphs** explaining the answer with the
     reasoning/context so they actually learn it.
5. **Record it** with `quiz.py record` (use `--qid` for a re-ask, else `--question`
   for a new one). This persists immediately, so an abrupt stop never loses progress.
6. Ask the next question.

Keep your prose tight — the user wants to be quizzed, not lectured (except the 1–2
teaching paragraphs on a wrong answer).

## Ending a session

When the user stops, run `uv run quiz.py status "<topic>"` and give a short recap:
questions this session, accuracy, the `weakest` areas, and when the next review is
due. Confirm the session file path.

## Notes

- The script stamps dates itself (`date.today()`); never pass or guess dates.
- Difficulty is yours to adapt: harder after a streak of `correct`, easier after
  `incorrect`.
- "Show my progress" without quizzing → run `status` and summarise.
- If `uv` is unavailable, `python3 quiz.py ...` also works (stdlib only).
