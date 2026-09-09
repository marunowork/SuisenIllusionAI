# AI画像生成Web API 簡易版 詳細設計書

**文書番号:** SUISEN-GALLERY-API-DD-002  
**版数:** 0.1  
**作成日:** 2026-08-24  
**対象:** さくらVPS上のAI画像生成Web API  
**ステータス:** 初期設計

---

# 1. システム概要

## 1.1 目的

キーワードをJSON形式で受け取り、Google AI Studio / Gemini APIを利用してAI画像を生成するWeb APIを提供する。

生成された画像はFirebase Cloud Storageへ保存し、画像情報をFirestoreへ登録する。

フロントエンド画面は実装せず、画像生成・取得・一覧・削除などの操作はすべてREST APIのJSONリクエスト/レスポンスで行う。

## 1.2 基本ユースケース

例えば以下のJSONをAPIへ送信する。

```json
{
    "keyword": "水仙"
}
```

処理フロー：

```text
JSON Request
    ↓
FastAPI
    ↓
入力チェック
    ↓
プロンプト生成
    ↓
Gemini API
    ↓
画像生成
    ↓
VPS一時保存
    ↓
Firebase Storage
    ↓
Firestore
    ↓
JSON Response
```

---

# 2. 設計方針

今回の簡易版では、元設計から以下を削除する。

- 動画生成
- Veo
- Celery
- Redis
- Worker
- Frontend
- jQuery
- ポーリング
- 動画用一時ファイル管理

代わりに、FastAPIから画像生成APIを直接呼び出す。

```text
Client
  │
  │ JSON
  ▼
Nginx
  │
  ▼
FastAPI
  │
  ├── Gemini API
  │
  ├── Firebase Storage
  │
  └── Firestore
```

---

# 3. 採用技術

| 分類 | 技術 | 採用理由 |
|---|---|---|
| VPS | さくらのVPS | APIサーバー |
| OS | Ubuntu | サーバーOS |
| コンテナ | Docker | 実行環境の統一 |
| コンテナ管理 | Docker Compose | API/Nginx管理 |
| Webサーバー | Nginx | HTTPS・リバースプロキシ |
| API | FastAPI | REST API |
| Python | 3.12 | アプリケーション実行環境 |
| AI | Google Gemini API | 画像生成 |
| Storage | Firebase Cloud Storage | 生成画像保存 |
| DB | Cloud Firestore | 画像メタデータ保存 |
| HTTPS | Let's Encrypt | TLS証明書 |

Redis、Celery、PostgreSQLは使用しない。

---

# 4. システム構成

## 4.1 論理構成

```text
                         Internet
                            │
                         HTTPS
                            │
                            ▼
                    ┌───────────────┐
                    │     Client    │
                    │ curl / Python │
                    │ Unity / etc.  │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     Nginx     │
                    │ Reverse Proxy │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    FastAPI    │
                    │  Python 3.12 │
                    └───────┬───────┘
                            │
               ┌────────────┼─────────────┐
               │            │             │
               ▼            ▼             ▼
        ┌────────────┐ ┌────────────┐ ┌────────────┐
        │ Gemini API │ │  Firebase  │ │ Firestore  │
        │ Image Gen  │ │  Storage   │ │ Metadata   │
        └────────────┘ └────────────┘ └────────────┘
```

---

# 5. サーバー構成

## 5.1 VPS

```text
さくらVPS
├── Ubuntu
├── Docker
├── Docker Compose
├── Nginx
└── Firewall
```

AI画像生成はGoogle側で実行するため、VPSにGPUは不要。

VPSの役割：

- HTTPS受付
- JSON API受付
- 入力チェック
- プロンプト生成
- Gemini API通信
- 画像一時保存
- Firebase Storage通信
- Firestore通信
- JSONレスポンス返却

---

# 6. Docker構成

## 6.1 コンテナ

Redis/Celery/Workerを廃止し、以下の2コンテナのみとする。

```text
docker-compose.yml

services:
    nginx
    api
```

## 6.2 APIコンテナ

