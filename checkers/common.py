"""
各サイトのチェッカーが共通で使うユーティリティ関数。
"""

import time

import re
import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}


def fetch_text(url: str, timeout: int = 30, retries: int = 2) -> str:
    """
    ページを取得し、HTMLタグを除いた visible text を返す。
    判定ロジック（マーカー文字列の有無）はこのテキストに対して行う。

    一時的なタイムアウトなどに備えて、失敗時は少し待ってから
    数回リトライする。
    """
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # script/style は文言判定のノイズになるので除去
            for tag in soup(["script", "style"]):
                tag.decompose()

            return soup.get_text(separator="\n")
        except requests.RequestException as e:
            last_error = e
            if attempt < retries:
                time.sleep(3)
    raise last_error


def extract_prices(text: str) -> list[int]:
    """
    テキスト中の「¥12,345」「12,345円」のような価格表記をすべて拾い、
    整数のリストにして返す（安すぎる/高すぎる誤検知を減らすため
    5桁以上の数値のみを価格とみなす）。
    """
    prices = []
    for m in re.finditer(r"[¥￥]\s?([\d,]{5,9})", text):
        prices.append(int(m.group(1).replace(",", "")))
    for m in re.finditer(r"([\d,]{5,9})\s?円", text):
        prices.append(int(m.group(1).replace(",", "")))
    return prices


def contains_any(text: str, markers: list[str]) -> str | None:
    """text の中に markers のいずれかが含まれていれば、最初に見つかった
    マーカー文字列を返す。見つからなければ None。"""
    for marker in markers:
        if marker in text:
            return marker
    return None
