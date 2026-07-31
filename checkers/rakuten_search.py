"""
楽天市場の「検索結果ページ」を丸ごと監視するチェッカー。

個別のショップページを1つずつ登録する方式（rakuten.py）だと、
- 新しく出品を始めたショップを拾えない
- 閉店・出品終了したショップの分だけ監視対象がじわじわ減っていく
という欠点がある。

このチェッカーは検索結果ページ（複数ショップの出品が価格順などで
並ぶ一覧）を直接見ることで、新しく出品されたショップも自動的に
拾えるようにする。ショップの個別URLをメンテナンスする必要がない。

判定基準（検索結果に並ぶ出品ごとに、以下をすべて満たすものが
1件でもあれば検知）:
- 商品タイトルに required_keywords が すべて含まれる
  （無関係なアクセサリー等を誤って拾わないため）
- 「中古」等の表記が無い
- 価格が指定範囲内

なお楽天の検索は既定で「売り切れ商品」を結果に含めない仕様のため、
在庫なしの商品を別途除外する処理は不要。
"""

import re
from urllib.parse import quote_plus

from . import common
from .rakuten import USED_ITEM_MARKERS

# 検索結果ページの各出品は "## [商品名](URL " という見出し形式で
# 現れる（common.fetch_text はページをMarkdown風のテキストに変換する）。
ITEM_HEADING_PATTERN = re.compile(r"## \[([^\]]+)\]\(([^)\s]+)")


def _build_search_url(keyword: str, price_min: int, price_max: int) -> str:
    encoded_keyword = quote_plus(keyword)
    return (
        f"https://search.rakuten.co.jp/search/mall/{encoded_keyword}/"
        f"?min={price_min}&max={price_max}"
    )


def check(site_config: dict) -> dict:
    keyword = site_config["keyword"]
    required_keywords = site_config.get("required_keywords", [])
    price_min = site_config.get("price_min")
    price_max = site_config.get("price_max")

    if price_min is None or price_max is None:
        raise ValueError(
            "rakuten_search サイトには price_min と price_max の指定が必要です"
        )

    url = _build_search_url(keyword, price_min, price_max)
    text = common.fetch_text(url)

    matches = list(ITEM_HEADING_PATTERN.finditer(text))
    found = []  # (title, item_url, price) のリスト

    for i, m in enumerate(matches):
        title = m.group(1)
        item_url = m.group(2)
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[block_start:block_end]

        # 無関係なアクセサリー等を除外（商品名に必須キーワードが無ければスキップ）
        # 「G7 X」「G7X」のような表記ゆれを吸収するため、空白を除いて比較する。
        normalized_title = title.replace(" ", "").replace("　", "")
        if required_keywords and not all(
            k.replace(" ", "") in normalized_title for k in required_keywords
        ):
            continue

        # 中古品を除外
        if common.contains_any(title + block, USED_ITEM_MARKERS):
            continue

        prices = common.extract_prices(title + block)
        matched_prices = [p for p in prices if price_min <= p <= price_max]
        if matched_prices:
            found.append((title, item_url, matched_prices[0]))

    in_stock = len(found) > 0

    if found:
        title, item_url, price = found[0]
        detail = f"{len(found)}件の該当出品を検出。例: {title} ¥{price:,}"
        return {
            "in_stock": True,
            "price": price,
            "detail": detail,
            "url": item_url,
        }
    else:
        detail = f"¥{price_min:,}〜¥{price_max:,}の範囲で該当する新品出品なし"
        return {"in_stock": False, "price": None, "detail": detail, "url": url}
