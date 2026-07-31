"""
ビックカメラ.com（biccamera.com）の商品ページ用チェッカー。

「販売を終了しました」等の文言が無ければ在庫あり（購入可能）と判定する。
※ ページ構成が変わると誤検知することがあるので、通知が来ない/来すぎる
   場合はこのファイルの OUT_OF_STOCK_MARKERS を見直してください。
"""

from . import common

OUT_OF_STOCK_MARKERS = [
    "予定数の販売を終了しました",
    "在庫がなくなりました",
    "ご購入できません",
    "販売を終了しました",
    "お取り扱いを終了しました",
    "只今在庫がありません",
    "入荷未定",
]


def check(site_config: dict) -> dict:
    url = site_config["url"]
    text = common.fetch_text(url)

    marker = common.contains_any(text, OUT_OF_STOCK_MARKERS)
    in_stock = marker is None

    detail = f"「{marker}」の表示あり" if marker else "在庫なしの表示なし"
    return {"in_stock": in_stock, "price": None, "detail": detail, "url": url}
