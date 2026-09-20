"""
Шаг 1. Сбор ссылок на открытые резюме с hh.ru по категориям (профессиям).

Библиотеки: requests, BeautifulSoup (bs4), lxml, time, random, re, urllib.parse, pandas
"""

import time
import random
import re
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

BASE = "https://hh.ru"

# 8 категорий -> поисковый текст на hh
CATEGORIES = {
    "Python-разработчик": "Python разработчик",
    "Frontend-разработчик": "Frontend разработчик",
    "Data Scientist": "Data Scientist",
    "Бухгалтер": "Бухгалтер",
    "Менеджер по продажам": "Менеджер по продажам",
    "Дизайнер": "Дизайнер",
    "HR-менеджер": "HR менеджер",
    "Юрист": "Юрист",
    "Маркетолог": "Маркетолог",
    "Системный администратор": "Системный администратор",
    "Тестировщик": "Тестировщик",
    "Водитель": "Водитель",
}

PAGES_PER_CATEGORY = 20   # ~20 резюме на страницу -> ~250-300 ссылок на категорию с запасом
SLEEP_MIN, SLEEP_MAX = 0.5, 1.0


def build_search_url(text: str, page: int) -> str:
    return (
        f"{BASE}/search/resume?area=1&exp_period=all_time&logic=normal"
        f"&no_magic=true&ored_clusters=true&pos=full_text&search_period=0"
        f"&text={quote(text)}&order_by=publication_time&page={page}"
    )


def extract_resume_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/resume/" in href:
            full = urljoin(BASE, href.split("?")[0])
            links.add(full)
    return list(links)


def collect_links_for_category(category: str, search_text: str) -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)
    collected = []

    for page in range(PAGES_PER_CATEGORY):
        url = build_search_url(search_text, page)
        try:
            resp = session.get(url, timeout=15)
        except requests.exceptions.RequestException as e:
            print(f"[{category}] page={page} ошибка запроса: {e}")
            break

        if resp.status_code == 403:
            print(f"[{category}] 403 — вероятно, антибот блокировка. Останавливаемся.")
            break
        if resp.status_code != 200:
            print(f"[{category}] page={page} статус={resp.status_code}")
            break

        links = extract_resume_links(resp.text)
        if not links:
            print(f"[{category}] page={page}: резюме не найдено, конец выдачи")
            break

        for link in links:
            collected.append({"category": category, "url": link})

        print(f"[{category}] page={page}: +{len(links)} ссылок (всего {len(collected)})")
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    return collected


def main():
    all_links = []
    for category, search_text in CATEGORIES.items():
        all_links.extend(collect_links_for_category(category, search_text))
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    df = pd.DataFrame(all_links).drop_duplicates(subset="url")
    df.to_csv("resume_links.csv", index=False, encoding="utf-8-sig")
    print(f"\nИтого собрано ссылок: {len(df)}")
    print(df["category"].value_counts())


if __name__ == "__main__":
    main()