```text
api
├── FastAPI
├── Python 3.12
├── Gemini API Client
├── Firebase Admin SDK
└── Pydantic
```

---

# 7. ディレクトリ構成

```text
SUISEN-GALLERY-api/
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── images.py
│   │       └── health.py
│   │
│   ├── schemas/
│   │   └── image.py
│   │
│   ├── services/
│   │   ├── image_service.py
│   │   ├── gemini_service.py
│   │   ├── firebase_service.py
│   │   └── prompt_service.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   └── utils/
│       └── file_utils.py
│
├── data/
│   └── images/
│
├── firebase/
│   └── service-account.json
│
└── docs/
    └── detailed-design.md
```

`service-account.json`はGitへ登録しない。

---

# 8. 外部サービス構成

## 8.1 Google AI Studio / Gemini API

Google AI StudioでAPIキーを取得する。

FastAPIからGemini APIを直接呼び出す。

今回の設計ではVeoを使用しない。

画像生成に対応したGemini画像生成モデルを使用する。

モデルIDは環境変数から変更できる構成とする。

```text
GEMINI_IMAGE_MODEL=...
```

具体的なモデルIDは実装時点でGoogle公式仕様を確認して決定する。

---

# 9. プロンプト設計

## 9.1 入力

```json
{
    "keyword": "水仙"
}
```

## 9.2 プロンプト生成

初期版ではLLMによるプロンプト拡張を行わず、FastAPI内部のテンプレートを使用する。

例：

```text
Create a high-quality photorealistic image of {keyword}.
Natural lighting.
Detailed flowers.
Soft background.
High resolution.
Photorealistic.
```

「水仙」の場合：

```text
Create a high-quality photorealistic image of daffodils
blooming in a spring garden.
Natural lighting.
Detailed flowers.
Soft background.
High resolution.
Photorealistic.
```

## 9.3 PromptService

```text
PromptService
    ├── keyword validation
    ├── keyword normalization
    └── prompt generation
```

将来的にGeminiによるプロンプト拡張を追加可能とする。

---

# 10. 画像生成処理

## 10.1 基本フロー

```text
POST /api/v1/images
        │
        ▼
入力チェック
        │
        ▼
Prompt生成
        │
        ▼
Gemini API
        │
        ▼
画像生成
        │
        ▼
VPS一時保存
        │
        ▼
Firebase Storage
        │
        ▼
Firestore
        │
        ▼
JSON Response
```

Redis/Celeryによるジョブキューは使用しない。

---

# 11. 同期処理方式

今回の簡易版では、APIリクエスト中に画像生成完了まで待機する。

```text
Client
   │
   │ POST
   ▼
FastAPI
   │
   ▼
Gemini API
   │
   ▼
画像生成
   │
   ▼
Firebase
   │
   ▼
Firestore
   │
   ▼
HTTP 200
```

この方式により、

- Redis不要
- Celery不要
- Worker不要
- Job Queue不要
- ポーリング不要

となる。

画像生成API自体の処理時間が長い場合は、Nginx/FastAPI側のタイムアウトを十分に設定する。

---

# 12. API仕様

## 12.1 画像生成

```http
POST /api/v1/images
Content-Type: application/json
```

### Request

最小構成：

```json
{
    "keyword": "水仙"
}
```

オプションを含める場合：

```json
{
    "keyword": "水仙",
    "aspect_ratio": "16:9",
    "image_size": "1024"
}
```

## 12.2 Response

成功：

```text
HTTP 200 OK
```

```json
{
    "image_id": "01JXXXXXXXXXXXX",
    "status": "completed",
    "keyword": "水仙",
    "image_url": "https://...",
    "aspect_ratio": "16:9",
    "image_size": "1024"
}
```

---

# 13. 画像取得API

## 13.1 ID指定

```http
GET /api/v1/images/{image_id}
```

### Response

```json
{
    "image_id": "01JXXXXXXXXXXXX",
    "status": "completed",
    "keyword": "水仙",
    "prompt": "Create a high-quality...",
    "image_url": "https://...",
    "aspect_ratio": "16:9",
    "image_size": "1024",
    "created_at": "2026-08-24T10:00:00Z"
}
```

