import os
import datetime
import json
import feedparser
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from database import SessionLocal
from models import Article, CustomSource

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("Valid GEMINI_API_KEY is required.")
    return genai.Client(api_key=api_key)

def analyze_content(title, text, source_type):
    client = get_gemini_client()
    safe_text = (text or "")[:4000]
    prompt = f"""
    以下のコンテンツを分析し、指定されたフォーマットのJSONで出力してください。
    
    タイトル: {title}
    種別: {source_type}
    コンテンツ: {safe_text}
    
    【JSON出力要件】
    {{
        "category": "LLM または 画像生成 または エージェント または 開発ツール または 研究 または ビジネス または 全般",
        "tags": ["技術", "概念", "などのタグを3-5個"],
        "company_tags": ["関連する企業名を1-3個。なければ空配列"],
        "priority_label": "BREAKING または HOT または HIGH または MEDIUM または LOW",
        "trust_level": "HIGH または MEDIUM または LOW",
        "trust_reason": "その信頼度の理由を1文で",
        "summary_ja": "日本語3行要約",
        "business_point": "ビジネスへの影響を1文で",
        "score_details": {{
            "relevance": 0-40,
            "reliability": 0-30,
            "freshness": 0-20,
            "virality": 0-10
        }}
    }}
    JSONコードブロックで返してください。それ以外の文字は不要です。
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        result = response.text.strip()
        if result.startswith("```json"):
            result = result[7:-3].strip()
        elif result.startswith("```"):
            result = result[3:-3].strip()
        return json.loads(result)
    except Exception as e:
        print(f"Gemini Analysis Error: {e}")
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
                # Ensure it's a channel ID, not a full youtube URL, or handle both.
                # Here we assume the DB value is the channel ID because defaults look like UC...
                items = fetch_youtube(source.url)
                
            for item in items:
                # Check exist
                if db.query(Article).filter(Article.url == item["url"]).first():
                    continue
                    
                text_to_analyze = item["summary"]
                transcript = ""
                
                if source.type == "youtube":
                    video_id = item["url"].split("v=")[-1]
                    if video_id:
                        transcript = get_youtube_transcript(video_id)
                        if transcript:
                            text_to_analyze = transcript
                
                analysis = analyze_content(item["title"], text_to_analyze, source.type)
                if not analysis:
                    print(f"Skipping {item['title']} due to analysis failure.")
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
                print(f"Added: {article.title}")
                
            source.last_fetched = datetime.datetime.now()
            db.commit()
            
        except Exception as e:
            print(f"Error processing source {source.url}: {e}")
            
    db.close()
    print("Collection finished.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    collect_data()
