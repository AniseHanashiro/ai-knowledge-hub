import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Ensure we can import models when run directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models import Base

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "./ai_knowledge_hub.db")
db_dir = os.path.dirname(os.path.abspath(DATABASE_PATH))
os.makedirs(db_dir, exist_ok=True)
print(f"[DB] データベースパス: {os.path.abspath(DATABASE_PATH)}")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    from models import CustomSource
    if db.query(CustomSource).count() == 0:
        default_rss = [
            ("rss", "https://hnrss.org/frontpage?q=AI", "HackerNews AI"),
            ("rss", "https://www.reddit.com/r/MachineLearning/.rss", "Reddit ML"),
            ("rss", "http://export.arxiv.org/rss/cs.AI", "arXiv cs.AI"),
            ("rss", "https://www.reddit.com/r/artificial/.rss", "Reddit AI"),
            ("rss", "https://feeds.feedburner.com/venturebeat/SZYF", "VentureBeat"),
            ("rss", "https://techcrunch.com/feed/", "TechCrunch"),
        ]
        default_yt = [
            ("youtube", "UCZHmQk67mSJgfCCTn7xBfew", "Two Minute Papers"),
            ("youtube", "UCbfYPyITQ-7l4upoX8nvctg", "Andrej Karpathy"),
            ("youtube", "UCgpjWze2V0I2RmGE7-dZ_Lw", "Yannic Kilcher"),
        ]
        
        for stype, url, name in default_rss + default_yt:
            source = CustomSource(type=stype, url=url, display_name=name, enabled=True)
            db.add(source)
        db.commit()
    db.close()
    print(f"Database initialized at {DATABASE_PATH}")

if __name__ == "__main__":
    init_db()
