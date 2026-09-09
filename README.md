# SuisenIllusionAI 

キーワードをJSONで受け取り、Google Gemini API で AI画像を生成し、
Firebase Cloud Storage / Firestore へ保存する REST API です。

Redis / Celery / Worker / Frontend は使用せず、FastAPI から
Gemini API を同期的に呼び出すシンプルな構成です。

## 構成

```text
Client(JSON) → Nginx → FastAPI → Gemini API
                              ├→ Firebase Storage
                              └→ Firestore
```

## ディレクトリ構成

```text
SuisenIllusionAI/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── app/
│   ├── main.py                  # FastAPIエントリポイント
│   ├── api/
│   │   ├── deps.py              # 依存性注入(サービス提供)
│   │   └── v1/
│   │       ├── images.py        # 画像生成/取得/一覧/削除API
│   │       └── health.py        # Health Check API
│   ├── schemas/
│   │   └── image.py             # Pydanticスキーマ
│   ├── services/
│   │   ├── image_service.py     # 全体オーケストレーション
│   │   ├── gemini_service.py    # Gemini API連携
│   │   ├── firebase_service.py  # Storage/Firestore連携
│   │   └── prompt_service.py    # keyword検証・プロンプト生成
│   ├── core/
│   │   ├── config.py            # 環境変数設定
│   │   ├── exceptions.py        # エラー定義
│   │   ├── logging_config.py    # ログ設定
│   │   └── rate_limit.py        # Rate Limit設定
│   └── utils/
│       └── file_utils.py        # 一時ファイル管理
├── nginx/
│   └── nginx.conf
├── data/images/                 # 一時画像保存先
├── firebase/                    # service-account.json 配置先(Git管理外)
└── docs/
    └── detailed-design.md
```

## セットアップ

### 1. 環境変数の設定

```bash
cp .env.example .env
# .env を編集し、GOOGLE_API_KEY / FIREBASE_PROJECT_ID / FIREBASE_STORAGE_BUCKET 等を設定
```

`GEMINI_IMAGE_MODEL` には、Google公式ドキュメントで確認した
画像生成対応モデルのIDを設定してください（本リポジトリのデフォルト値は仮設定です）。

### 2. Firebase サービスアカウントの配置

Firebase コンソールでサービスアカウントキーを発行し、以下に配置します。

```text
firebase/service-account.json
```

このファイルは `.gitignore` により Git 管理対象外です。

### 3. ローカル起動(Dockerなし)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. Docker Compose での起動

```bash
docker compose up --build
```

- Nginx: `http://localhost/`
- FastAPI(直接): `http://localhost:8000/`（コンテナ外からは通常Nginx経由でアクセス）

HTTPS化する場合は Let's Encrypt 等で証明書を取得し、
`nginx/nginx.conf` のコメントアウトされた 443 用設定を有効化してください。

## API仕様

| メソッド | パス | 説明 |
|---|---|---|
| POST | `/api/v1/images` | キーワードからAI画像を**5枚**生成 |
| GET | `/api/v1/images/{image_id}` | 画像情報(5枚分のURL)を取得 |
| GET | `/api/v1/images?page=&limit=&keyword=` | 画像一覧を取得 |
| DELETE | `/api/v1/images/{image_id}` | 画像(5枚分)を削除(物理削除) |
| GET | `/api/health` | ヘルスチェック |

### 画像生成の例

```bash
curl -X POST http://localhost/api/v1/images \
  -H "Content-Type: application/json" \
  -d '{"keyword": "水仙"}'
```

レスポンス例(1〜2回目、新規生成の場合)：

```json
{
    "image_id": "01JXXXXXXXXXXXX",
    "status": "completed",
    "source": "generated",
    "keyword": "水仙",
    "image_urls": [
        "https://.../01JXXXXXXXXXXXX-0.png",
        "https://.../01JXXXXXXXXXXXX-1.png",
        "https://.../01JXXXXXXXXXXXX-2.png",
        "https://.../01JXXXXXXXXXXXX-3.png",
        "https://.../01JXXXXXXXXXXXX-4.png"
    ],
    "aspect_ratio": "16:9",
    "image_size": "1024",
    "daily_requests_used": 1,
    "daily_requests_limit": 2,
    "is_unlimited_client": false
}
```

同一IPからの3回目以降のリクエストは、新規生成せず既存画像をランダムに返す
(`source: "existing"`, `image_id: null`)。ただしlocalhost(127.0.0.1/::1)は無制限。

## 主な設計上の決定事項

- 画像生成は**同期処理**（Redis / Celery / Worker / Job Queue は不使用）
- 1回の生成リクエストにつき**5枚**の画像を生成する(`IMAGES_PER_REQUEST`で変更可)。
  `gemini-2.5-flash-image` は複数枚同時生成(candidateCount等)に非対応のため、
  Gemini APIを5回ループ呼び出しして実現している(課金は5枚分発生する点に注意)
- クライアントIPアドレス単位で1日あたり**2回**(=新規画像10枚)まで生成可能。
  超過分は新規生成せず既存の生成済み画像URLをランダムに返す。
  localhost(127.0.0.1/::1)は無制限
- `image_size` は初期版では `1024` のみ許可（設計書40章）
- Rate Limit は1 IPあたり 1分間 5リクエスト（設計書32章、`slowapi` によるインメモリ実装。
  上記の1日あたり生成回数制限とは別レイヤー）
- 生成完了後、VPS上の一時画像ファイルは即座に削除（異常終了分は起動時と定期処理でクリーンアップ）
- APIキー・サービスアカウントはVPS側のみ保持し、レスポンス・ログには一切出力しない
- Gemini API通信エラー時の自動リトライは行わない（二重課金防止、設計書36章）

## 運用ドキュメント

本番相当環境での動作確認結果、Gemini APIのモデルライフサイクル管理(重要な移行期限あり)、
課金・レート制限の運用、障害対応手順(Runbook)などは `docs/operations-guide.md` にまとめています。
運用担当者は必ず目を通してください。特に4章「モデルライフサイクル管理」は対応期限があります。
