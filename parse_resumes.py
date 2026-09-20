"""
Шаг 2. Парсинг полей со страниц отдельных резюме (по ссылкам из resume_links.csv)
и сборка итогового датасета resumes_dataset.csv.

Библиотеки: requests, BeautifulSoup (bs4), lxml, json, html, re, pandas, time, random

ВАЖНО: hh.ru встраивает данные резюме в структурированном виде внутри
<template id="HH-Lux-InitialState">...JSON...</template>. Это НАМНОГО надёжнее,
чем парсить data-qa атрибуты вручную: JSON-структура стабильнее верстки и
не меняется при редизайнах страницы. Поэтому основной способ извлечения —
через этот JSON, а BeautifulSoup используется только чтобы его найти.
"""

import json
import html as html_module
import re
import time
import random

import requests
from bs4 import BeautifulSoup
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

SLEEP_MIN, SLEEP_MAX = 0.1, 0.4


def extract_initial_state(html_text: str) -> dict | None:
    """Достаёт и парсит JSON из <template id="HH-Lux-InitialState">."""
    soup = BeautifulSoup(html_text, "lxml")
    tpl = soup.find("template", id="HH-Lux-InitialState")
    if not tpl:
        return None
    # Содержимое template — HTML-экранированный JSON (&#34; вместо ")
    raw = tpl.decode_contents()
    raw = html_module.unescape(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _get(d, *path, default=None):
    """Безопасный доступ по цепочке ключей, например _get(state, 'resume', 'title', 'value')."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def parse_resume_page(html_text: str) -> dict:
    state = extract_initial_state(html_text)
    if not state:
        # Резервный путь на случай, если структура страницы изменится
        return {
            "title": None, "salary": None, "age": None, "city": None,
            "gender": None, "citizenship": None, "education_level": None,
            "experience_years": None, "experience_months": None,
            "skills": None, "languages": None, "about": None,
        }

    resume = state.get("resume", {}) or {}

    title = _get(resume, "title", "value")

    salary_val = _get(resume, "salary", "value")
    salary = None
    if isinstance(salary_val, dict):
        salary = f"{salary_val.get('amount')} {salary_val.get('currency')}"

    age = _get(resume, "age", "value")
    city = _get(resume, "area", "value", "title")
    gender = _get(resume, "gender", "value")

    citizenship_list = _get(resume, "citizenship", "value", default=[])
    citizenship = ", ".join(c.get("title", "") for c in citizenship_list) if citizenship_list else None

    education_level = _get(resume, "educationLevel", "value")

    total_exp = resume.get("totalExperience") or {}
    experience_years = total_exp.get("years")
    experience_months = total_exp.get("months")

    skills_list = _get(resume, "keySkills", "value", default=[])
    skills = ", ".join(s.get("string", "") for s in skills_list) if skills_list else None

    lang_list = _get(resume, "language", "value", default=[])
    languages = "; ".join(
        f"{l.get('title', '')} ({l.get('degree', '')})" for l in lang_list
    ) if lang_list else None

    return {
        "title": title,
        "salary": salary,
        "age": age,
        "city": city,
        "gender": gender,
        "citizenship": citizenship,
        "education_level": education_level,
        "experience_years": experience_years,
        "experience_months": experience_months,
        "skills": skills,
        "languages": languages,
    }


OUTPUT_FILE = "resumes_dataset.csv"
CONSECUTIVE_403_LIMIT = 8  # остановка при подозрении на блокировку


def main():
    links_df = pd.read_csv("resume_links.csv")

    # Пропускаем уже обработанные ссылки при повторном запуске
    already_done = set()
    try:
        done_df = pd.read_csv(OUTPUT_FILE)
        already_done = set(done_df["source_url"])
        print(f"Уже обработано ранее: {len(already_done)} резюме, продолжаем")
    except FileNotFoundError:
        pass

    session = requests.Session()
    session.headers.update(HEADERS)

    consecutive_403 = 0
    processed_count = len(already_done)

    for i, row in links_df.iterrows():
        url, category = row["url"], row["category"]
        if url in already_done:
            continue

        try:
            resp = session.get(url, timeout=15)
        except requests.exceptions.RequestException as e:
            print(f"[{i}] ошибка запроса {url}: {e}")
            continue

        if resp.status_code == 403:
            consecutive_403 += 1
            print(f"[{i}] 403 на {url} — подряд: {consecutive_403}")
            if consecutive_403 >= CONSECUTIVE_403_LIMIT:
                print("Слишком много 403 подряд — похоже на блокировку. Останавливаемся.")
                break
            time.sleep(5)
            continue
        consecutive_403 = 0

        if resp.status_code != 200:
            print(f"[{i}] статус {resp.status_code} на {url}")
            continue

        try:
            fields = parse_resume_page(resp.text)
        except Exception as e:
            print(f"[{i}] ошибка парсинга {url}: {e}")
            continue
        fields["category"] = category
        fields["source_url"] = url

        # Дозапись сразу в CSV — прогресс не теряется при обрыве
        row_df = pd.DataFrame([fields])
        row_df.to_csv(
            OUTPUT_FILE,
            mode="a",
            header=not _file_has_content(OUTPUT_FILE),
            index=False,
            encoding="utf-8-sig",
        )
        already_done.add(url)
        processed_count += 1

        if processed_count % 20 == 0:
            print(f"Обработано {processed_count}/{len(links_df)}")

        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    print(f"\nГотово. Всего резюме в датасете: {processed_count}")


def _file_has_content(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return bool(f.readline())
    except FileNotFoundError:
        return False

if __name__ == "__main__":
    main()