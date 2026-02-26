from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi.responses import HTMLResponse
from database import get_db
from models import Article
from auth import verify_feed_token

router = APIRouter(prefix="/feed", tags=["feed"])

@router.get("/{token}", response_class=HTMLResponse)
def get_notebook_feed(token: str, db: Session = Depends(get_db)):
    verify_feed_token(token)
    
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    
    articles = db.query(Article).filter(
        Article.score >= 55,
        Article.published_at >= sixty_days_ago
    ).order_by(Article.published_at.desc()).all()
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>AI Knowledge Hub Feed for NotebookLM</title>
        <style>
            body {{ font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .article {{ margin-bottom: 40px; border-bottom: 1px solid #ccc; padding-bottom: 20px; }}
            .metadata {{ color: #666; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <h1>AI Knowledge Hub - Curated Feed</h1>
        <p>Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    """
    
    for article in articles:
        tags_str = ", ".join(article.tags) if article.tags else ""
        companies_str = ", ".join(article.company_tags) if article.company_tags else ""
        
        html_content += f"""
        <div class="article">
            <h2>{article.title}</h2>
            <div class="metadata">
                <p><strong>Source:</strong> {article.source_name} | <strong>Date:</strong> {article.published_at.strftime('%Y-%m-%d')}</p>
                <p><strong>Category:</strong> {article.category} | <strong>Score:</strong> {article.score}</p>
                <p><strong>Tags:</strong> {tags_str} | <strong>Companies:</strong> {companies_str}</p>
                <p><strong>URL:</strong> <a href="{article.url}">{article.url}</a></p>
            </div>
            <h3>Summary</h3>
            <p>{article.summary}</p>
            <h3>Business Point</h3>
            <p>{article.score_details.get('business_point', 'N/A')}</p>
            <h3>Full Text / Transcript</h3>
            <p>{article.full_text or article.transcript or 'No full text available.'}</p>
        </div>
        """
        
    html_content += """
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)
