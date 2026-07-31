"""
複数商品 x 複数サイトの在庫検知メインスクリプト。

- config/products.yaml を読み込み、商品ごと・サイトごとにチェックを行う
- サイトごとの判定ロジックは checkers/ 以下のモジュールに分離されている
- 「在庫なし → 在庫あり」に変わったときだけ LINE に通知する
- 状態は state.json に保存し、次回実行時に前回状態と比較する

商品を増やす・サイトを増やす場合は config/products.yaml とこのファイル冒頭の
CHECKERS 辞書だけを見ればよい（判定ロジック自体は checkers/ 以下に分離）。
"""

import json
import os
import sys
from pathlib import Path

import requests
import yaml

from checkers import canon_official, yamada, biccamera, kakaku_kaago, kaago, rakuten

# サイトキー(config内のsite:の値) -> チェッカー関数 の対応表。
# 新しいサイトを追加するときは、checkers/ に新しいモジュールを作って
# ここに1行足すだけでよい。
CHECKERS = {
    "canon_official": canon_official.check,
    "yamada": yamada.check,
    "biccamera": biccamera.check,
    "kakaku_kaago": kakaku_kaago.check,
    "kaago": kaago.check,
    "rakuten": rakuten.check,
}

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config" / "products.yaml"
STATE_FILE = BASE_DIR / "state.json"

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_previous_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_line_broadcast(message: str) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("LINE_CHANNEL_ACCESS_TOKEN が未設定のため通知をスキップします")
        return

    resp = requests.post(
        "https://api.line.me/v2/bot/message/broadcast",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        },
        json={"messages": [{"type": "text", "text": message}]},
        timeout=20,
    )
    if resp.status_code != 200:
        print(f"LINE通知の送信に失敗: {resp.status_code} {resp.text}")
        resp.raise_for_status()


def main() -> int:
    config = load_config()
    previous_state = load_previous_state()
    new_state = {}
    notifications = []  # (product_name, site_key, result) のリスト

    for product in config["products"]:
        product_id = product["id"]
        product_name = product["name"]

        for site_entry in product["sites"]:
            site_key = site_entry["site"]
            url = site_entry.get("url", "")
            state_key = f"{product_id}:{site_key}:{url}"

            if not url:
                print(f"[skip] {product_name} / {site_key}: URL未設定")
                continue

            checker = CHECKERS.get(site_key)
            if checker is None:
                print(f"[warn] 未知のサイトキーです: {site_key}（スキップ）")
                continue

            try:
                result = checker(site_entry)
            except Exception as e:
                print(f"[error] {product_name} / {site_key} の取得に失敗: {e}")
                # 失敗時は前回状態を維持して次回に持ち越す
                new_state[state_key] = previous_state.get(state_key, False)
                continue

            in_stock = result["in_stock"]
            was_in_stock = previous_state.get(state_key, False)
            new_state[state_key] = in_stock

            print(
                f"{product_name} / {site_key} -> 在庫あり: {in_stock} "
                f"(前回: {was_in_stock}) {result.get('detail', '')}"
            )

            if in_stock and not was_in_stock:
                notifications.append((product_name, site_key, result))

    if notifications:
        lines = ["【在庫検知】"]
        for product_name, site_key, result in notifications:
            price_part = f" ¥{result['price']:,}" if result.get("price") else ""
            lines.append(f"■ {product_name} ({site_key}){price_part}")
            lines.append(result["url"])
        send_line_broadcast("\n".join(lines))
        print("通知を送信しました")

    save_state(new_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
