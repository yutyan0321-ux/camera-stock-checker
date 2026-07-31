"""
Kaago（価格.comが運営する通販モール、kaago.com）の各ショップ商品ページ用チェッカー。

Kaagoは1つのURLに全ショップの価格が集約されているわけではなく、
ショップごとに個別の商品ページがある。そのため、同じ商品を複数の
ショップURLとして config/products.yaml に登録し、それぞれ個別に
価格帯チェックを行う。

設定ファイルで指定した price_min 〜 price_max の範囲内であれば
「検知（在庫あり）」とみなす。
"""

from . import common


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
    in_stock = len(matched) > 0

    if matched:
        detail = f"¥{price_min:,}〜¥{price_max:,}の範囲で価格を検出: " + ", ".join(
            f"¥{p:,}" for p in matched[:5]
        )
    else:
        detail = f"¥{price_min:,}〜¥{price_max:,}の範囲の価格は見つからず"

    price = matched[0] if matched else None
    return {"in_stock": in_stock, "price": price, "detail": detail, "url": url}
