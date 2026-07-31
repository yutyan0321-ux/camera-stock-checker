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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

from checkers import (
    canon_official,
    yamada,
    biccamera,
    kakaku_kaago,
    kaago,
    rakuten,
    rakuten_search,
)

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
    "rakuten_search": rakuten_search.check,
}

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config" / "products.yaml"
STATE_FILE = BASE_DIR / "state.json"

# 履歴として保持する最大件数（これを超えたら古いものから消す）
HISTORY_LIMIT = 20

JST = timezone(timedelta(hours=9))

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
    notifications = []  # (product_name, site_key, result, count) のリスト
    broken_links = []  # (product_name, site_key, url) のリスト

    for product in config["products"]:
        product_id = product["id"]
        product_name = product["name"]

        for site_entry in product["sites"]:
            site_key = site_entry["site"]
            # url を使うサイト(kaago, rakuten等)と keyword を使うサイト
            # (rakuten_search)があるため、どちらか存在する方を識別子にする。
            identifier = site_entry.get("url") or site_entry.get("keyword", "")
            state_key = f"{product_id}:{site_key}:{identifier}"
            error_key = f"{state_key}#error"

            if not identifier:
                print(f"[skip] {product_name} / {site_key}: URL/keyword未設定")
                continue

            checker = CHECKERS.get(site_key)
            if checker is None:
                print(f"[warn] 未知のサイトキーです: {site_key}（スキップ）")
                continue

            try:
                result = checker(site_entry)
            except Exception as e:
                error_str = str(e)
                print(f"[error] {product_name} / {site_key} の取得に失敗: {error_str}")
                # 失敗時は前回状態を維持して次回に持ち越す
                new_state[state_key] = previous_state.get(state_key, False)

                # 404は「ページ自体が無くなった」ことを示す。一時的な通信
                # エラー（タイムアウト等）と区別し、404に変わった最初の
                # タイミングだけ警告する（毎回通知が来るとうるさいため）。
                is_broken = "404" in error_str
                was_broken = previous_state.get(error_key, False)
                new_state[error_key] = is_broken
                if is_broken and not was_broken:
                    broken_links.append((product_name, site_key, identifier))
                continue

            new_state[error_key] = False

            in_stock = result["in_stock"]
            was_in_stock = previous_state.get(state_key, False)
            new_state[state_key] = in_stock

            print(
                f"{product_name} / {site_key} -> 在庫あり: {in_stock} "
                f"(前回: {was_in_stock}) {result.get('detail', '')}"
            )

            # 「在庫なし → 在庫あり」に変わった回数を累計でカウントする。
            # どのショップがよく入荷するかを、しばらく運用した後に
            # state.json を見れば振り返られるようにするため。
            count_key = f"{state_key}#count"
            count = previous_state.get(count_key, 0)

            # 検知した日時(JST)と価格の履歴も直近 HISTORY_LIMIT 件だけ残す。
            # 「いつ・いくらで出やすいか」の傾向をあとから振り返るため。
            history_key = f"{state_key}#history"
            history = previous_state.get(history_key, [])

            if in_stock and not was_in_stock:
                count += 1
                detected_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
                history = history + [
                    {"date": detected_at, "price": result.get("price")}
                ]
                history = history[-HISTORY_LIMIT:]
                notifications.append((product_name, site_key, result, count))

            new_state[count_key] = count
            new_state[history_key] = history

    lines = []

    if notifications:
        lines.append("【在庫検知】")
        for product_name, site_key, result, count in notifications:
            price_part = f" ¥{result['price']:,}" if result.get("price") else ""
            lines.append(
                f"■ {product_name} ({site_key}){price_part} "
                f"(累計入荷検知: {count}回)"
            )
            # rakuten_searchのように複数候補が見つかるサイトでは、
            # 安い順の一覧（各候補のURL込み）が detail に入っているので
            # そちらを表示し、重複する単独のurl行は出さない。
            if site_key == "rakuten_search" and result.get("detail"):
                lines.append(result["detail"])
            else:
                lines.append(result["url"])

    if broken_links:
        if lines:
            lines.append("")
        lines.append("【⚠ リンク切れの可能性】ショップの入れ替えをご検討ください")
        for product_name, site_key, url in broken_links:
            lines.append(f"■ {product_name} ({site_key})")
            lines.append(url)

    if lines:
        send_line_broadcast("\n".join(lines))
        print("通知を送信しました")

    save_state(new_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
