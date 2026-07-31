"""
楽天市場の各ショップ商品ページ用チェッカー。

楽天市場もKaagoと同様、ショップごとに個別の商品ページがあるため、
複数のショップURLを config/products.yaml に登録し、それぞれ個別に
チェックする。

判定は3段階：
1. 商品ページの中に「中古」を示す文言があれば、価格や在庫に関わらず
   除外する（タイトルの「新品」表記だけを信用せず、本文全体を見て
   中古品を弾く）
2. 「価格が指定範囲内」かどうか
3. 「売り切れ・販売終了などの表示が無い」かどうか

1で除外されず、2と3の両方を満たした場合のみ「検知（在庫あり）」
とみなす。
"""

from . import common

USED_ITEM_MARKERS = [
    "中古",
    "訳あり",
    "リユース",
    "ジャンク",
    "USED",
    "キズあり",
    "難あり",
    "動作確認済み",
]

OUT_OF_STOCK_MARKERS = [
    "売り切れました",
    "売り切れ",
    "販売を終了しました",
    "在庫切れ",
    "在庫がありません",
    "品切れ",
    "完売",
]


def check(site_config: dict) -> dict:
    url = site_config["url"]
    price_min = site_config.get("price_min")
    price_max = site_config.get("price_max")

    if price_min is None or price_max is None:
        raise ValueError(
            "rakuten サイトには price_min と price_max の指定が必要です"
        )

    text = common.fetch_text(url)

    # 中古品を示す文言があれば、価格や在庫状況に関わらず除外する
    used_marker = common.contains_any(text, USED_ITEM_MARKERS)
    if used_marker:
        detail = f"「{used_marker}」の表示があり中古品の可能性があるため除外"
        return {"in_stock": False, "price": None, "detail": detail, "url": url}

    prices = common.extract_prices(text)
    matched = sorted({p for p in prices if price_min <= p <= price_max})
    price_in_range = len(matched) > 0

    out_of_stock_marker = common.contains_any(text, OUT_OF_STOCK_MARKERS)
    is_out_of_stock = out_of_stock_marker is not None

    in_stock = price_in_range and not is_out_of_stock

    if is_out_of_stock:
        detail = f"価格は範囲内だが「{out_of_stock_marker}」の表示あり（在庫なし扱い）"
    elif matched:
        detail = f"¥{price_min:,}〜¥{price_max:,}の範囲で価格を検出: " + ", ".join(
            f"¥{p:,}" for p in matched[:5]
        )
    else:
        detail = f"¥{price_min:,}〜¥{price_max:,}の範囲の価格は見つからず"

    price = matched[0] if (matched and in_stock) else None
    return {"in_stock": in_stock, "price": price, "detail": detail, "url": url}