---

# 14. 画像一覧API

```http
GET /api/v1/images
```

Query Parameter：

```text
page
limit
keyword
```

例：

```http
GET /api/v1/images?page=1&limit=20
```

Response：

```json
{
    "items": [
        {
            "image_id": "01JXXXX",
            "keyword": "水仙",
            "status": "completed",
            "image_url": "https://...",
            "created_at": "2026-08-24T10:00:00Z"
        }
    ],
    "page": 1,
    "limit": 20,
    "total": 1
}
```

---

# 15. 画像削除API

```http
DELETE /api/v1/images/{image_id}
```

処理：

```text
API
 │
 ├── Firestore削除
 │
 └── Firebase Storage削除
```

初期版では物理削除とする。

---

# 16. Health Check

```http
GET /api/health
```

Response：

```json
{
    "status": "ok"
}
```

Docker Healthcheckから利用する。

---

# 17. Firestore設計

## 17.1 Collection

```text
images
```

## 17.2 Document ID

```text
image_id
```

## 17.3 Document

```json
{
    "image_id": "01JXXXX",
    "keyword": "水仙",
    "prompt": "Create a high-quality photorealistic image...",
    "model": "使用モデルID",
    "status": "completed",
    "image_size": "1024",
    "aspect_ratio": "16:9",
    "storage_path": "images/2026/08/24/01JXXXX.png",
    "image_url": "https://...",
    "created_at": "...",
    "completed_at": "...",
    "error_code": null,
    "error_message": null
}
```

---

# 18. 画像ステータス

同期処理を基本とするため、状態は簡略化する。

```text
processing
completed
failed
```

状態遷移：

```text
processing
    │
    ├── completed
    │
    └── failed
```

Firestoreへ登録する場合は画像生成開始時に`processing`を登録し、完了後に`completed`へ更新する。

---

# 19. Firebase Storage設計

保存パス：

```text
images/
└── YYYY/
    └── MM/
        └── DD/
            └── {image_id}.png
```

例：

```text
images/2026/08/24/01JXXXX.png
```

画像形式は生成APIの出力仕様に応じてPNG/JPEG等を使用する。

---

# 20. Firebaseアクセス方式

VPS上のFastAPIからFirebase Admin SDKを使用する。

```text
FastAPI
    │
    ▼
Firebase Admin SDK
    │
    ├── Firestore
    │
    └── Storage
```

クライアントからFirebase Storageへ直接アップロードする方式にはしない。

---

# 21. 画像URL設計

初期版ではFirebase Storage上の画像URLをAPIレスポンスとして返す。

本番運用で画像を無制限に公開する必要がない場合は、

```text
API
 ↓
アクセス確認
 ↓
短時間有効URL
 ↓
Client
```

というSigned URL方式を推奨する。

---

# 22. APIリクエスト例

## 22.1 curl

```bash
curl -X POST \
  https://example.com/api/v1/images \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "水仙"
  }'
```

Response：

```json
{
    "image_id": "01JXXXX",
    "status": "completed",
    "keyword": "水仙",
    "image_url": "https://..."
}
```

---

# 23. Pythonからの利用例

```python
import requests

url = "https://example.com/api/v1/images"

payload = {
    "keyword": "水仙"
}

response = requests.post(
    url,
    json=payload,
    timeout=300
)

response.raise_for_status()

data = response.json()

print(data["image_id"])
print(data["image_url"])
```

---

# 24. 画像取得

```bash
curl \
  https://example.com/api/v1/images/01JXXXX
```

Response：

```json
{
    "image_id": "01JXXXX",
    "status": "completed",
    "keyword": "水仙",
    "image_url": "https://..."
}
```

---

# 25. 画像一覧取得

```bash
curl \
  "https://example.com/api/v1/images?page=1&limit=20"
```

---

# 26. 画像削除

```bash
curl -X DELETE \
  https://example.com/api/v1/images/01JXXXX
```

Response：

```json
{
    "image_id": "01JXXXX",
    "status": "deleted"
}
```

