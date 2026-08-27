# ONE: The Internet's Hourly Diamond - Architecture & Roadmap

This document serves as the master blueprint for **ONE**. It captures the core product philosophy, the current state of the MVP, and the roadmap for future phases so that any developer or AI assistant can easily understand the context and pick up where development left off.

## 1. Core Concept

The internet is saturated with endless feeds. The philosophy of ONE is:
> **"You don't need another feed. You need one good thing."**

ONE presents exactly **one piece of exceptional content per hour**. The goal is not to maximize endless scrolling, but to find something genuinely worth the user's time (a "Diamond"), especially focusing on emerging trends before they go viral.

---

## 2. Current State (MVP Implemented)

We have built a functional MVP focusing on backend ingestion, AI scoring, and a minimalist frontend.

### 2.1 Backend & Ingestion Engine (Python)
*   **Database:** SQLite (`sql_app_v2.db`) used for rapid MVP prototyping, interfaced via SQLAlchemy.
*   **Ingestion Script (`ingestion.py`):** Uses the YouTube Data API (via direct HTTP requests to avoid Python 3.6 library conflicts) to pull the latest videos from a list of high-quality "seed" channels.
*   **RSS Connector (`rss_ingestion.py`, Phase B):** Ingests articles from RSS/Atom feeds (Quanta, Aeon, Nautilus by default — edit `SEED_FEEDS`), parsing with the stdlib and extracting readable article text into the `transcript` field for scoring. Articles get a neutral rarity score (no view data). TikTok/Instagram are deliberately excluded (no public API; scraping violates ToS) — planned as user-submitted embeds in Phase C.
*   **AI Scoring Pipeline (`ai_scoring.py`):** Uses Gemini via REST (model set by the `GEMINI_MODEL` env var). Scores from the LLM are validated and clamped to 0-100; if the API key is missing, scoring is skipped unless `ALLOW_MOCK_SCORING=1` explicitly opts into mock data.
    *   It extracts transcripts and evaluates content based on: Quality, Interestingness, Rarity, Originality, and Clickbait (Penalty).
    *   **Viral Outlier Score:** We implemented a hybrid calculation that checks the video's views against the channel's subscriber count. If a video is recent (under 14 days old) and has a view-to-subscriber ratio > 3x, it receives a massive score bonus. This bubbles potential "pre-viral" hits to the top.
    *   **Rotating Themes:** The AI assigns a `Theme` (e.g., Bioscience, Architecture, Oddball, AI) to each candidate so content can rotate predictably throughout the day.
*   **Auto-Scheduler (`auto_schedule.py`):** Promotes the highest-scoring `ContentCandidate` to the active `HourlyOne` slot, preferring a different theme than the previous hour so themes rotate.
*   **Hourly Runner (`run_hourly.py`):** Long-running loop that re-runs the ingestion/scoring pipeline every 6 hours (configurable via `PIPELINE_EVERY_HOURS`) and schedules a new `HourlyOne` at the top of every hour.
*   **API Server (`simple_api.py`):** A lightweight pure-Python HTTP server (threaded) serving the active `HourlyOne` (current hour, falling back to the latest with an `is_stale` flag), the daily chat (`/comments`, today's messages only, newest 50), and `/feedback`. A FastAPI equivalent lives in `app/main.py` for when the stack moves to a modern Python.

### 2.2 Frontend (Next.js)
*   **Minimalist UI (`page.tsx`):** A clean, distraction-free interface showing only the current hour's featured content, its metadata, and the AI-generated editorial explanation.
*   **Playable Media:** Clicking the thumbnail plays YouTube content in an embedded player (non-YouTube sources open in a new tab). The page re-checks `/hourly` every minute so an open tab rolls over to the new hour automatically.
*   **Feedback Mechanism:** Large buttons asking "Never Seen It" vs "I Knew This" post to `/feedback` (stored against the current `HourlyOne`) and show a thank-you state.
*   **Side-Panel Chat:** A persistent community chat that slides in from the right. It allows users to discuss the current content. The chat is a "Daily Lobby": the API only returns comments posted since midnight (UTC), so it clears daily. Users can set an optional display name (stored in `localStorage`, sent with each comment — no account needed).
*   **Archive Page (`/archive`):** "Past Diamonds" — every previously featured item, newest first, linking out to the original content.
*   **Admin Review Queue (`/admin`, Phase A):** Token-gated dashboard (set `ADMIN_TOKEN` in `.env`, sent as the `X-Admin-Token` header) showing the ranked `PENDING_REVIEW` queue with full score breakdowns. "Feature Now" overrides the current hour's `HourlyOne` (the displaced pick returns to the queue); "Reject" removes a candidate. The auto-scheduler still covers unattended hours.

---

## 3. Database Schema

The core entities in the SQLite database:
*   **`ContentCandidate`**: Stores the raw video metadata, scores (Quality, Rarity, Outlier, Diamond Score), AI explanation, and Status.
*   **`HourlyOne`**: The schedule table mapping a specific `publish_time` hour block to a `candidate_id` and a `theme`.
*   **`Comment`**: Stores the user chat messages.
*   **`User` / `Feedback`**: Scaffolding exists in `models.py` to track user interaction and feedback.

---

## 4. Future Roadmap & Next Steps (Pending Phases)

The following features are architected conceptually but are **NOT yet implemented**. Future development should prioritize these items.

### Phase A: Admin Review Queue — DONE (MVP version)
*   Implemented as a single ranked queue with a current-hour override at `/admin` (see 2.2). Possible follow-up: per-upcoming-hour slots with pre-assigned picks.

### Phase B: Expanded Sourcing — PARTIALLY DONE
*   RSS/Atom connector for blogs, magazines, and news is live (`rss_ingestion.py`).
*   Remaining: TikToks and Instagram Reels have no public content API and scraping violates their ToS — accept them as user-submitted links (Phase C) rendered via official embeds instead.

### Phase C: User System & Community Submissions
*   Create a robust User System (authentication, profiles).
*   Build a submission portal allowing users to suggest content links. These user-submitted links will be fed directly into the `ContentCandidate` pipeline for AI scoring.

### Phase D: Multi-Armed Bandit (A/B Testing)
*   For the first X minutes of every hour, run an A/B test.
*   Split the active audience into 2 or 3 cohorts, showing them different top-ranked videos.
*   The video that receives the highest engagement or "Never Seen It" clicks automatically "wins" and is shown to all users for the remainder of the hour.
*   *Note on UX:* The side-panel chat thread will remain unified and persistent regardless of which video variant the user is seeing. This might create brief cross-conversation confusion, but preserving community continuity is the higher priority.
