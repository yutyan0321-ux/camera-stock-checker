"""
各サイトのチェッカーが共通で使うユーティリティ関数。
"""

import time

import re
from curl_cffi import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}


def _fetch_response(url: str, timeout: int = 30, retries: int = 2):
    """ページを取得し、requestsのレスポンスオブジェクトを返す（内部用）。"""
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=timeout, impersonate="chrome"
            )
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(3)
    raise last_error


def fetch_soup(url: str, timeout: int = 30, retries: int = 2) -> BeautifulSoup:
    """
    ページを取得し、BeautifulSoupオブジェクトをそのまま返す。

    fetch_text() と違い、リンク(href)などのHTML構造を保持したまま扱える。
    検索結果ページのように「1ページに複数の商品が並ぶ」ものを解析する
    ときは、こちらを使ってリンクごとに商品を区別する必要がある
    （fetch_text() はリンク情報を失った「見た目のテキストだけ」を返す
    ため、商品の区切りやURLが分からなくなってしまう）。
    """
    resp = _fetch_response(url, timeout=timeout, retries=retries)
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup


def fetch_text(url: str, timeout: int = 30, retries: int = 2) -> str:
    """
    ページを取得し、HTMLタグを除いた visible text を返す。
    判定ロジック（マーカー文字列の有無）はこのテキストに対して行う。

    curl_cffi の impersonate="chrome" を使うことで、TLS/JA3の指紋レベルで
    本物のChromeブラウザに近づけている（requestsのUser-Agent偽装だけでは
    TLSハンドシェイクの特徴でBotだと見抜かれることがあるため）。
    """
    soup = fetch_soup(url, timeout=timeout, retries=retries)
    return soup.get_text(separator="\n")


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
