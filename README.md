# MetaTrend Watcher

保有株のメタトレンド仮説をニュースで毎日検証し、9時・17時にLINE通知するMVPです。
初期設定ではキオクシアホールディングスを監視対象として登録します。

## できること

- Google News RSSから関連ニュースを収集
- 保有銘柄ごとの投資仮説に対して、ニュースをポジティブ/ネガティブ/中立に分類
- メタトレンドスコア、業績期待、上値余地、下落リスク、利確警戒度を算出
- 毎日9時・17時にLINEへレポート通知
- `/dashboard` でブラウザ表示

## セットアップ

```bash
cd metatrend-watcher
python -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` に以下を設定してください。

```bash
OPENAI_API_KEY=sk-...
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=...
```

LINE通知を使わない場合、LINE関連は空欄でも動きます。その場合は通知内容がコンソールに表示されます。

## 起動

```bash
uvicorn app.main:app --reload
```

ブラウザで開く:

- http://127.0.0.1:8000/dashboard
- http://127.0.0.1:8000/docs

手動実行:

```bash
curl -X POST http://127.0.0.1:8000/run-now
```

## Renderに置く場合

Start Command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Environment Variablesに `.env` と同じ値を登録してください。

## 注意

このアプリは投資助言ではありません。ニュースと開示情報を整理し、投資仮説の維持/弱化を見える化するための補助ツールです。
