# AI Knowledge Hub

AIを中心とした技術やニュースの自動収集・AI分析・検索ハブです。

## セットアップ

1. \`cd backend && pip install -r ../requirements.txt\`
2. \`python database.py\` (データベースとデフォルトソースの初期化)
3. \`uvicorn main:app --reload --port 8000\`

ブラウザで \`http://localhost:8000\` にアクセスします。
