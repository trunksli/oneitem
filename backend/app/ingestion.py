import os
import re
import requests
import datetime
from sqlalchemy.orm import Session
from . import models, database

def get_youtube_api_key():
    # Read at call time (not import time) so it works regardless of when load_dotenv() ran.
    return os.getenv("YOUTUBE_API_KEY")

def get_channel_info(channel_id: str):
    url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails,statistics&id={channel_id}&key={get_youtube_api_key()}"
    res = requests.get(url)
    res.raise_for_status()
    data = res.json()
    if not data.get('items'):
        return None
    return data['items'][0]

def get_playlist_items(playlist_id: str, max_results: int = 10):
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}&maxResults={max_results}&key={get_youtube_api_key()}"
    res = requests.get(url)
    res.raise_for_status()
    return res.json().get('items', [])

def get_videos_details(video_ids: list):
    ids_str = ",".join(video_ids)
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id={ids_str}&key={get_youtube_api_key()}"
    res = requests.get(url)
    res.raise_for_status()
    return res.json().get('items', [])

def fetch_latest_videos_from_channel(channel_id: str, max_results: int = 10):
    """
    Fetches the latest videos from a specific channel to seed the DB.
    """
    if not get_youtube_api_key():
        raise ValueError("YOUTUBE_API_KEY not set")
        
    channel_info = get_channel_info(channel_id)
    if not channel_info:
        print(f"Channel {channel_id} not found.")
        return []

    uploads_playlist_id = channel_info['contentDetails']['relatedPlaylists']['uploads']
    subscriber_count = int(channel_info['statistics'].get('subscriberCount', 0))

    playlist_items = get_playlist_items(uploads_playlist_id, max_results)
    if not playlist_items:
        return []
        
    video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_items]
    
    # Fetch detailed video stats
    video_items = get_videos_details(video_ids)

    candidates = []
    for item in video_items:
        snippet = item['snippet']
        stats = item['statistics']
        content_details = item['contentDetails']
        
        # Parse ISO 8601 duration (e.g. PT1H2M10S) to seconds.
        # Anchor on the time designator 'T' so the hours component is included
        # and the date-part 'M' (months) can never be misread as minutes.
        duration_raw = content_details['duration']
        duration_match = re.search(r'T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_raw)
        hours, minutes, seconds = (
            (int(g) if g else 0) for g in (duration_match.groups() if duration_match else (0, 0, 0))
        )
        duration_seconds = (hours * 3600) + (minutes * 60) + seconds

        candidates.append({
            "source_id": item['id'],
            "url": f"https://www.youtube.com/watch?v={item['id']}",
            "title": snippet['title'],
            "description": snippet['description'],
            "creator_name": snippet['channelTitle'],
            "creator_url": f"https://www.youtube.com/channel/{snippet['channelId']}",
            "upload_date": datetime.datetime.strptime(snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"),
            "thumbnail_url": snippet['thumbnails'].get('high', snippet['thumbnails'].get('default'))['url'],
            "view_count": int(stats.get('viewCount', 0)),
            "subscriber_count": subscriber_count,
            "duration_seconds": duration_seconds
        })
        
    return candidates

def ingest_seed_channels(db: Session, channel_ids: list):
    """
    Ingests latest videos from a list of 'Obsessive Expert' seed channels.
    """
    for channel_id in channel_ids:
        print(f"Fetching for channel: {channel_id}")
        try:
            videos = fetch_latest_videos_from_channel(channel_id)
            for v_data in videos:
                # Check if already exists
                existing = db.query(models.ContentCandidate).filter_by(url=v_data['url']).first()
                if not existing:
                    candidate = models.ContentCandidate(
                        source_type=models.SourceType.YOUTUBE,
                        **v_data
                    )
                    db.add(candidate)
            db.commit()
        except Exception as e:
            print(f"Error fetching channel {channel_id}: {e}")
            db.rollback()

if __name__ == "__main__":
    # Example Seed Channels
    # Practical Engineering: UCMOqf8ab-42UUQIdVoKwjlQ
    # Technology Connections: UCy0tKL1T7wFoYcxCe0xjN6Q
    SEED_CHANNELS = [
        "UCMOqf8ab-42UUQIdVoKwjlQ", 
        "UCy0tKL1T7wFoYcxCe0xjN6Q"
    ]
    
    # Simple manual run
    db_gen = database.get_db()
    db = next(db_gen)
    print("Starting ingestion...")
    ingest_seed_channels(db, SEED_CHANNELS)
    print("Ingestion complete.")

