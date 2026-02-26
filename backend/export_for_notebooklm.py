import os
import json
from database import SessionLocal
from models import Article, CustomSource

def export_for_notebooklm():
    db = SessionLocal()
    articles = db.query(Article).order_by(Article.published_at.desc()).all()
    
    export_content = "# AI Knowledge Hub - Export for NotebookLM\n\n"
    export_content += "This document contains all fetched AI trends, articles, and video transcripts, ready for NotebookLM analysis.\n\n"
    export_content += "=" * 80 + "\n\n"
    
    for article in articles:
        export_content += f"## Title: {article.title}\n"
        export_content += f"**Source:** {article.source_name} ({article.source_type})\n"
        export_content += f"**URL:** {article.url}\n"
        export_content += f"**Category:** {article.category}\n"
        export_content += f"**Published Date:** {article.published_at}\n\n"
        export_content += f"### Summary\n{article.summary}\n\n"
        
        if article.full_text:
            export_content += f"### Full Text / Transcript\n{article.full_text}\n\n"
        
        export_content += "=" * 80 + "\n\n"
        
    export_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notebooklm_export.txt")
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(export_content)
        
    print(f"Exported {len(articles)} articles to {export_path}")

if __name__ == "__main__":
    export_for_notebooklm()
