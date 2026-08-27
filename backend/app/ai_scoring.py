import os
import json
import requests
from sqlalchemy.orm import Session
from . import models

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

def get_video_transcript(video_id: str) -> str:
    """Fetches the transcript for a YouTube video.

    Supports both library generations: 0.6.x exposes the static
    get_transcript() returning dicts, 1.x uses an instance .fetch()
    returning snippet objects.
    """
    if not YouTubeTranscriptApi:
        return ""
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            segments = YouTubeTranscriptApi.get_transcript(video_id)
        else:
            segments = YouTubeTranscriptApi().fetch(video_id)
        parts = []
        for segment in segments:
            if isinstance(segment, dict):
                parts.append(segment.get("text", ""))
            else:
                parts.append(getattr(segment, "text", ""))
        return " ".join(parts)
    except Exception as e:
        print(f"Could not fetch transcript for {video_id}: {e}")
        return ""

def call_llm(prompt: str) -> dict:
    """Calls the Gemini API directly using requests (compatible with Python 3.6)."""
    # Read at call time (not import time) so it works regardless of when load_dotenv() ran.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        # Mock data must be explicitly opted into, otherwise fake scores end up
        # in the DB and can get auto-published as if they were real evaluations.
        if os.getenv("ALLOW_MOCK_SCORING") == "1":
            print("GEMINI_API_KEY is not set - using MOCK scores (ALLOW_MOCK_SCORING=1).")
            return {
                "quality_score": 85,
                "interestingness_score": 90,
                "trustworthiness_score": 95,
                "originality_score": 80,
                "expertise_score": 90,
                "clickbait_penalty": 0,
                "explanation": "[MOCK] A fascinating mock explanation of this video."
            }
        print("GEMINI_API_KEY is not set. Skipping scoring (set ALLOW_MOCK_SCORING=1 to use mock scores for local testing).")
        return {}
        
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
        content_kind = "video"
    else:
        # RSS/web candidates store their extracted article text in the same slot
        transcript = candidate.transcript or ""
        content_kind = "article"
        
    # Prepare the prompt
    prompt = f"""
    You are an expert content curator for a service called ONE. 
    Our goal is to find exactly one exceptional piece of content per hour. We are looking for "diamonds in the rough" - highly interesting, trustworthy, non-clickbait content by obsessive experts.
    
    Evaluate the following {content_kind} candidate.

    Title: {candidate.title}
    Creator/Publication: {candidate.creator_name}
    Description: {(candidate.description or "")[:500]}...
    {"Transcript" if content_kind == "video" else "Article text"}: {(transcript or "")[:3000]}...
    
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

    def clamp_score(key):
        """Coerce an LLM-provided score to a float in [0, 100]; None if absent/invalid."""
        value = scores.get(key)
        try:
            return max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            return None

    quality = clamp_score("quality_score")
    interestingness = clamp_score("interestingness_score")

    # Without the two core scores the composite is meaningless; leave the
    # candidate PENDING_AI so a later run can retry instead of ranking it at 0.
    if quality is None or interestingness is None:
        print("LLM response missing core scores for", candidate.id, "- leaving as PENDING_AI.")
        return False

    # Map AI scores to the candidate model
    candidate.quality_score = quality
    candidate.interestingness_score = interestingness
    candidate.trustworthiness_score = clamp_score("trustworthiness_score") or 0
    candidate.originality_score = clamp_score("originality_score") or 0
    candidate.expertise_score = clamp_score("expertise_score") or 0
    candidate.clickbait_penalty = clamp_score("clickbait_penalty") or 0
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
    
    if candidate.view_count is None:
        # Articles/RSS have no view data - unknown reach is not the same as
        # obscure, so use a neutral rarity instead of maxing it out.
        rarity = 60
    elif views < 5000:
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
    # Channels that hide their subscriber count come through as 0 - without real
    # subscriber data the ratio is meaningless, so no bonus in that case.
    ratio = (views / subs) if subs > 0 else 0
    
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
