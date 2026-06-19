# quiz

A [Claude Code](https://docs.claude.com/en/docs/claude-code) skill for being quizzed on any topic, one question at a time, with spaced repetition.

You pick a topic; Claude asks a question, grades your answer, teaches you when you're wrong (1–2 paragraphs), then moves on. Sessions persist to disk so you can resume later — questions you miss come back sooner (Leitner boxes), and progress is tracked over time.

## Install

Copy the folder into your skills directory:

```bash
git clone https://github.com/sbracegirdle/quiz-skill.git ~/.claude/skills/quiz
```

## Use

```
/quiz
```

Then name a topic. Say "stop" any time to end and save. Sessions are stored as JSON in `~/.claude/quiz-sessions/`.

## Files

- `SKILL.md` — instructions Claude follows to run the quiz.
- `quiz.py` — helper script that owns session storage, stats, and the spaced-repetition schedule (stdlib only; runs via `uv` or `python3`).
