import os
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func
import google.generativeai as genai

import models, database
# We will import collector module for the /api/collect endpoint, which we'll rewrite later.

app = FastAPI(title="AI Knowledge Hub API V3")

# Auto DB Init
models.Base.metadata.create_all(bind=database.engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static folder exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

@app.get("/{page_name}.html")
def serve_pages(page_name: str):
    if os.path.exists(f"static/{page_name}.html"):
        return FileResponse(f"static/{page_name}.html")
    raise HTTPException(status_code=404, detail="Page not found")

@app.get("/login")
def serve_login_redirect():
    # Login is removed, but route might be cached
    return FileResponse("static/index.html")

# ============================
# API: Articles
# ============================

@app.get("/api/articles")
def get_articles(
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    trust_level: Optional[str] = None,
    score_min: Optional[int] = None,
    score_max: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source_type: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "published_at",
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Article)
    
    if search:
        s = f"%{search}%"
        query = query.filter(or_(
            models.Article.title.ilike(s),
            models.Article.summary_ja.ilike(s),
            models.Article.business_point.ilike(s),
            models.Article.full_text.ilike(s)
        ))
        
    if category and category != "all":
        query = query.filter(models.Article.category == category)
    if trust_level and trust_level != "all":
        query = query.filter(models.Article.trust_level == trust_level)
    if score_min is not None:
        query = query.filter(models.Article.score >= score_min)
    if score_max is not None:
        query = query.filter(models.Article.score <= score_max)
    if source_type and source_type != "all":
        query = query.filter(models.Article.source_type == source_type)
        
    if date_from:
        try:
            d_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            query = query.filter(models.Article.published_at >= d_from)
        except ValueError:
            pass
            
    if sort_by == "score":
        query = query.order_by(desc(models.Article.score))
    else:
        query = query.order_by(desc(models.Article.published_at))
        
    total = query.count()
    total_pages = (total + per_page - 1) // per_page
    skip = (page - 1) * per_page
    
    articles = query.offset(skip).limit(per_page).all()
    
    return {
        "articles": articles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }

@app.get("/api/articles/{id}")
def get_article(id: int, db: Session = Depends(database.get_db)):
    article = db.query(models.Article).filter(models.Article.id == id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Not found")
    return article

class ClipReq(BaseModel):
    folder: str = "default"

@app.post("/api/articles/{id}/clip")
def clip_article(id: int, req: ClipReq, db: Session = Depends(database.get_db)):
    article = db.query(models.Article).filter(models.Article.id == id).first()
    if not article:
        raise HTTPException(status_code=404)
    article.is_clipped = 1
    article.clip_folder = req.folder
    db.commit()
    return {"status": "success"}

@app.delete("/api/articles/{id}/clip")
def unclip_article(id: int, db: Session = Depends(database.get_db)):
    article = db.query(models.Article).filter(models.Article.id == id).first()
    if not article:
        raise HTTPException(status_code=404)
    article.is_clipped = 0
    article.clip_folder = None
    db.commit()
    return {"status": "success"}

# ============================
# API: AI Search
# ============================
class AISearchReq(BaseModel):
    query: str

@app.post("/api/search/ai")
def ai_search(req: AISearchReq, db: Session = Depends(database.get_db)):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    The user is asking a natural language question to search an AI news database.
    Convert their intent into these database filters:
    {{
      "keyword": "Main search term or null",
      "category": "One of: 企業トラッカー, ツール・ローンチ, AI活用ハック, 技術・研究, 社会・倫理・政策, ビジネス・投資, 雑多・コラム, or null",
      "source_type": "youtube or article or null",
      "region": "japan or global or us or eu or null",
      "date_range": "today or week or month or null",
      "company_tags": ["Company name", "or null"],
      "interpreted": "One short Japanese sentence explaining how you interpreted this query"
    }}
    
    User Query: "{req.query}"
    Return ONLY valid JSON.
    """
    try:
        res = model.generate_content(prompt).text.strip()
        if res.startswith("```json"): res = res[7:-3]
        elif res.startswith("```"): res = res[3:-3]
        
        parsed = json.loads(res.strip())
        
        # Build query
        db_query = db.query(models.Article)
        
        if parsed.get("keyword"):
            k = f"%{parsed['keyword']}%"
            db_query = db_query.filter(or_(
                models.Article.title.ilike(k),
                models.Article.summary_ja.ilike(k),
                models.Article.full_text.ilike(k)
            ))
            
        if parsed.get("source_type"):
            db_query = db_query.filter(models.Article.source_type == parsed["source_type"])
            
        if parsed.get("category"):
            db_query = db_query.filter(models.Article.category == parsed["category"])
            
        if parsed.get("region"):
            db_query = db_query.filter(models.Article.region == parsed["region"])
            
        if parsed.get("date_range"):
            d = datetime.utcnow()
            if parsed["date_range"] == "today":
                d = d.replace(hour=0,minute=0,second=0)
            elif parsed["date_range"] == "week":
                d = d - timedelta(days=7)
            elif parsed["date_range"] == "month":
                d = d - timedelta(days=30)
            db_query = db_query.filter(models.Article.published_at >= d)
            
        arts = db_query.order_by(desc(models.Article.published_at)).limit(50).all()
        return {
            "articles": arts,
            "interpreted_query": parsed.get("interpreted", "AI Searching..."),
            "filters_applied": parsed
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="AI parsing failed")

# ============================
# API: Sources & Following
# ============================
class SourceReq(BaseModel):
    type: str
    url: str
    display_name: str
    category: str = "雑多・コラム"
    priority_bonus: int = 0

@app.get("/api/sources")
def get_sources(db: Session = Depends(database.get_db)):
    return db.query(models.CustomSource).all()

@app.post("/api/sources")
def create_source(req: SourceReq, db: Session = Depends(database.get_db)):
    new_src = models.CustomSource(**req.dict())
    db.add(new_src)
    db.commit()
    return new_src

@app.put("/api/sources/{id}")
def toggle_source(id: int, db: Session = Depends(database.get_db)):
    src = db.query(models.CustomSource).filter(models.CustomSource.id == id).first()
    if src:
        src.enabled = 1 if src.enabled == 0 else 0
        db.commit()
        return src
    raise HTTPException(404)

@app.delete("/api/sources/{id}")
def delete_source(id: int, db: Session = Depends(database.get_db)):
    src = db.query(models.CustomSource).filter(models.CustomSource.id == id).first()
    db.delete(src)
    db.commit()
    return {"status": "deleted"}

class DetectReq(BaseModel):
    url: str

@app.post("/api/sources/detect")
def detect_source(req: DetectReq):
    url = req.url.lower()
    if "youtube.com" in url or "youtu.be" in url:
        return {"type": "youtube", "display_name": "New YouTube Channel", "suggested_category": "ツール・ローンチ"}
    elif "reddit.com" in url:
        return {"type": "reddit", "display_name": "New Subreddit", "suggested_category": "雑多・コラム"}
    else:
        return {"type": "rss", "display_name": "New RSS Feed", "suggested_category": "技術・研究"}

# ============================
# API: Clips & Timeline & Stats
# ============================

@app.get("/api/clips")
def get_all_clips(folder: Optional[str] = None, db: Session = Depends(database.get_db)):
    q = db.query(models.Article).filter(models.Article.is_clipped == 1)
    if folder:
        q = q.filter(models.Article.clip_folder == folder)
    return q.order_by(desc(models.Article.published_at)).all()

@app.get("/api/clips/folders")
def get_clip_folders(db: Session = Depends(database.get_db)):
    folders = db.query(models.Article.clip_folder).filter(models.Article.is_clipped == 1).distinct().all()
    return [f[0] for f in folders if f[0]]

@app.get("/api/timeline/calendar")
def get_calendar(db: Session = Depends(database.get_db)):
    arts = db.query(models.Article.published_at).all()
    dates = {}
    for a in arts:
        if a[0]:
            d = a[0].strftime("%Y-%m-%d")
            dates[d] = dates.get(d, 0) + 1
    return {"dates": dates}

@app.get("/api/timeline/stream")
def get_stream(date: str, db: Session = Depends(database.get_db)):
    d_start = datetime.strptime(date, "%Y-%m-%d")
    d_end = d_start + timedelta(days=1)
    arts = db.query(models.Article).filter(
        models.Article.published_at >= d_start,
        models.Article.published_at < d_end
    ).order_by(desc(models.Article.published_at)).all()
    return arts

@app.get("/api/stats")
def get_stats(db: Session = Depends(database.get_db)):
    total = db.query(models.Article).count()
    today_start = datetime.utcnow().replace(hour=0,minute=0,second=0)
    today = db.query(models.Article).filter(models.Article.published_at >= today_start).count()
    high = db.query(models.Article).filter(models.Article.trust_level == "HIGH").count()
    avg_score = db.query(func.avg(models.Article.score)).scalar() or 0
    return {
        "total_articles": total,
        "today_articles": today,
        "high_trust_count": high,
        "avg_score": round(avg_score, 1)
    }

# ============================
# API: Feed & Actions
# ============================

@app.get("/feed/public", response_class=HTMLResponse)
def public_feed(db: Session = Depends(database.get_db)):
    cutoff = datetime.utcnow() - timedelta(days=60)
    arts = db.query(models.Article).filter(
        models.Article.score >= 55,
        models.Article.published_at >= cutoff
    ).order_by(desc(models.Article.score)).limit(100).all()
    
    html = "<html><head><meta charset='utf-8'><title>AI Knowledge Hub Export</title></head><body>"
    html += "<h1>High Quality AI Knowledge Base</h1>"
    for a in arts:
        html += f"<h2>{a.title}</h2>"
        html += f"<p><strong>Date:</strong> {a.published_at}</p>"
        html += f"<p><strong>Source:</strong> {a.source_name}</p>"
        html += f"<p><strong>Score:</strong> {a.score} | <strong>Trust:</strong> {a.trust_level}</p>"
        html += f"<p><strong>Summary:</strong> {a.summary_ja}</p>"
        if a.business_point:
            html += f"<p><strong>Business Insight:</strong> {a.business_point}</p>"
        if a.transcript:
            html += f"<details><summary>Full Transcript/Content</summary><div>{a.transcript}</div></details>"
        html += "<hr>"
    html += "</body></html>"
    return html

@app.post("/api/collect")
def run_collection(bg_tasks: BackgroundTasks):
    try:
        import collector
        bg_tasks.add_task(collector.run_all)
        return {"status": "started", "message": "Collection triggered in background."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
