import os
import datetime
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional

from database import get_db, init_db
import models
from ai_search import search_articles
from collector import collect_data
from feed import generate_atom_feed

app = FastAPI(title="AI Knowledge Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class SourceCreate(BaseModel):
    url: str
    source_type: Optional[str] = None

class SourceUpdate(BaseModel):
    enabled: bool

class ATSearchRequest(BaseModel):
    query: str

class KeywordCreate(BaseModel):
    terms: List[str]

# ========================
# Frontend Routes
# ========================
@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

@app.get("/{page}.html")
def serve_html(page: str):
    return FileResponse(f"static/{page}.html")

# ========================
# API Endpoints
# ========================
@app.get("/api/articles")
def get_articles(
    category: Optional[str] = None,
    priority: Optional[str] = None,
    source_type: Optional[str] = None,
    days: Optional[int] = 7,
    min_score: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(models.Article)
    if category:
        q = q.filter(models.Article.category == category)
    if priority:
        q = q.filter(models.Article.priority_label == priority)
    if source_type:
        q = q.filter(models.Article.source_type == source_type)
    if days:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        q = q.filter(models.Article.published_at >= cutoff)
    if min_score:
        q = q.filter(models.Article.score >= min_score)
    if search:
        q = q.filter(
            models.Article.title.icontains(search) | 
            models.Article.summary_ja.icontains(search)
        )
        
    return q.order_by(desc(models.Article.score)).limit(100).all()

@app.get("/api/articles/{id}")
def get_article(id: int, db: Session = Depends(get_db)):
    a = db.query(models.Article).filter(models.Article.id == id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Not found")
    return a

@app.post("/api/articles/{id}/clip")
def clip_article(id: int, folder: Optional[str] = None, db: Session = Depends(get_db)):
    a = db.query(models.Article).filter(models.Article.id == id).first()
    if not a:
        raise HTTPException(status_code=404)
    a.is_clipped = True
    a.clip_folder = folder or "default"
    db.commit()
    return {"success": True}

@app.delete("/api/articles/{id}/clip")
def unclip_article(id: int, db: Session = Depends(get_db)):
    a = db.query(models.Article).filter(models.Article.id == id).first()
    if not a:
        raise HTTPException(status_code=404)
    a.is_clipped = False
    a.clip_folder = None
    db.commit()
    return {"success": True}

@app.post("/api/search/ai")
def ai_search_endpoint(req: ATSearchRequest):
    res = search_articles(req.query)
    return res

@app.get("/api/sources")
def get_sources(db: Session = Depends(get_db)):
    return db.query(models.CustomSource).all()

@app.post("/api/sources")
def add_source(req: SourceCreate, db: Session = Depends(get_db)):
    stype = req.source_type
    if not stype:
        stype = "youtube" if "youtube.com" in req.url or "v=" in req.url or req.url.startswith("UC") else "rss"
    s = models.CustomSource(url=req.url, type=stype, enabled=True, display_name=req.url)
    db.add(s)
    db.commit()
    return s

@app.put("/api/sources/{id}")
def update_source(id: int, req: SourceUpdate, db: Session = Depends(get_db)):
    s = db.query(models.CustomSource).filter(models.CustomSource.id == id).first()
    if not s:
        raise HTTPException(status_code=404)
    s.enabled = req.enabled
    db.commit()
    return s

@app.delete("/api/sources/{id}")
def delete_source(id: int, db: Session = Depends(get_db)):
    s = db.query(models.CustomSource).filter(models.CustomSource.id == id).first()
    if not s:
        raise HTTPException(status_code=404)
    db.delete(s)
    db.commit()
    return {"success": True}

@app.get("/api/keywords")
def get_keywords(db: Session = Depends(get_db)):
    return db.query(models.Keyword).all()

@app.post("/api/keywords")
def add_keyword(req: KeywordCreate, db: Session = Depends(get_db)):
    k = models.Keyword(terms=req.terms)
    db.add(k)
    db.commit()
    return k

@app.delete("/api/keywords/{id}")
def delete_keyword(id: int, db: Session = Depends(get_db)):
    k = db.query(models.Keyword).filter(models.Keyword.id == id).first()
    if not k:
        raise HTTPException(status_code=404)
    db.delete(k)
    db.commit()
    return {"success": True}

@app.get("/api/timeline")
def get_timeline(days: int = 7, db: Session = Depends(get_db)):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    articles = db.query(models.Article).filter(models.Article.published_at >= cutoff).order_by(desc(models.Article.published_at)).all()
    
    result = {}
    for a in articles:
        if not a.published_at: continue
        d_str = a.published_at.strftime("%Y-%m-%d")
        if d_str not in result:
            result[d_str] = []
        result[d_str].append(a)
    return result

@app.get("/api/clips")
def get_clips(db: Session = Depends(get_db)):
    clipped = db.query(models.Article).filter(models.Article.is_clipped == True).all()
    res = {}
    for c in clipped:
        f = c.clip_folder or "default"
        if f not in res: res[f] = []
        res[f].append(c)
    return res

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_articles = db.query(models.Article).count()
    total_sources = db.query(models.CustomSource).count()
    return {"articles": total_articles, "sources": total_sources}

@app.get("/feed/public")
def get_public_feed(db: Session = Depends(get_db)):
    articles = db.query(models.Article).filter(models.Article.score >= 55).order_by(desc(models.Article.published_at)).limit(50).all()
    feed = generate_atom_feed(articles)
    return Response(content=feed, media_type="application/xml")

@app.post("/api/collect")
def run_collection(background_tasks: BackgroundTasks):
    background_tasks.add_task(collect_data)
    return {"message": "Collection started in background"}
