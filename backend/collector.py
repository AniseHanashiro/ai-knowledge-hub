import os
import datetime
import json
import feedparser
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from database import SessionLocal
from models import Article, CustomSource

import time
import random

def get_gemini_analysis(title: str, text: str, source_type: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("[GEMINI] APIキーなし、デフォルト値使用")
        return {}
    
    for attempt in range(4):  # 最大4回試行
        try:
            # リクエスト前に2秒ウェイト（固定）
            time.sleep(2.0)
            
            client = genai.Client(api_key=api_key)
            safe_text = (text or "")[:1500]
            
            prompt = f"""以下のAI/テクノロジーニュース記事を分析してJSON形式で返してください。
            
タイトル: {title}
種別: {source_type}
記事内容:
{safe_text}

必ず以下のJSON形式のみで回答（```不要）:
{{
  "summary_ja": "日本語で3行の要約",
  "tags": ["タグ1", "タグ2"],
  "company_tags": ["関連する企業名を1-3個。なければ空配列"],
  "category": "LLM または 画像生成 または エージェント または 開発ツール または 研究 または ビジネス または 全般",
  "priority_label": "BREAKING または HOT または HIGH または MEDIUM または LOW",
  "trust_level": "HIGH または MEDIUM または LOW",
  "trust_reason": "その信頼度の理由を1文で",
  "business_point": "ビジネスへの影響を1文で",
  "score_details": {{
      "relevance": 0-40,
      "reliability": 0-30,
      "freshness": 0-20,
      "virality": 0-10
  }}
}}"""
            print(f"[GEMINI] 分析開始: {title[:50]}")
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            
            result_text = response.text.strip()
            # JSONブロックの除去
            for marker in ['```json', '```']:
                if marker in result_text:
                    parts = result_text.split(marker)
                    if len(parts) >= 2:
                        result_text = parts[1].split('```')[0].strip()
                        break
            
            result = json.loads(result_text)
            print(f"[GEMINI] ✓ 分析成功: category={result.get('category')}")
            return result
            
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 30 * (2 ** attempt)
                print(f"[RATE LIMIT] 429エラー、{wait}秒待機... (試行{attempt+1}/4)")
                time.sleep(wait)
            elif "json" in err.lower() or "JSONDecodeError" in err:
                print(f"[GEMINI] JSONパースエラー: {err[:100]}")
                # JSON失敗の場合は再試行しない
                return {}
            else:
                print(f"[GEMINI] 予期せぬエラー: {err[:200]}")
                return {}
    
    print("[GEMINI] 最大試行数超過、デフォルト値使用")
    return {}

def fetch_rss(url):
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:5]: # Top 5 recent
        items.append({
            "title": entry.get("title", ""),
            "url": entry.get("link", url),
            "summary": entry.get("summary", ""),
            "published_at": datetime.datetime.now() # Simplified
        })
    return items

def fetch_youtube(channel_id):
    yt_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    return fetch_rss(yt_url)
    
def get_youtube_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'ja'])
        text = " ".join([t['text'] for t in transcript])
        return text
    except Exception as e:
        print(f"Failed to get transcript for {video_id}: {e}")
        return ""

def score_article(details):
    try:
        return details.get("relevance", 10) + details.get("reliability", 10) + details.get("freshness", 10) + details.get("virality", 5)
    except:
        return 0

def collect_data():
    db = SessionLocal()
    sources = db.query(CustomSource).filter(CustomSource.enabled == True).all()
    
    for source in sources:
        try:
            print(f"Fetching source: {source.display_name} ({source.url})")
            items = []
            if source.type == "rss":
                items = fetch_rss(source.url)
            elif source.type == "youtube":
                items = fetch_youtube(source.url)
                
            print(f"[{source.type.upper()}] {source.display_name}: {len(items)}件取得")
                
            MAX_PER_SOURCE = 3
            saved_count = 0
                
            for item in items:
                if saved_count >= MAX_PER_SOURCE:
                    print(f"[LIMIT] {source.display_name}: 最大{MAX_PER_SOURCE}件に達しました")
                    break
                    
                # Check exist
                if db.query(Article).filter(Article.url == item["url"]).first():
                    print(f"[SKIP] 重複スキップ: {item['title'][:50]}")
                    continue
                    
                text_to_analyze = item["summary"]
                transcript = ""
                
                if source.type == "youtube":
                    video_id = item["url"].split("v=")[-1]
                    if video_id:
                        transcript = get_youtube_transcript(video_id)
                        if transcript:
                            text_to_analyze = transcript
                
                analysis = get_gemini_analysis(item["title"], text_to_analyze, source.type)
                if not analysis:
                    print(f"[SKIP] {item['title'][:50]} due to analysis failure.")
                    continue
                
                score = score_article(analysis.get("score_details", {}))
                
                article = Article(
                    title=item["title"],
                    summary=item.get("summary", ""),
                    summary_ja=analysis.get("summary_ja", "要約なし"),
                    business_point=analysis.get("business_point", ""),
                    full_text=text_to_analyze,
                    url=item["url"],
                    source_name=source.display_name,
                    source_type=source.type,
                    category=analysis.get("category", "未分類"),
                    tags=analysis.get("tags", []),
                    company_tags=analysis.get("company_tags", []),
                    priority_label=analysis.get("priority_label", "LOW"),
                    trust_level=analysis.get("trust_level", "LOW"),
                    trust_reason=analysis.get("trust_reason", ""),
                    score=score,
                    score_details=analysis.get("score_details", {}),
                    published_at=item["published_at"],
                    fetched_at=datetime.datetime.now(),
                    transcript=transcript,
                    source_id=source.id
                )
                db.add(article)
                db.commit()
                print(f"[SAVE] 保存: {article.title[:50]}")
                saved_count += 1
                
            source.last_fetched = datetime.datetime.now()
            db.commit()
            
        except Exception as e:
            import traceback
            print(f"[ERROR] processing source {source.url}: {e}")
            traceback.print_exc()
            
    db.close()
    print("Collection finished.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    collect_data()
