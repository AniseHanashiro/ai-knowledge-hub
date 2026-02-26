# AI Knowledge Hub

個人専用のAIニュース自動収集・整理サイトです。Gemini APIを活用してニュースを自動分類・要約し、スコアリングします。

## 技術スタック
- バックエンド: Python 3.11, FastAPI, SQLite
- フロントエンド: HTML, CSS, Vanilla JS
- AI/API: Google Gemini API (gemini-1.5-flash)

## 起動手順

1. **プロジェクトディレクトリに移動**
   新しいワークスペースとして設定することをお勧めします。
   ```bash
   cd C:\Users\user\.gemini\antigravity\scratch\ai-knowledge-hub
   ```

2. **依存関係のインストール**
   ```bash
   pip install -r requirements.txt
   ```

3. **環境変数の設定**
   `backend/.env.example` をコピーして `backend/.env` を作成します。
   ※`.env` にご自身の `GEMINI_API_KEY` を設定してください。
   ```bash
   # Windows PowerShell
   Copy-Item backend\.env.example backend\.env
   ```

4. **サーバーの起動**
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

5. **ブラウザでアクセス**
   [http://localhost:8000/login](http://localhost:8000/login) にアクセスします。
   初期パスワード: `pass1234` (環境変数 `SITE_PASSWORD` で変更可能)

## NotebookLM用フィード
設定した `FEED_SECRET_TOKEN` を使って以下のURLにアクセスすると、NotebookLM用のフィードが取得できます。
[http://localhost:8000/feed/myfeedsecrettoken123456789abcde](http://localhost:8000/feed/myfeedsecrettoken123456789abcde)

## デイリー収集の実行
手動でニュースを収集する場合は、以下のコマンドを実行します。
```bash
python backend/collector.py
```
