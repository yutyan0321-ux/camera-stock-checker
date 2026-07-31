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

【実装メモ】
検索結果ページには商品ごとのリンク(<a href="https://item.rakuten.co.jp/...">)
が並んでいる。これを common.fetch_soup() でHTML構造ごと取得し、
リンクのhrefで商品を区別する（common.fetch_text()のような「見た目の
テキストだけ」の抽出だと、リンクの区切りが失われて商品ごとに
価格を対応づけられなくなるため、これは使わない）。
"""

import re
from urllib.parse import quote_plus

from . import common
from .rakuten import USED_ITEM_MARKERS

ITEM_URL_PATTERN = re.compile(r"^https://item\.rakuten\.co\.jp/")

# 価格を含んでいそうな塊かどうかの簡易判定（¥や円が入っているか）
_PRICE_HINT_PATTERN = re.compile(r"[¥￥]|\d[\d,]{3,}\s*円")

# カメラ本体ではなく付属品・アクセサリーであることを示す語。
# 「SX740対応」のような形でカメラ本体の型番を含んでしまう
# 保護フィルム・ケース・バッテリー等を誤検知しないよう除外する。
ACCESSORY_MARKERS = [
    "フィルム",
    "ガラスフィルム",
    "保護フィルム",
    "ケース",
    "カバー",
    "ストラップ",
    "互換品",
    "互換バッテリー",
    "バッテリー",
    "液晶保護",
    "レンズフィルター",
    "レンズキャップ",
    "スクリーンプロテクター",
]


def _build_search_url(keyword: str, price_min: int, price_max: int) -> str:
    encoded_keyword = quote_plus(keyword)
    return (
        f"https://search.rakuten.co.jp/search/mall/{encoded_keyword}/"
        f"?min={price_min}&max={price_max}"
    )


def _find_price_block(anchor, max_levels: int = 3) -> str:
    """
    商品リンクの周辺テキストから、価格が書かれていそうな最小のブロックを
    探す。親要素を1階層ずつさかのぼり、価格らしき文字列(¥や円)が
    含まれた時点のテキストを返す。
    見つからなければ最後にたどり着いた階層のテキストを返す。
    """
    node = anchor
    block_text = anchor.get_text(separator=" ")
    for _ in range(max_levels):
        if node.parent is None:
            break
        node = node.parent
        block_text = node.get_text(separator=" ")
        if _PRICE_HINT_PATTERN.search(block_text):
            break
    return block_text


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
    soup = common.fetch_soup(url)

    seen_hrefs = set()
    found = []  # (title, item_url, price) のリスト

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not ITEM_URL_PATTERN.match(href):
            continue

        title = anchor.get_text(strip=True)
        if not title:
            # 画像だけのリンク（テキストが無い）は商品タイトルの
            # リンクではないのでスキップする。
            continue

        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # 無関係なアクセサリー等を除外
        # 「G7 X」「G7X」のような表記ゆれを吸収するため、空白を除いて比較する。
        normalized_title = title.replace(" ", "").replace("　", "")
        if required_keywords and not all(
            k.replace(" ", "") in normalized_title for k in required_keywords
        ):
            continue

        # 中古品を除外
        if common.contains_any(title, USED_ITEM_MARKERS):
            continue

        # アクセサリー・付属品を除外（カメラ本体ではないため）
        if common.contains_any(title, ACCESSORY_MARKERS):
            continue

        block_text = _find_price_block(anchor)
        if common.contains_any(block_text, USED_ITEM_MARKERS):
            continue

        prices = common.extract_prices(title + " " + block_text)
        matched_prices = [p for p in prices if price_min <= p <= price_max]
        if matched_prices:
            found.append((title, href, matched_prices[0]))

    in_stock = len(found) > 0

    if found:
        # 転売目的での利用を想定し、最も安い出品を優先して知らせる。
        found.sort(key=lambda item: item[2])
        cheapest_title, cheapest_url, cheapest_price = found[0]

        top_candidates = found[:5]
        # 候補ごとに「タイトル・価格・URL」を1行ずつ並べる
        # （URLが無いと候補を見ても開けないため、必ず含める）。
        candidates_lines = [
            f"{i}. {t} ¥{p:,}\n{u}"
            for i, (t, u, p) in enumerate(top_candidates, start=1)
        ]
        candidates_text = "\n".join(candidates_lines)
        detail = (
            f"{len(found)}件の該当出品を検出（安い順）: {candidates_text}"
        )
        return {
            "in_stock": True,
            "price": cheapest_price,
            "detail": detail,
            "url": cheapest_url,
        }
    else:
        detail = f"¥{price_min:,}〜¥{price_max:,}の範囲で該当する新品出品なし"
        return {"in_stock": False, "price": None, "detail": detail, "url": url}
