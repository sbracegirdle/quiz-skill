#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Quiz session store helper.

Owns all JSON IO, Leitner-box math, date arithmetic, stats and logging so the
calling agent only decides the grade and supplies question/answer text.

Sessions live in ~/.claude/quiz-sessions/<topic-slug>.json

Commands (all print JSON to stdout):
  start  <topic>                      create-or-resume; bumps sessions on resume
  record <topic> --result R ...       grade an answer (new or re-asked question)
  due    <topic>                      questions due for review today (sorted)
  status <topic>                      stats + per-question accuracy + due count
  list                                all topics on disk

record flags:
  --result   correct|partial|incorrect   (required)
  --question "text"                       question text (required for NEW)
  --answer   "text"                       canonical answer (NEW; optional update)
  --notes    "text"                       one-line key point (NEW; optional update)
  --qid      q3                           re-ask an EXISTING question by id
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "quiz-sessions"
INTERVALS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}  # box -> days until next review


def slugify(topic: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", topic.lower())).strip("-")


def path_for(topic: str) -> Path:
    return SESSIONS_DIR / f"{slugify(topic)}.json"


def today_str() -> str:
    return date.today().isoformat()


def add_days(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def next_box(box: int, result: str) -> int:
    if result == "correct":
        return min(box + 1, 5)
    if result == "incorrect":
        return 1
    return box  # partial


def load(topic: str) -> dict:
    p = path_for(topic)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def save(topic: str, data: dict) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path_for(topic).write_text(json.dumps(data, indent=2) + "\n")


def fresh(topic: str) -> dict:
    t = today_str()
    return {
        "topic": topic,
        "created": t,
        "updated": t,
        "stats": {"sessions": 1, "totalAsked": 0, "totalCorrect": 0},
        "questions": [],
        "log": [],
    }


def due_questions(data: dict) -> list:
    t = today_str()
    due = [q for q in data["questions"] if q.get("nextReview", t) <= t]
    # Spaced-repetition priority: lowest box first, then oldest review date.
    due.sort(key=lambda q: (q["box"], q.get("nextReview", "")))
    return due


def emit(obj) -> None:
    print(json.dumps(obj, indent=2))


def cmd_start(args):
    data = load(args.topic)
    p = path_for(args.topic)
    if data is None:
        data = fresh(args.topic)
        resumed = False
    else:
        data["stats"]["sessions"] = data["stats"].get("sessions", 0) + 1
        data["updated"] = today_str()
        resumed = True
    save(args.topic, data)
    due = due_questions(data)
    st = data["stats"]
    acc = round(100 * st["totalCorrect"] / st["totalAsked"]) if st["totalAsked"] else None
    emit({
        "topic": data["topic"],
        "slug": slugify(args.topic),
        "path": str(p),
        "resumed": resumed,
        "stats": st,
        "accuracyPct": acc,
        "today": today_str(),
        "dueCount": len(due),
        "due": [{"id": q["id"], "question": q["question"], "box": q["box"],
                 "notes": q.get("notes", "")} for q in due],
    })


def cmd_record(args):
    data = load(args.topic)
    if data is None:
        data = fresh(args.topic)
    t = today_str()
    qmap = {q["id"]: q for q in data["questions"]}

    if args.qid:  # re-ask existing
        q = qmap.get(args.qid)
        if q is None:
            emit({"error": f"unknown qid {args.qid}"})
            sys.exit(1)
        q["box"] = next_box(q["box"], args.result)
        q["timesAsked"] += 1
        if args.result == "correct":
            q["timesCorrect"] += 1
        q["lastAsked"] = t
        q["nextReview"] = add_days(t, INTERVALS[q["box"]])
        if args.question:
            q["question"] = args.question
        if args.answer:
            q["answer"] = args.answer
        if args.notes:
            q["notes"] = args.notes
    else:  # new question
        if not args.question:
            emit({"error": "--question required for a new question"})
            sys.exit(1)
        nums = [int(m.group(1)) for q in data["questions"]
                if (m := re.match(r"q(\d+)$", q["id"]))]
        qid = f"q{(max(nums) + 1) if nums else 1}"
        box = next_box(1, args.result)
        q = {
            "id": qid,
            "question": args.question,
            "answer": args.answer or "",
            "box": box,
            "timesAsked": 1,
            "timesCorrect": 1 if args.result == "correct" else 0,
            "lastAsked": t,
            "nextReview": add_days(t, INTERVALS[box]),
            "notes": args.notes or "",
        }
        data["questions"].append(q)

    data["log"].append({"date": t, "qid": q["id"], "result": args.result})
    data["stats"]["totalAsked"] += 1
    if args.result == "correct":
        data["stats"]["totalCorrect"] += 1
    data["updated"] = t
    save(args.topic, data)
    emit({"recorded": q, "stats": data["stats"]})


def cmd_due(args):
    data = load(args.topic)
    if data is None:
        emit({"error": "no such session", "topic": args.topic})
        sys.exit(1)
    emit({"today": today_str(), "due": due_questions(data)})


def cmd_status(args):
    data = load(args.topic)
    if data is None:
        emit({"error": "no such session", "topic": args.topic})
        sys.exit(1)
    st = data["stats"]
    acc = round(100 * st["totalCorrect"] / st["totalAsked"]) if st["totalAsked"] else None
    qs = sorted(
        ({"id": q["id"], "question": q["question"], "box": q["box"],
          "timesAsked": q["timesAsked"], "timesCorrect": q["timesCorrect"],
          "accuracyPct": round(100 * q["timesCorrect"] / q["timesAsked"]),
          "nextReview": q.get("nextReview")} for q in data["questions"]),
        key=lambda q: (q["accuracyPct"], q["box"]),
    )
    emit({
        "topic": data["topic"],
        "stats": st,
        "accuracyPct": acc,
        "today": today_str(),
        "dueCount": len(due_questions(data)),
        "weakest": qs[:5],
        "questions": qs,
    })


def cmd_list(_args):
    if not SESSIONS_DIR.exists():
        emit({"topics": []})
        return
    out = []
    for p in sorted(SESSIONS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            out.append({"topic": d.get("topic"), "slug": p.stem,
                        "stats": d.get("stats"), "updated": d.get("updated")})
        except (json.JSONDecodeError, OSError):
            continue
    emit({"topics": out})


def main():
    ap = argparse.ArgumentParser(description="Quiz session store helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start"); s.add_argument("topic"); s.set_defaults(fn=cmd_start)

    r = sub.add_parser("record")
    r.add_argument("topic")
    r.add_argument("--result", required=True, choices=["correct", "partial", "incorrect"])
    r.add_argument("--question"); r.add_argument("--answer")
    r.add_argument("--notes"); r.add_argument("--qid")
    r.set_defaults(fn=cmd_record)

    d = sub.add_parser("due"); d.add_argument("topic"); d.set_defaults(fn=cmd_due)
    st = sub.add_parser("status"); st.add_argument("topic"); st.set_defaults(fn=cmd_status)
    sub.add_parser("list").set_defaults(fn=cmd_list)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
