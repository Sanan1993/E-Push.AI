"""Пинг IndexNow (Bing/Yandex и др.) по страницам, изменившимся в последнем коммите.

Запускается в GitHub Action после коммита автообновления каталога.
Best-effort: ошибка пинга не должна ронять пайплайн.
"""

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

from generate_llms import (
    INDEXNOW_KEY,
    SITE_ROOT,
    STORE_CANONICAL_URL,
    STORE_SLUG,
)

HOST = SITE_ROOT.replace("https://", "")
ENDPOINT = "https://api.indexnow.org/indexnow"
STORE_DIR = f"stores/{STORE_SLUG}"


def changed_files():
  try:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=AM", "HEAD~1", "HEAD"],
        text=True,
    )
  except Exception:
    return None
  return [line.strip() for line in out.splitlines() if line.strip()]


def file_to_url(path):
  if path == f"{STORE_DIR}/index.html":
    return STORE_CANONICAL_URL
  m = re.fullmatch(rf"{re.escape(STORE_DIR)}/page-(\d+)\.html", path)
  if m:
    return f"{SITE_ROOT}/{STORE_DIR}/page-{m.group(1)}.html"
  if path == "llms.txt":
    return f"{SITE_ROOT}/llms.txt"
  if path == f"{STORE_DIR}/llms.txt":
    return f"{SITE_ROOT}/{STORE_DIR}/llms.txt"
  return None


def main():
  dry_run = "--dry-run" in sys.argv
  files = changed_files()
  if files is None:
    print("Не удалось получить diff — отправляю только главные адреса.")
    urls = [STORE_CANONICAL_URL, f"{SITE_ROOT}/llms.txt"]
  else:
    urls = sorted({u for u in map(file_to_url, files) if u})

  if not urls:
    print("Индексируемых изменений нет — пинг не нужен.")
    return

  print(f"К отправке в IndexNow: {len(urls)} URL")
  if dry_run:
    print("\n".join(urls))
    return

  body = json.dumps({
      "host": HOST,
      "key": INDEXNOW_KEY,
      "keyLocation": f"{SITE_ROOT}/{INDEXNOW_KEY}.txt",
      "urlList": urls,
  }).encode("utf-8")
  req = urllib.request.Request(
      ENDPOINT,
      data=body,
      headers={"Content-Type": "application/json; charset=utf-8"},
      method="POST",
  )
  try:
    with urllib.request.urlopen(req, timeout=30) as resp:
      print(f"IndexNow ответил: HTTP {resp.status}")
  except urllib.error.HTTPError as e:
    print(f"IndexNow отклонил запрос: HTTP {e.code} {e.reason}")
  except Exception as e:
    print(f"IndexNow недоступен: {e}")


if __name__ == "__main__":
  main()
