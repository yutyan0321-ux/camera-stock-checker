# 在庫検知ボット（複数商品・複数サイト対応版）

Canon PowerShot G7 X Mark III / SX740 HS を対象に、以下4サイトの
在庫（またはKaagoでの価格帯出品）を5分おきに自動チェックし、
検知したらLINEに通知します。GitHub Actions（無料枠）で動きます。

- キヤノンオンラインショップ（公式）
- ヤマダウェブコム
- ビックカメラ.com
- 価格.com（Kaagoなど各ショップの出品価格を含む）※価格帯フィルタつき

## ディレクトリ構成

```
config/products.yaml       … 監視したい商品とサイトの一覧（★ここを編集して増減する）
checkers/common.py         … 共通処理（ページ取得・価格抽出など）
checkers/canon_official.py … キヤノンオンラインショップ用の判定ロジック
checkers/yamada.py         … ヤマダウェブコム用の判定ロジック
checkers/biccamera.py      … ビックカメラ用の判定ロジック
checkers/kakaku_kaago.py   … 価格.com(Kaago)用の判定ロジック（価格帯フィルタ）
check_stock.py             … 全体をまとめて実行するメインスクリプト
state.json                 … 前回の在庫状態（自動生成・自動更新）
.github/workflows/         … 5分おきの自動実行設定
```

## セットアップ手順（前回と同じ）

### 1. LINE公式アカウントの準備
1. https://www.linebiz.com/jp/entry/ から公式アカウントを作成
2. LINE Developers コンソール（https://developers.line.biz/console/）
   で Messaging API を有効化し、「チャネルアクセストークン（長期）」を発行
3. QRコードから自分のLINEで公式アカウントを友だち追加

### 2. GitHubリポジトリの準備
このフォルダの中身一式をそのままリポジトリにpushしてください。

### 3. Secretsの登録
`Settings → Secrets and variables → Actions` で
`LINE_CHANNEL_ACCESS_TOKEN` を登録。

### 4. 動作確認
`Actions` タブ → workflow → `Run workflow` で手動実行し、ログを確認。

## 商品・サイトの追加や変更をしたいとき

### 商品を追加/変更したい
`config/products.yaml` を編集するだけです。コードの変更は不要です。
例えば新しいカメラを追加したい場合：

```yaml
  - id: g5x_mark2
    name: "PowerShot G5 X Mark II"
    sites:
      - site: canon_official
        url: "https://store.canon.jp/online/g/xxxxx/"
      - site: kakaku_kaago
        url: "https://kakaku.com/item/xxxxx/"
        price_min: 80000
        price_max: 100000
```

### 監視するサイトを追加したい
1. `checkers/新しいサイト名.py` を作り、`check(site_config)` 関数を実装する
   （他のチェッカーファイルをコピーして書き換えるのが早いです）
2. `check_stock.py` の `CHECKERS` 辞書に1行追加する
   ```python
   CHECKERS = {
       ...
       "yodobashi": yodobashi.check,
   }
   ```
3. `config/products.yaml` の該当商品に `site: yodobashi` の項目を追加する

## 現時点で未確定のURL
- ヤマダウェブコムの SX740 HS 商品ページ（`config/products.yaml` 内にTODOコメントあり）
- 各サイトの「色違い」ページ（ブラック/シルバー両方を監視したい場合は
  同じ `site:` で項目をもう1つ追加してください）

## 判定ロジックについて（重要）
在庫判定は「ページ内に『販売終了しました』のような文言が含まれていないこと」
をもって在庫ありとみなす、シンプルな仕組みです。各サイトがページの文言や
デザインを変更すると誤検知する可能性があります。通知が来ない/来すぎる場合は
該当する `checkers/*.py` 内の `OUT_OF_STOCK_MARKERS` を実際のページを見ながら
調整してください。

価格.com(Kaago)については、ページ内の価格表記のうち `price_min`〜`price_max`
の範囲に入るものが1件でもあれば検知したものとして通知します。
