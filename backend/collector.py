import os
import json
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import requests

import models, database
from sqlalchemy.orm import Session

DEFAULT_RSS_SOURCES = [
    {"url": "https://hnrss.org/frontpage?q=AI", "name": "Hacker News AI", "category": "技術・研究"},
    {"url": "https://www.reddit.com/r/MachineLearning/.rss", "name": "Reddit ML", "category": "技術・研究"},
    {"url": "http://export.arxiv.org/rss/cs.AI", "name": "arXiv AI", "category": "技術・研究"},
    {"url": "https://techcrunch.com/tag/artificial-intelligence/feed/", "name": "TechCrunch AI", "category": "企業トラッカー"},
    {"url": "https://venturebeat.com/category/ai/feed/", "name": "VentureBeat AI", "category": "ビジネス・投資"},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "name": "The Verge AI", "category": "ツール・ローンチ"},
    {"url": "https://openai.com/blog/rss.xml", "name": "OpenAI Blog", "category": "企業トラッカー"},
    {"url": "https://blog.google/technology/ai/rss/", "name": "Google AI Blog", "category": "企業トラッカー"},
    {"url": "https://www.anthropic.com/rss.xml", "name": "Anthropic Blog", "category": "企業トラッカー"},
]

DEFAULT_YOUTUBE = [
    {"url": "UCZHmQk67mSJgfCCTn7xBfew", "name": "Yannic Kilcher"},
    {"url": "UCbfYPyITQ-7l4upoX8nvctg", "name": "Two Minute Papers"},
    {"url": "UCgpjWze2V0I2RmGE7-dZ_Lw", "name": "Matt Wolfe"},
]

GEMINI_PROMPT = """
You are an expert AI news curator. Analyze this text/transcript and return a structured JSON.
If the content is NOT about artificial intelligence, return an empty JSON object: {}

JSON Schema:
{
  "category": "One of: 企業トラッカー, ツール・ローンチ, AI活用ハック, 技術・研究, 社会・倫理・政策, ビジネス・投資, 雑多・コラム",
  "tags": ["tag1", "tag2", "tag3"],
  "company_tags": ["company1"],
  "priority_label": "BREAKING or HOT or WATCH or INFO",
  "trust_level": "HIGH or MEDIUM or LOW",
  "trust_reason": "One Japanese sentence explaining why this trust level was given",
  "summary_ja": "3 sentence Japanese summary. Separate sentences by newline.",
  "business_point": "One Japanese sentence explaining the business impact/use case",
  "audience": "general or developer or business or researcher",
  "region": "global or japan or us or eu",
  "score": {
    "category_relevance": number (0-40),
    "trust": number (0-30),
    "recency": number (0-20),
    "multi_source": number (0-10),
    "total": number (SUM of above, max 100)
  }
}

Return ONLY the raw JSON.
Content to analyze:
"""

def init_sources(db: Session):
    for rss in DEFAULT_RSS_SOURCES:
        if not db.query(models.CustomSource).filter(models.CustomSource.url == rss["url"]).first():
            db.add(models.CustomSource(type="rss", url=rss["url"], display_name=rss["name"], category=rss["category"]))
    for yt in DEFAULT_YOUTUBE:
        if not db.query(models.CustomSource).filter(models.CustomSource.url == yt["url"]).first():
            db.add(models.CustomSource(type="youtube", url=yt["url"], display_name=yt["name"], category="ツール・ローンチ"))
    db.commit()

def fetch_youtube_video(video_id: str):
    try:
        ts = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([t['text'] for t in ts])
        return text
    except Exception:
        return ""

def process_item(title, url, content, source_name, source_type, db, model):
    if db.query(models.Article).filter(models.Article.url == url).first():
        return False
        
    try:
        prompt = f"{GEMINI_PROMPT}\nTitle: {title}\nSource: {source_name}\nContent: {content[:8000]}"
        res = model.generate_content(prompt).text.strip()
        if res.startswith("```json"): res = res[7:-3]
        elif res.startswith("```"): res = res[3:-3]
        
        parsed = json.loads(res.strip())
        if not parsed.get("category"):
            return False
            
        score_data = parsed.get("score", {})
        total_score = score_data.get("total", 0)
        if total_score < 40:
            return False
            
        article = models.Article(
            title=title,
            full_text=content,
            url=url,
            source_name=source_name,
            source_type=source_type,
            category=parsed.get("category", "雑多・コラム"),
            tags=json.dumps(parsed.get("tags", [])),
            company_tags=json.dumps(parsed.get("company_tags", [])),
            priority_label=parsed.get("priority_label", "INFO"),
            trust_level=parsed.get("trust_level", "MEDIUM"),
            trust_reason=parsed.get("trust_reason", ""),
            score=total_score,
            score_details=json.dumps(score_data),
            audience=parsed.get("audience", "general"),
            region=parsed.get("region", "global"),
            summary_ja=parsed.get("summary_ja", ""),
            business_point=parsed.get("business_point", ""),
            published_at=datetime.utcnow(),
            transcript=content if source_type == 'youtube' else None
        )
        db.add(article)
        db.commit()
        return True
    except Exception as e:
        print(f"Failed to process {title}: {e}")
        return False

def run_all(status_dict=None):
    if status_dict is None:
        status_dict = {}
        
    db = database.SessionLocal()
    try:
        if status_dict: status_dict["message"] = "Initializing sources..."
        init_sources(db)
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        sources = db.query(models.CustomSource).filter(models.CustomSource.enabled == 1).all()
        for src in sources:
            try:
                if status_dict: status_dict["message"] = f"Fetching {src.display_name}..."
                if src.type == "rss":
                    feed = feedparser.parse(src.url)
                    for entry in getattr(feed, 'entries', [])[:10]:
                        title = entry.title
                        url = entry.link
                        content = BeautifulSoup(entry.description, 'html.parser').get_text() if hasattr(entry, 'description') else ""
                        process_item(title, url, content, src.display_name, "article", db, model)
                elif src.type == "youtube":
                    yt_feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={src.url}"
                    feed = feedparser.parse(yt_feed_url)
                    for entry in getattr(feed, 'entries', [])[:3]:
                        title = entry.title
                        url = entry.link
                        video_id = entry.yt_videoid
                        content = fetch_youtube_video(video_id)
                        process_item(title, url, content, src.display_name, "youtube", db, model)
                
                src.last_fetched = datetime.utcnow()
                db.commit()
            except Exception as e:
                err_msg = f"Error fetching source {src.display_name}: {e}"
                print(err_msg)
                if status_dict: status_dict["last_error"] = str(e)
                
        if status_dict: status_dict["message"] = "Collection complete."
    except Exception as e:
        err_msg = f"Fatal error in collection: {e}"
        print(err_msg)
        if status_dict: 
            status_dict["last_error"] = str(e)
            status_dict["message"] = "Failed"
    finally:
        db.close()

if __name__ == "__main__":
    run_all()
