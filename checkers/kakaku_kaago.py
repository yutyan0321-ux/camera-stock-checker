"""
価格.com の商品ページ（複数ショップの価格が一覧表示されるページ）用チェッカー。
Kaago（価格.comの公式通販モール）を含む各ショップの出品価格がここに載る。

設定ファイルで指定した price_min 〜 price_max の範囲内の価格が
1件でも見つかったら「検知」とみなす。
"""

from . import common


def check(site_config: dict) -> dict:
    url = site_config["url"]
    price_min = site_config.get("price_min")
    price_max = site_config.get("price_max")

    if price_min is None or price_max is None:
        raise ValueError(
            "kakaku_kaago サイトには price_min と price_max の指定が必要です"
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

    # 価格帯内の最安値を price として返す（通知メッセージ用）
    price = matched[0] if matched else None
    return {"in_stock": in_stock, "price": price, "detail": detail, "url": url}