---

# 27. 環境変数

`.env`：

```text
APP_ENV=production

GOOGLE_API_KEY=xxxxxxxx

GEMINI_IMAGE_MODEL=xxxxxxxx

FIREBASE_PROJECT_ID=xxxxxxxx

FIREBASE_STORAGE_BUCKET=xxxxxxxx

IMAGE_TEMP_DIR=/data/images

MAX_IMAGE_SIZE_MB=20

API_TIMEOUT_SECONDS=300
```

Redis関連の環境変数は不要。

```text
REDIS_URL
```

は削除する。

APIキーなどの秘密情報をGitへ登録しない。

---

# 28. Firebase認証情報

Firebase Admin SDKのサービスアカウント情報：

```text
firebase/service-account.json
```

DockerではRead Only Volume等で参照させる。

Gitには登録しない。

`.gitignore`：

```text
.env
firebase/service-account.json
data/images/*
__pycache__/
*.pyc
```

---

# 29. セキュリティ設計

## 29.1 Google APIキー

Google APIキーはクライアントへ公開しない。

```text
Client
   X
   ↓
Google API

Client
   ↓
FastAPI
   ↓
Google API
```

APIキーはVPS側だけに保持する。

---

# 30. HTTPS

外部通信はHTTPSのみとする。

```text
HTTP :80
    ↓
HTTPS :443
```

NginxでHTTPからHTTPSへリダイレクトする。

---

# 31. 入力バリデーション

`keyword`には制限を設ける。

初期値：

```text
最小文字数: 1
最大文字数: 100
```

禁止：

```text
空文字
NULL
極端に長い文字列
制御文字
```

PydanticによってリクエストJSONを検証する。

---

# 32. Rate Limit

画像生成はGoogle APIの利用料金が発生するため、過剰なリクエストを防止する。

初期値：

```text
1 IP
1分間 5リクエスト
```

本番ではユーザー単位の制限へ変更可能とする。

Redisを使用しないため、初期版ではNginxのRate Limitまたは単一VPS内の簡易制御を利用する。

---

# 33. 重複生成対策

同一キーワードが短時間に繰り返された場合、

```text
水仙
水仙
水仙
水仙
```

すべてを生成するとAPI料金が発生する。

そのため将来的に、

```text
idempotency_key
```

を導入する。

初期版ではRate Limitのみとする。

---

# 34. エラー設計

## 入力エラー

```text
INVALID_REQUEST
```

HTTP：

```text
400 Bad Request
```

## Gemini APIエラー

```text
IMAGE_GENERATION_API_ERROR
```

HTTP：

```text
502 Bad Gateway
```

## タイムアウト

```text
IMAGE_GENERATION_TIMEOUT
```

HTTP：

```text
504 Gateway Timeout
```

## Firebaseエラー

```text
FIREBASE_UPLOAD_ERROR
```

HTTP：

```text
502 Bad Gateway
```

## システムエラー

```text
INTERNAL_SERVER_ERROR
```

HTTP：

```text
500 Internal Server Error
```

---

# 35. エラーレスポンス

```json
{
    "error_code": "IMAGE_GENERATION_API_ERROR",
    "message": "Image generation failed."
}
```

内部エラーの詳細情報やAPIキーなどはレスポンスに含めない。

---

# 36. リトライ設計

今回の簡易版では、画像生成APIの自動リトライは慎重に扱う。

理由：

```text
API呼び出し
    ↓
実際には画像生成成功
    ↓
レスポンス通信だけ失敗
    ↓
再度画像生成
```

となった場合、二重生成による追加料金が発生する可能性があるため。

初期版では、

```text
Gemini API呼び出し
       ↓
通信エラー
       ↓
failed
```

を基本とする。

将来的にidempotencyや生成状態確認が利用できる場合にリトライを追加する。

---

# 37. タイムアウト設計

画像生成は通常のREST APIより時間がかかる可能性がある。

初期値：

```text
300秒
```

構成：

```text
Client
    │
    │ 最大5分程度
    ▼
Nginx
    │
    ▼
FastAPI
    │
    ▼
Gemini
```

