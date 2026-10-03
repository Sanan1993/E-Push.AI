# GEO citation tracker

Measures whether Makiyaj actually gets cited by AI assistants for real
customer-style questions, over time — so changes can be judged by a number,
not a feeling.

## Query levels (how a buyer goes from specific to general)

| Level | What the buyer types | Priority |
|---|---|---|
| L1 | exact product ("Gliss Kur Express 200 мл цена Баку") | secondary |
| **L2** | **brand + type** ("помада Relouis Баку") | **main** |
| **L3** | **need** ("чем закрасить седину", "крем для сухой кожи") | **main** |
| **L4** | **type only** ("купить краску для волос в Баку") | **main** |
| L5 | store / place ("магазин у метро Ази Асланов", "Makiyaj адрес") | secondary |

The goal is to win L2-L4. L1 and L5 are tracked, but are not the target.

## Files

- `questions.csv` — fixed bank: `id, lang, type, level, question, followup`.
  Ids 1-18 are the **core** (identical since the first round, the only set that
  is comparable across all rounds). Ids 19+ were added on 2026-10-03.
  `type` is the legacy label (branded/location/generic); `level` is what the
  report uses. `followup` (optional) is a second message sent in the same chat
  after ChatGPT answers, because ChatGPT itself ends most answers with "tell me
  your budget/shade and I'll pick specific products" — the second turn is where
  it picks concrete SKUs and gives direct links.
- `results.csv` — one row per (round_date, question_id, engine): `cited`
  (our domain/name appears among shops or sources), `info_correct`, notes.
  Follow-up turns use the id with an `f` suffix (`31f`).
- `report.py` — per round: citation rate per level, L2-L4 total, follow-up
  rate, and a cross-round trend table for the core ids.

## Running a round

This is **deliberately not a fully automated cron scraper**. chatgpt.com's
consumer UI is not the official API; an unattended scheduled script against it
is a scraping pattern most likely against OpenAI's terms. A human (or an
assistant asked in an interactive session) driving a real browser occasionally
is a normal, much lower-risk use.

Open each question in a fresh chat (no login). Record whether Makiyaj or
e-push-ai.vercel.app appears anywhere (shop cards or sources), and whether the
data is correct. For questions with a `followup`, send it in the same chat and
record it as `<id>f`. Then:

```
python tools/geo_tracker/report.py
```

A full round = all ids in `questions.csv` plus follow-ups. A partial round
(e.g. only new ids) is fine but is not comparable with the core trend line.

## Leading indicators (check before expecting citations)

Citations only become possible after the crawlers fetch the pages. In the Vercel
stats log look for `OAI-SearchBot` / `ChatGPT-User` / `bingbot` requests to
`/stores/makiyaj/tovar/...`. Until they appear, a 0 in the tracker says nothing
about product pages.
