import os
import json
import requests
from sqlalchemy.orm import Session
from . import models

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_video_transcript(video_id: str) -> str:
    """Fetches the transcript for a YouTube video."""
    if not YouTubeTranscriptApi:
        return "Transcript extraction library not available."
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine the text
        full_text = " ".join([t['text'] for t in transcript_list])
        return full_text
    except Exception as e:
        print(f"Could not fetch transcript for {video_id}: {e}")
        return ""

def call_llm(prompt: str) -> dict:
    """Calls the Gemini API directly using requests (compatible with Python 3.6)."""
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set.")
        # Return mock data for local testing if no key is provided
        return {
            "quality_score": 85,
            "interestingness_score": 90,
            "trustworthiness_score": 95,
            "originality_score": 80,
            "expertise_score": 90,
            "clickbait_penalty": 0,
            "explanation": "A fascinating mock explanation of this video."
        }
        
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        text_response = data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text_response)
    except Exception as e:
        print(f"LLM API call failed: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
             print(response.text)
        return {}

def score_candidate(db: Session, candidate: models.ContentCandidate):
    """
    Fetches transcript, evaluates the candidate using AI, 
    calculates rarity, and assigns a Diamond Score.
    """
    print(f"Scoring candidate: {candidate.title}")
    
    if candidate.source_type == models.SourceType.YOUTUBE:
        transcript = get_video_transcript(candidate.source_id)
        candidate.transcript = transcript
    else:
        transcript = ""
        
    # Prepare the prompt
    prompt = f"""
    You are an expert content curator for a service called ONE. 
    Our goal is to find exactly one exceptional piece of content per hour. We are looking for "diamonds in the rough" - highly interesting, trustworthy, non-clickbait content by obsessive experts.
    
    Evaluate the following video candidate.
    
    Title: {candidate.title}
    Channel: {candidate.creator_name}
    Description: {candidate.description[:500]}...
    Transcript: {transcript[:3000]}...
    
    Please provide a JSON response with the following keys:
    - quality_score: Integer 0-100. How well-made, substantive, and worthwhile is this?
    - interestingness_score: Integer 0-100. Would an intellectually curious person find this fascinating?
    - trustworthiness_score: Integer 0-100. Is the creator credible? (Penalize medical/political/financial misinformation heavily).
    - originality_score: Integer 0-100. Does this provide something meaningfully different from common content?
    - expertise_score: Integer 0-100. Does the creator demonstrate genuine knowledge or unusual experience?
    - clickbait_penalty: Integer 0-100. Higher means MORE clickbait/sensationalism.
    - theme: String. Pick the single most appropriate theme from this exact list: Bioscience, AI, Weird Food, Architecture, Gaming, Oddball, Random, History, Engineering, Culture.
    - explanation: String. A concise 2-3 sentence editorial explanation of why this was selected and why it's exceptional (do not use generic language like "This fascinating video explores...").
    
    Return ONLY valid JSON.
    """
    
    # Get scores from AI
    scores = call_llm(prompt)
    
    if not scores:
        print("Failed to get scores for", candidate.id)
        return False
        
    # Map AI scores to the candidate model
    candidate.quality_score = scores.get("quality_score", 0)
    candidate.interestingness_score = scores.get("interestingness_score", 0)
    candidate.trustworthiness_score = scores.get("trustworthiness_score", 0)
    candidate.originality_score = scores.get("originality_score", 0)
    candidate.expertise_score = scores.get("expertise_score", 0)
    candidate.clickbait_penalty = scores.get("clickbait_penalty", 0)
    candidate.ai_explanation = scores.get("explanation", "")
    
    theme_str = scores.get("theme", "Random")
    try:
        candidate.theme = models.Theme(theme_str)
    except ValueError:
        candidate.theme = models.Theme.RANDOM
    
    from datetime import datetime
    
    # Calculate Rarity/Obscurity Score (0-100)
    views = candidate.view_count or 0
    subs = candidate.subscriber_count or 0
    
    if views < 5000:
        rarity = 100
    elif views < 50000:
        rarity = 85
    elif views < 500000:
        rarity = 60
    elif views < 2000000:
        rarity = 30
    else:
        rarity = 5
        
    candidate.rarity_score = rarity
    
    # Quick-and-dirty Viral Outlier Score
    # We look for a high ratio of views to subscribers, especially on recent videos.
    # A standard video gets ~10% of subscriber count in views.
    ratio = views / max(subs, 1)
    
    outlier_bonus = 0
    if candidate.upload_date:
        days_old = (datetime.utcnow() - candidate.upload_date).days
        # Only heavily reward "emerging" trends (under 14 days old)
        if days_old <= 14:
            if ratio >= 3.0:
                outlier_bonus = 30  # Massive viral breakout
            elif ratio >= 1.0:
                outlier_bonus = 15  # Strong performer
            elif ratio >= 0.5:
                outlier_bonus = 5   # Above average
                
    candidate.outlier_score = outlier_bonus
    
    # The Diamond Score (Composite)
    # Weights: Quality (0.45), Interestingness (0.25), Rarity (0.2), Originality (0.1)
    # Then we add the outlier_bonus (up to 30 pts) to bubble up pre-viral hits without making it the ONLY factor.
    base_score = (
        (candidate.quality_score * 0.45) +
        (candidate.interestingness_score * 0.25) +
        (candidate.rarity_score * 0.2) +
        (candidate.originality_score * 0.1)
    )
    
    # Apply penalties
    penalty = candidate.clickbait_penalty * 0.5
    
    # Trust check - if trust is too low, nuke the score
    if candidate.trustworthiness_score < 50:
        candidate.diamond_score = 0
        candidate.status = models.Status.REJECTED
        candidate.admin_notes = "Rejected by AI due to low trust score."
    else:
        # Cap the final score at 100
        candidate.diamond_score = max(0, min(100, base_score + candidate.outlier_score - penalty))
        candidate.status = models.Status.PENDING_REVIEW

    db.commit()
    return True