実際の生成時間を測定したうえで最終値を決定する。

---

# 38. 一時ファイル管理

VPS：

```text
/data/images/
```

を一時領域とする。

処理：

```text
Gemini
   ↓
generated.png
   ↓
Firebase Storage
   ↓
Firestore
   ↓
generated.png削除
```

Firebase Storageへの保存が完了したら、VPS上の一時ファイルを削除する。

異常終了したファイルについては定期クリーンアップする。

例：

```text
24時間以上経過した一時画像
        ↓
削除
```

---

# 39. コスト設計

今回の簡易版では、コスト削減のため以下を廃止する。

```text
Redis
Celery
Worker
Frontend
```

そのため、VPS上に必要なサービス数を削減できる。

最大のコスト要因はAI画像生成APIであるため、以下を管理する。

```text
使用モデル
画像サイズ
画像生成回数
Rate Limit
重複生成
```

モデルIDは環境変数から変更可能とする。

---

# 40. 画像生成コスト管理

APIでは必要以上の画像サイズを指定できないようにする。

例えば初期版では、

```text
image_size
    1024
```

のみ許可する。

将来的に、

```text
512
1024
2048
```

などを追加する。

高解像度画像はAPI料金や処理時間に影響する可能性があるため、初期版では選択肢を限定する。

---

# 41. ログ設計

API：

```text
INFO
WARNING
ERROR
```

を出力する。

例：

```text
2026-08-24 10:00:01 INFO image request keyword=水仙
2026-08-24 10:00:01 INFO image generation started
2026-08-24 10:00:30 INFO image generation completed
2026-08-24 10:00:32 INFO firebase upload completed
```

APIキーなどの秘密情報はログに出力しない。

---

# 42. 監視対象

最低限以下を監視する。

```text
CPU使用率
メモリ使用率
ディスク使用率
API稼働状態
Firebase通信
Gemini APIエラー
画像生成失敗数
```

RedisとWorkerの監視は不要。

特にVPSでは一時画像が残り続けないよう、ディスク使用率を監視する。

---

# 43. バックアップ

VPS上の画像は一時データなのでバックアップ対象外とする。

永続データ：

```text
Firebase Storage
Firestore
```

をバックアップ対象とする。

ソースコード：

```text
GitHub
```

で管理する。

秘密情報：

```text
Google API Key
Firebase Service Account
```

はGitHubへ保存しない。

---

# 44. 可用性

初期版：

```text
VPS 1台
    │
    ├── Nginx
    │
    └── FastAPI
```

とする。

RedisやWorkerがないため、元設計より構成が単純になる。

アクセス数が増加した場合は将来的に、

```text
             ┌── FastAPI
Nginx ───────┼── FastAPI
             └── FastAPI
```

へ拡張できる。

ただし画像生成処理を同期実行する設計のため、大量アクセス時には非同期ジョブ方式への変更を検討する。

---

# 45. APIバージョン

API URLは、

```text
/api/v1/
```

を使用する。

例：

```text
POST   /api/v1/images
GET    /api/v1/images
GET    /api/v1/images/{image_id}
DELETE /api/v1/images/{image_id}
```

将来仕様変更した場合、

```text
/api/v2/images
```

を追加できる。

---

# 46. 初期プロジェクト構成

```text
SUISEN-GALLERY-generator/
│
├── README.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── images.py
│   │       └── health.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   ├── schemas/
│   │   └── image.py
│   │
│   ├── services/
│   │   ├── gemini_service.py
│   │   ├── prompt_service.py
│   │   ├── firebase_service.py
│   │   └── image_service.py
│   │
│   └── utils/
│       └── file_utils.py
│
├── data/
│   └── images/
│
├── firebase/
│   └── service-account.json
│
└── docs/
    └── detailed-design.md
```

---

# 47. Docker Compose

簡易版では以下の2サービスとする。

```yaml
services:

  api:
    build: .
    container_name: suisen-api
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data/images:/data/images
      - ./firebase:/app/firebase:ro
    expose:
      - "8000"

  nginx:
    image: nginx:alpine
    container_name: suisen-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
```

