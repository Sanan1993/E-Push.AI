# GEO citation tracker

Measures whether Makiyaj actually gets cited by AI assistants for real
customer-style questions, over time — so changes like the FAQ blocks or the
prices page can be judged by a number, not a feeling.

## Files

- `questions.csv` — fixed question bank (id, lang, type, question). `type` is
  `branded` (name/address already in the question), `location` (metro/район
  in the question, no name), or `generic` (no hint at all — this is the
  number that actually matters, since branded queries already work).
- `results.csv` — one row per (round_date, question_id, engine): was Makiyaj
  cited (`cited`), and if so was the info correct (`info_correct`), plus a
  free-text note.
- `report.py` — reads both, prints citation rate per round and per type.

## Running a new round

This is **deliberately not a fully automated cron scraper**. ChatGPT's
consumer web UI (chatgpt.com) is not the official API — running an unattended
scheduled script against it is a scraping/automation pattern most likely
against OpenAI's usage terms. A human (or an assistant, asked to do it in an
interactive session) driving a real browser occasionally is a normal, much
lower-risk use.

To run a round: open each question in `questions.csv` fresh (new chat, no
prior context) in chatgpt.com without logging in, note whether Makiyaj (or
e-push-ai.vercel.app) appears anywhere in the answer, and whether the address/
phone/data given is correct. Append one row per question to `results.csv`
with today's date. Then:

```
python tools/geo_tracker/report.py
```

Compare the `generic` row across rounds — that's the number the FAQ/prices
tools were meant to move.
