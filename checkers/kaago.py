"""
Kaago（価格.comが運営する通販モール、kaago.com）の各ショップ商品ページ用チェッカー。

Kaagoは1つのURLに全ショップの価格が集約されているわけではなく、
ショップごとに個別の商品ページがある。そのため、同じ商品を複数の
ショップURLとして config/products.yaml に登録し、それぞれ個別に
価格帯チェックを行う。

「価格が指定範囲内」かつ「在庫なしの表示が無い」の両方を満たした
場合のみ「検知（在庫あり）」とみなす。価格だけで判定すると、
売り切れ・入荷待ちの商品でも過去の価格が表示され続けるページで
誤検知するため（実際にこの誤検知が発生したため両方チェックする
形に修正した）。
"""

from . import common

OUT_OF_STOCK_MARKERS = [
    "在庫なし",
    "入荷待ちとなっております",
    "現在入荷待ち",
    "販売を終了しました",
    "品切れ",
]


def check(site_config: dict) -> dict:
    url = site_config["url"]
    price_min = site_config.get("price_min")
    price_max = site_config.get("price_max")

    if price_min is None or price_max is None:
        raise ValueError(
            "kaago サイトには price_min と price_max の指定が必要です"
        )

    text = common.fetch_text(url)
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
