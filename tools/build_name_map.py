"""Собирает data/name_map.csv: штрихкод -> бренд / категория / объём.

Берёт из локального каталога маркетплейса (SQLite) только факты о товарах,
которые есть в нашей таблице. Сам каталог в репозиторий не попадает — он
весит ~1 ГБ и лежит на компьютере; GitHub Action читает готовый маленький CSV.

Запуск (из корня репозитория):
    python tools/build_name_map.py --catalog путь\\к\\catalog.sqlite
Перезапускать, когда у партнёра появляются новые товары.
"""

import argparse
import csv
import io
import os
import sqlite3
import sys
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generate_llms import (  # noqa: E402
    NAME_MAP_FILE,
    SHEET_CSV_URL,
    extract_size,
    normalize_barcode,
)


def our_barcodes():
  req = urllib.request.Request(SHEET_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
  csv_data = urllib.request.urlopen(req).read().decode("utf-8")
  df = pd.read_csv(io.StringIO(csv_data), header=None, dtype=str).iloc[1:]
  return {normalize_barcode(v) for v in df[2] if normalize_barcode(v)}


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--catalog", required=True, help="путь к catalog.sqlite")
  args = parser.parse_args()

  wanted = our_barcodes()
  con = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True)

  rows = {}
  query = (
      "select barcode, brand, category, name from uniq "
      "where barcode is not null and barcode != ''"
  )
  for barcode, brand, category, name in con.execute(query):
    key = normalize_barcode(barcode)
    if key in wanted and key not in rows:
      rows[key] = {
          "barcode": key,
          "brand": (brand or "").strip(),
          "category": (category or "").strip(),
          "size": extract_size(name) or "",
      }

  os.makedirs(os.path.dirname(NAME_MAP_FILE), exist_ok=True)
  with open(NAME_MAP_FILE, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["barcode", "brand", "category", "size"], lineterminator="\n"
    )
    writer.writeheader()
    for key in sorted(rows):
      writer.writerow(rows[key])

  print(f"Наших штрихкодов: {len(wanted)} | найдено в каталоге: {len(rows)}")
  print(f"Записано: {NAME_MAP_FILE}")


if __name__ == "__main__":
  main()
