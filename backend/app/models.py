import uuid
import enum
from sqlalchemy import Column, String, Integer, BigInteger, Text, DateTime, Boolean, ForeignKey, Float, Enum
# sqlalchemy.orm (not sqlalchemy.ext.declarative) so this works on 1.4 and 2.x alike
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class SourceType(str, enum.Enum):
    YOUTUBE = "YOUTUBE"
    RSS = "RSS"
    WEB = "WEB"

class Status(str, enum.Enum):
    PENDING_AI = "PENDING_AI"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"

class SeenBefore(str, enum.Enum):
    NEVER_SEEN = "NEVER_SEEN"
    SEEN_BEFORE = "SEEN_BEFORE"
    KNEW_ALREADY = "KNEW_ALREADY"

class Theme(str, enum.Enum):
    BIOSCIENCE = "Bioscience"
    AI = "AI"
    WEIRD_FOOD = "Weird Food"
    ARCHITECTURE = "Architecture"
    GAMING = "Gaming"
    ODDBALL = "Oddball"
    RANDOM = "Random"
    HISTORY = "History"
    ENGINEERING = "Engineering"
    CULTURE = "Culture"

class ContentCandidate(Base):
    __tablename__ = "content_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, unique=True, index=True)
    source_type = Column(Enum(SourceType), nullable=False)
    source_id = Column(String, index=True)
    title = Column(String)
    description = Column(Text)
    creator_name = Column(String)
    creator_url = Column(String)
    upload_date = Column(DateTime)
    discovered_date = Column(DateTime, default=datetime.utcnow)
    thumbnail_url = Column(String)
    duration_seconds = Column(Integer, nullable=True)
    view_count = Column(BigInteger, nullable=True)
    subscriber_count = Column(BigInteger, nullable=True)
    transcript = Column(Text, nullable=True)
    status = Column(Enum(Status), default=Status.PENDING_AI)
    theme = Column(Enum(Theme), nullable=True)
    
    # Scores (0-100)
    quality_score = Column(Float, nullable=True)
    interestingness_score = Column(Float, nullable=True)
    trustworthiness_score = Column(Float, nullable=True)
    originality_score = Column(Float, nullable=True)
    rarity_score = Column(Float, nullable=True)
    obscurity_score = Column(Float, nullable=True)
    expertise_score = Column(Float, nullable=True)
    clickbait_penalty = Column(Float, nullable=True)
    outlier_score = Column(Float, nullable=True)
    diamond_score = Column(Float, nullable=True)
    
    ai_explanation = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)

class HourlyOne(Base):
    __tablename__ = "hourly_ones"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    publish_time = Column(DateTime, unique=True, index=True) # E.g. 2026-08-23 09:00:00
    theme = Column(Enum(Theme), nullable=False)
    candidate_id = Column(String(36), ForeignKey("content_candidates.id"))
    editorial_explanation = Column(Text, nullable=True)
    is_bandit_winner = Column(Boolean, default=False) # For future multi-armed bandit

    # Incrementality tracking: view count when featured vs ~7 days later.
    # A pick that stayed obscure was incremental; one that exploded anyway was frontrun.
    views_at_feature = Column(BigInteger, nullable=True)
    views_after_7d = Column(BigInteger, nullable=True)
    outcome_checked_at = Column(DateTime, nullable=True)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(Text, nullable=True)

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    hourly_one_id = Column(String(36), ForeignKey("hourly_ones.id"))
    seen_before = Column(Enum(SeenBefore))
    worth_time = Column(Boolean)
    would_recommend = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)

class Comment(Base):
    __tablename__ = "comments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    display_name = Column(String(40), nullable=True)  # user-chosen pseudonym, no account needed
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # The comment thread persists across content changes, but we track when it was posted
    # to facilitate the daily midnight/morning clear out.
