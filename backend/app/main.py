from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os

from . import models
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ONE - Daily Diamond API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to ONE API"}

@app.get("/candidates")
def get_candidates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    candidates = db.query(models.ContentCandidate).order_by(models.ContentCandidate.diamond_score.desc()).offset(skip).limit(limit).all()
    return candidates

@app.get("/hourly")
def get_hourly_one(db: Session = Depends(get_db)):
    # In a real scenario, this would query for the current hour's date
    hourly = db.query(models.HourlyOne).order_by(models.HourlyOne.publish_time.desc()).first()
    if not hourly:
        raise HTTPException(status_code=404, detail="No hourly one found")
    
    # Also fetch the associated candidate
    candidate = db.query(models.ContentCandidate).filter(models.ContentCandidate.id == hourly.candidate_id).first()
    return {
        "hourly": hourly,
        "candidate": candidate
    }

from pydantic import BaseModel

class CommentCreate(BaseModel):
    content: str

@app.get("/comments")
def get_comments(db: Session = Depends(get_db), limit: int = 50):
    comments = db.query(models.Comment).order_by(models.Comment.created_at.asc()).limit(limit).all()
    return comments

@app.post("/comments")
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    db_comment = models.Comment(content=comment.content)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

# We would add routes for feedback, admin actions, etc.

