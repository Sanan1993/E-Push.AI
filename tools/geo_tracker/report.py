"""Отчёт по раундам трекера цитирований (tools/geo_tracker/).

Вопросы разбиты на уровни по тому, как покупатель идёт от конкретного к общему:
  L1 точный товар · L2 бренд+тип · L3 потребность · L4 только тип · L5 магазин/место.
Главные для нас L2-L4 (там реально выигрывать); L1 и L5 — вторичны.

Строки с question_id вида "31f" — второй ход (follow-up) в том же чате.
"ядро" = вопросы id 1-18, существовавшие с первого раунда: только их можно
честно сравнивать между всеми раундами.

Запуск: python tools/geo_tracker/report.py
"""

import collections
import csv
import os
import sys

# Windows-консоль по умолчанию cp1251 и падает на кириллице/эмодзи в print().
if hasattr(sys.stdout, "reconfigure"):
  sys.stdout.reconfigure(encoding="utf-8")

DIR = os.path.dirname(__file__)
LEVELS = ["L1", "L2", "L3", "L4", "L5"]
MAIN_LEVELS = ["L2", "L3", "L4"]
LEVEL_NAMES = {
    "L1": "точный товар", "L2": "бренд+тип", "L3": "потребность",
    "L4": "только тип", "L5": "магазин/место",
}
CORE_MAX_ID = 18


def load_csv(name):
  with open(os.path.join(DIR, name), encoding="utf-8", newline="") as f:
    return list(csv.DictReader(f))


def base_id(qid):
  return qid[:-1] if qid.endswith("f") else qid


def is_followup(qid):
  return qid.endswith("f")


def is_core(qid):
  return int(base_id(qid)) <= CORE_MAX_ID


def tally(rows, questions):
  """{level: [cited, total]} только по первым ходам."""
  out = collections.defaultdict(lambda: [0, 0])
  for r in rows:
    if is_followup(r["question_id"]):
      continue
    level = questions.get(base_id(r["question_id"]), {}).get("level", "?")
    out[level][1] += 1
    if r["cited"] == "yes":
      out[level][0] += 1
  return out


def fmt(c, t):
  return f"{c}/{t}" if t else "-"


def main():
  questions = {q["id"]: q for q in load_csv("questions.csv")}
  results = load_csv("results.csv")

  by_round = collections.defaultdict(list)
  for r in results:
    by_round[(r["round_date"], r["engine"])].append(r)

  for (round_date, engine), rows in sorted(by_round.items()):
    first = [r for r in rows if not is_followup(r["question_id"])]
    follow = [r for r in rows if is_followup(r["question_id"])]
    total = len(first)
    cited = sum(1 for r in first if r["cited"] == "yes")
    print(f"\n=== {round_date} / {engine}: {cited}/{total} процитировано ({cited/total:.0%}) ===")

    t_all = tally(first, questions)
    t_core = tally([r for r in first if is_core(r["question_id"])], questions)
    has_extra = any(not is_core(r["question_id"]) for r in first)
    for level in LEVELS:
      c, t = t_all.get(level, [0, 0])
      if not t:
        continue
      star = "*" if level in MAIN_LEVELS else " "
      line = f"  {star}{level} {LEVEL_NAMES[level]:14s}: {fmt(c, t):>6s}"
      if has_extra:
        line += f"   (ядро: {fmt(*t_core.get(level, [0, 0]))})"
      print(line)

    main_c = sum(t_all[l][0] for l in MAIN_LEVELS if l in t_all)
    main_t = sum(t_all[l][1] for l in MAIN_LEVELS if l in t_all)
    if main_t:
      print(f"  главные L2-L4: {main_c}/{main_t} ({main_c/main_t:.0%})")

    if follow:
      fc = sum(1 for r in follow if r["cited"] == "yes")
      ids = ", ".join(r["question_id"] for r in follow if r["cited"] == "yes") or "-"
      print(f"  второй ход (follow-up): {fc}/{len(follow)} процитировано (id: {ids})")

    wrong = [r for r in rows if r["cited"] == "yes" and r["info_correct"] == "no"]
    if wrong:
      print(f"  [!] процитирован с неверными данными: {len(wrong)}"
            f" (id {', '.join(r['question_id'] for r in wrong)})")

  rounds = sorted({r["round_date"] for r in results})
  if len(rounds) > 1:
    print("\n--- Динамика по раундам, ЯДРО id 1-18 (сравнимо между раундами) ---")
    for level in LEVELS:
      parts = []
      for round_date in rounds:
        rows = [r for r in results if r["round_date"] == round_date
                and not is_followup(r["question_id"]) and is_core(r["question_id"])]
        c, t = tally(rows, questions).get(level, [0, 0])
        parts.append(f"{round_date}: {fmt(c, t)}" if t else None)
      parts = [p for p in parts if p]
      if parts:
        star = "*" if level in MAIN_LEVELS else " "
        print(f"  {star}{level} {LEVEL_NAMES[level]:14s} " + " | ".join(parts))


if __name__ == "__main__":
  main()
