import os
import json
from google import genai
from sqlalchemy import or_
from database import SessionLocal
from models import Article

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("Valid GEMINI_API_KEY is required.")
    return genai.Client(api_key=api_key)

def search_articles(query: str):
    try:
        client = get_gemini_client()
    except ValueError as e:
        return {"error": str(e), "parsed_query": None, "results": []}

    # 1. Parse query
    prompt_parse = f"""
    以下の自然言語クエリから検索条件をJSONで抽出してください。
    クエリ: "{query}"
    
    フォーマット:
    {{
        "keywords": ["検索語1", "検索語2"],
        "source_type": "rss または youtube または null",
        "category": "カテゴリ名 または null"
    }}
    JSONのみを出力してください。Markdownバッククォートを含む場合は取り除いてください。
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt_parse
        )
        result_text = response.text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
        
        parsed = json.loads(result_text)
    except Exception as e:
        print(f"Error parsing query: {e}")
        parsed = {"keywords": [query], "source_type": None, "category": None}
        
    # 2. Search DB
    db = SessionLocal()
    try:
        q = db.query(Article)
        
        if parsed.get("source_type"):
            q = q.filter(Article.source_type == parsed["source_type"])
        if parsed.get("category"):
            q = q.filter(Article.category == parsed["category"])
            
        filters = []
        for kw in parsed.get("keywords", []):
            kw_filter = or_(
                Article.title.icontains(kw),
                Article.summary_ja.icontains(kw),
                Article.full_text.icontains(kw),
                Article.transcript.icontains(kw)
            )
            filters.append(kw_filter)
            
        if filters:
            q = q.filter(or_(*filters))
            
        articles = q.order_by(Article.score.desc()).limit(20).all()
        article_dicts = []
        for a in articles:
            article_dicts.append({
                "id": a.id, "title": a.title, "summary_ja": a.summary_ja,
                "score": a.score, "source_type": a.source_type, "url": a.url
            })
            
    finally:
        db.close()
        
    if not article_dicts:
        return {"parsed_query": parsed, "results": []}
        
    # 3. Re-rank with Gemini
    articles_json = json.dumps(article_dicts, ensure_ascii=False)
    prompt_rank = f"""
    ユーザーのクエリと検索結果のリストがあります。
    クエリに最も関連する順に結果を再ランキングし、各結果について短い関連度ノート(なぜ関連しているか)を付けてください。
    
    クエリ: "{query}"
    検索結果:
    {articles_json}
    
    出力は以下のJSONのみとしてください:
    [
        {{"id": 記事ID, "relevance_note": "関連している理由", "rank_score": 0〜100のスコア}}
    ]
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt_rank
        )
        rank_text = response.text.strip()
        if rank_text.startswith("```json"):
            rank_text = rank_text[7:-3].strip()
        elif rank_text.startswith("```"):
            rank_text = rank_text[3:-3].strip()
            
        ranked = json.loads(rank_text)
        
        # Merge back
        final_results = []
        db = SessionLocal()
        for r in ranked:
            a = db.query(Article).filter(Article.id == r["id"]).first()
            if a:
                a_dict = {c.name: getattr(a, c.name) for c in a.__table__.columns}
                a_dict["relevance_note"] = r.get("relevance_note", "")
                a_dict["ai_rank_score"] = r.get("rank_score", 0)
                final_results.append(a_dict)
        db.close()
        final_results.sort(key=lambda x: x.get("ai_rank_score", 0), reverse=True)
        return {"parsed_query": parsed, "results": final_results}
        
    except Exception as e:
        print(f"Error ranking: {e}")
        db = SessionLocal()
        final_results = []
        for a_dict in article_dicts:
            a = db.query(Article).filter(Article.id == a_dict["id"]).first()
            if a:
                ad = {c.name: getattr(a, c.name) for c in a.__table__.columns}
                ad["relevance_note"] = "AI ranking failed"
                ad["ai_rank_score"] = a_dict["score"]
                final_results.append(ad)
        db.close()
        return {"parsed_query": parsed, "results": final_results}