RedisおよびWorkerは存在しない。

---

# 48. FastAPI処理イメージ

```text
POST /api/v1/images
        │
        ▼
ImageRequest
        │
        ▼
keyword validation
        │
        ▼
PromptService
        │
        ▼
GeminiService
        │
        ▼
画像データ取得
        │
        ▼
一時ファイル保存
        │
        ▼
FirebaseService
        │
        ├── Storage upload
        │
        └── Firestore insert
        │
        ▼
一時ファイル削除
        │
        ▼
ImageResponse
```

---

# 49. Pydantic Request

```python
from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):

    keyword: str = Field(
        min_length=1,
        max_length=100
    )

    aspect_ratio: str = "16:9"

    image_size: str = "1024"
```

---

# 50. Pydantic Response

```python
from pydantic import BaseModel


class ImageGenerateResponse(BaseModel):

    image_id: str
    status: str
    keyword: str
    image_url: str
```

---

# 51. サービス責務

## GeminiService

```text
GeminiService
├── Gemini API接続
├── プロンプト送信
├── 画像データ取得
└── APIエラー処理
```

## PromptService

```text
PromptService
├── keyword validation
├── keyword normalization
└── prompt generation
```

## FirebaseService

```text
FirebaseService
├── Storage upload
├── Storage delete
├── Firestore insert
├── Firestore find
└── Firestore delete
```

## ImageService

```text
ImageService
├── 画像生成処理
├── 一時ファイル管理
├── Firebase保存
└── Firestore登録
```

---

# 52. 初期開発範囲

## 必須

- [ ] Ubuntuセットアップ
- [ ] Dockerセットアップ
- [ ] Docker Compose
- [ ] Nginx
- [ ] HTTPS
- [ ] FastAPI
- [ ] Python 3.12
- [ ] Google Gemini API
- [ ] Gemini画像生成
- [ ] Firebase Storage
- [ ] Firestore
- [ ] 画像生成API
- [ ] 画像取得API
- [ ] 画像一覧API
- [ ] 画像削除API
- [ ] エラー処理
- [ ] ログ
- [ ] 一時ファイル削除
- [ ] Rate Limit

## 初期版では実装しない

- [ ] Redis
- [ ] Celery
- [ ] Worker
- [ ] PostgreSQL
- [ ] Frontend
- [ ] WebSocket
- [ ] SSE
- [ ] ユーザー認証
- [ ] MR連携
- [ ] 複数参照画像
- [ ] 画像編集
- [ ] 画像延長
- [ ] 動画生成

---

# 53. 開発環境

開発PC：

```text
MacBook
    │
    ├── VS Code
    ├── Git
    └── Docker Desktop
```

本番：

```text
さくらVPS
    │
    ├── Ubuntu
    ├── Docker
    └── Nginx
```

GitHub：

```text
GitHub Repository
    │
    ├── source
    ├── Dockerfile
    ├── docker-compose.yml
    └── documentation
```

---

# 54. MRアプリとの将来連携

APIをWeb画面専用にせず、REST APIとして独立させる。

将来的には、

```text
                 ┌── curl
                 │
                 ├── Python
                 │
                 ├── Web Application
                 │
                 └── Unity MR
                         │
                         ▼
                      FastAPI
                         │
                         ▼
                    Gemini API
```

という構成にできる。

Unity側からもJSON APIを利用可能とする。

---

# 55. 今後の拡張

## Phase 1

```text
キーワード
    ↓
Gemini画像生成
    ↓
PNG/JPEG
    ↓
Firebase Storage
    ↓
Firestore
    ↓
JSON
```

## Phase 2

```text
ユーザー認証
生成履歴
お気に入り
画像削除
```

## Phase 3

```text
画像アップロード
    ↓
参照画像
    ↓
画像生成
```

## Phase 4

```text
画像編集
画像バリエーション生成
高解像度化
```

## Phase 5

```text
Unity MR
    ↓
FastAPI
    ↓
画像取得
```

