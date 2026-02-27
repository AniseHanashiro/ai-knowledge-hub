from sqlalchemy import Column, Integer, String, Boolean, JSON, Float, DateTime
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    summary = Column(String)
    summary_ja = Column(String)
    business_point = Column(String)
    full_text = Column(String)
    url = Column(String, unique=True, index=True, nullable=False)
    source_name = Column(String)
    source_type = Column(String)
    category = Column(String)
    tags = Column(JSON)
    company_tags = Column(JSON)
    priority_label = Column(String)
    trust_level = Column(String)
    trust_reason = Column(String)
    score = Column(Float)
    score_details = Column(JSON)
    audience = Column(String)
    region = Column(String)
    published_at = Column(DateTime)
    fetched_at = Column(DateTime)
    transcript = Column(String)
    source_id = Column(Integer)
    is_clipped = Column(Boolean, default=False)
    clip_folder = Column(String)

class CustomSource(Base):
    __tablename__ = "custom_sources"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False) # rss, youtube
    url = Column(String, nullable=False) # rss url or channel it
    display_name = Column(String)
    category = Column(String)
    priority_bonus = Column(Float, default=0.0)
    enabled = Column(Boolean, default=True)
    last_fetched = Column(DateTime)

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    terms = Column(JSON)
    condition = Column(String)
    excludes = Column(JSON)
    bonus = Column(Float, default=0.0)
    enabled = Column(Boolean, default=True)
