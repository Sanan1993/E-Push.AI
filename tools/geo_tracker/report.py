"""Отчёт по раундам трекера цитирований (tools/geo_tracker/).

Читает questions.csv + results.csv, печатает долю цитирований по раундам и по
типу вопроса (branded / location / generic) — чтобы видеть, реально ли новые
инструменты (FAQ, страница цен и т.д.) сдвигают именно generic-запросы, а не
просто общее число.

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


def load_csv(name):
  with open(os.path.join(DIR, name), encoding="utf-8", newline="") as f:
    return list(csv.DictReader(f))


def main():
  questions = {q["id"]: q for q in load_csv("questions.csv")}
  results = load_csv("results.csv")

  by_round = collections.defaultdict(list)
  for r in results:
    by_round[(r["round_date"], r["engine"])].append(r)

  for (round_date, engine), rows in sorted(by_round.items()):
    total = len(rows)
    cited = sum(1 for r in rows if r["cited"] == "yes")
    print(f"\n=== {round_date} / {engine}: {cited}/{total} процитировано ({cited/total:.0%}) ===")

    by_type = collections.defaultdict(lambda: [0, 0])
    for r in rows:
      qtype = questions.get(r["question_id"], {}).get("type", "?")
      by_type[qtype][1] += 1
      if r["cited"] == "yes":
        by_type[qtype][0] += 1
    for qtype, (c, t) in sorted(by_type.items()):
      print(f"  {qtype:10s}: {c}/{t} ({c/t:.0%})")

    wrong = [r for r in rows if r["cited"] == "yes" and r["info_correct"] == "no"]
    if wrong:
      print(f"  [!] процитирован с неверными данными: {len(wrong)}"
            f" (id {', '.join(r['question_id'] for r in wrong)})")

  rounds = sorted({r["round_date"] for r in results})
  if len(rounds) > 1:
    print("\n--- Сравнение раундов (generic-вопросы, самое важное) ---")
    for round_date in rounds:
      rows = [r for r in results if r["round_date"] == round_date
              and questions.get(r["question_id"], {}).get("type") == "generic"]
      if not rows:
        continue
      cited = sum(1 for r in rows if r["cited"] == "yes")
      print(f"  {round_date}: {cited}/{len(rows)} generic-вопросов процитировано")


if __name__ == "__main__":
  main()