## Phase 6

必要になった段階で、

```text
FastAPI
   ↓
Queue
   ↓
Worker
```

へ移行する。

Redis/Celeryは最初から導入せず、同期方式で処理できない規模になった時点で導入を検討する。

---

# 56. 設計上の重要な決定事項

| 項目 | 決定 |
|---|---|
| 生成対象 | AI画像 |
| 動画生成 | 使用しない |
| AI | Google Gemini API |
| APIキー | VPS側のみ保持 |
| AI実行場所 | Google |
| VPS GPU | 不要 |
| API | FastAPI |
| Python | 3.12 |
| 非同期処理 | 使用しない |
| Queue | 使用しない |
| Redis | 使用しない |
| Celery | 使用しない |
| Worker | 使用しない |
| 画像一時保存 | VPS |
| 永続画像保存 | Firebase Storage |
| メタデータ | Firestore |
| Frontend | なし |
| 操作方式 | JSON REST API |
| 画像取得 | JSON API |
| 生成方式 | 同期 |
| 状態取得 | 不要 |
| HTTPS | Nginx + TLS |
| DB | Firestoreのみ |
| PostgreSQL | 使用しない |
| MR連携 | 将来対応 |

---

# 57. 今後の実装順序

### Step 1

Google AI Studioで画像生成APIが正常に動作することを確認する。

```text
Google AI Studio
      ↓
Gemini API
      ↓
画像生成
```

### Step 2

FastAPIからGemini APIを呼び出す。

```text
FastAPI
    ↓
Gemini
    ↓
画像
```

### Step 3

Firebase Storageを追加する。

```text
FastAPI
    ↓
Gemini
    ↓
画像
    ↓
Firebase Storage
```

### Step 4

Firestoreを追加する。

```text
FastAPI
    ↓
Gemini
    ↓
Firebase Storage
    ↓
Firestore
```

### Step 5

JSON APIを完成させる。

```text
POST /api/v1/images
GET /api/v1/images
GET /api/v1/images/{image_id}
DELETE /api/v1/images/{image_id}
```

### Step 6

Docker化する。

```text
Docker Compose
    ↓
Nginx
    ↓
FastAPI
```

### Step 7

さくらVPSへデプロイする。

```text
MacBook
    ↓
GitHub
    ↓
さくらVPS
    ↓
Docker
```

### Step 8

HTTPS、Rate Limit、監視を追加する。

---

# 58. 設計完了基準

以下を満たした時点で初期版を完成とする。

```text
[1] JSONで「水仙」を送信
        ↓
[2] FastAPIが受付
        ↓
[3] 入力チェック
        ↓
[4] プロンプト生成
        ↓
[5] Gemini画像生成
        ↓
[6] 画像をVPSへ一時保存
        ↓
[7] Firebase Storageへ保存
        ↓
[8] Firestoreへ登録
        ↓
[9] 一時画像削除
        ↓
[10] JSONでimage_idを返却
        ↓
[11] image_urlを取得
        ↓
[12] クライアントから画像取得
```

---

# 59. 最終構成

```text
                    Internet
                       │
                      HTTPS
                       │
                       ▼
                ┌─────────────┐
                │   Client    │
                │ JSON Request│
                └──────┬──────┘
                       │
                       ▼
                ┌─────────────┐
                │    Nginx    │
                └──────┬──────┘
                       │
                       ▼
                ┌─────────────┐
                │   FastAPI   │
                │ Python 3.12│
                └──────┬──────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
    ┌──────────┐ ┌────────────┐ ┌───────────┐
    │  Gemini  │ │  Firebase  │ │ Firestore │
    │ Image AI │ │  Storage   │ │ Metadata  │
    └──────────┘ └────────────┘ └───────────┘
```

この構成では、VPS上に必要なのはNginxとFastAPIだけであり、元設計のRedis/Celery/Worker/Frontendを削除できる。

PoC・小規模利用ではこの構成を基本とし、アクセス量増加や画像生成処理によるタイムアウト・同時実行数の問題が発生した段階で、非同期ジョブ方式を導入する。
