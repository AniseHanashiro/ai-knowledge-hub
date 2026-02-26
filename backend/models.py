from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    summary = Column(Text)
    full_text = Column(Text)
    url = Column(String, unique=True, index=True, nullable=False)
    source_name = Column(String)
    source_type = Column(String, default="article")
    category = Column(String, default="雑多・コラム")
    tags = Column(String, default="[]")
    company_tags = Column(String, default="[]")
    priority_label = Column(String, default="INFO")
    trust_level = Column(String, default="MEDIUM")
    trust_reason = Column(Text)
    score = Column(Integer, default=0)
    score_details = Column(String, default="{}")
    audience = Column(String, default="general")
    region = Column(String, default="global")
    summary_ja = Column(Text)
    business_point = Column(Text)
    published_at = Column(DateTime)
    fetched_at = Column(DateTime, server_default=func.now())
    transcript = Column(Text)
    source_id = Column(Integer)
    is_clipped = Column(Integer, default=0)
    clip_folder = Column(String)

class CustomSource(Base):
    __tablename__ = "custom_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    display_name = Column(String)
    category = Column(String, default="雑多・コラム")
    priority_bonus = Column(Integer, default=0)
    enabled = Column(Integer, default=1)
    last_fetched = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    terms = Column(String, default="[]")
    condition = Column(String, default="OR")
    excludes = Column(String, default="[]")
    bonus = Column(Integer, default=0)
    enabled = Column(Integer, default=1)
