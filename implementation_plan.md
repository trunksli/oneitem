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
*   **AI Scoring Pipeline (`ai_scoring.py`):** Uses Gemini 1.5 Flash (via REST) to evaluate candidates. 
    *   It extracts transcripts and evaluates content based on: Quality, Interestingness, Rarity, Originality, and Clickbait (Penalty).
    *   **Viral Outlier Score:** We implemented a hybrid calculation that checks the video's views against the channel's subscriber count. If a video is recent (under 14 days old) and has a view-to-subscriber ratio > 3x, it receives a massive score bonus. This bubbles potential "pre-viral" hits to the top.
    *   **Rotating Themes:** The AI assigns a `Theme` (e.g., Bioscience, Architecture, Oddball, AI) to each candidate so content can rotate predictably throughout the day.
*   **Auto-Scheduler (`auto_schedule.py`):** Automatically promotes the highest-scoring `ContentCandidate` to the active `HourlyOne` slot.
*   **API Server (`simple_api.py`):** A lightweight pure-Python HTTP server serving the active `HourlyOne` and managing real-time chat endpoints.

### 2.2 Frontend (Next.js)
*   **Minimalist UI (`page.tsx`):** A clean, distraction-free interface showing only the current hour's featured content, its metadata, and the AI-generated editorial explanation.
*   **Feedback Mechanism:** Large buttons asking "Never Seen It" vs "I Knew This" to track content novelty.
*   **Side-Panel Chat:** A persistent community chat that slides in from the right. It allows users to discuss the current content. The chat is designed as a "Daily Lobby" that clears at midnight.

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

### Phase A: Admin Review Queue (Manual Curation)
*   Instead of auto-scheduling, build an Admin Dashboard.
*   For each upcoming hour, the system should present a **ranked list of the top 5 candidates** alongside their Diamond/Outlier scores.
*   The admin can review the AI's suggestions and manually select (override) which item becomes the `HourlyOne`.

### Phase B: Expanded Sourcing
*   Expand the ingestion engine beyond YouTube.
*   Write connectors to scrape and score: TikToks, Instagram Reels, long-form blogs, news articles, and obscure websites. 

### Phase C: User System & Community Submissions
*   Create a robust User System (authentication, profiles).
*   Build a submission portal allowing users to suggest content links. These user-submitted links will be fed directly into the `ContentCandidate` pipeline for AI scoring.

### Phase D: Multi-Armed Bandit (A/B Testing)
*   For the first X minutes of every hour, run an A/B test.
*   Split the active audience into 2 or 3 cohorts, showing them different top-ranked videos.
*   The video that receives the highest engagement or "Never Seen It" clicks automatically "wins" and is shown to all users for the remainder of the hour.
*   *Note on UX:* The side-panel chat thread will remain unified and persistent regardless of which video variant the user is seeing. This might create brief cross-conversation confusion, but preserving community continuity is the higher priority.
