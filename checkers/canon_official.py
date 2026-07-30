"""
キヤノンオンラインショップ（store.canon.jp）の商品ページ用チェッカー。

「受注停止」「納期未定」等の文言が無ければ在庫あり（注文可能）と判定する。
"""

from . import common

OUT_OF_STOCK_MARKERS = [
    "受注の受付を停止しております",
    "納期未定",
    "受注停止",
]


def check(site_config: dict) -> dict:
    url = site_config["url"]
    text = common.fetch_text(url)

    marker = common.contains_any(text, OUT_OF_STOCK_MARKERS)
    in_stock = marker is None

    detail = f"「{marker}」の表示あり" if marker else "在庫なしの表示なし"
    return {"in_stock": in_stock, "price": None, "detail": detail, "url": url}
