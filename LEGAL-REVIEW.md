# Legal review queue

The Privacy Policy and Terms of Service (`frontend/src/lib/legal.ts`, rendered at
`/privacy` and `/terms`) were drafted by the engineering side, adapted from the
Balmody (Verse) documents. **They have not been reviewed by a lawyer.** This is
the list of what a reviewer is being asked to check, most consequential first.

## 1. Copyright and the DMCA safe harbor

ONE features third-party work: it shows each item's title, the publisher's
`og:image`, a short preview (the opening sentences or an AI-written summary), and
a link or official embed. It keeps at most 3,000 characters of source text, only
until the item is scored.

- **Is the preview-and-link pattern defensible as fair use** for articles, and is
  showing the publisher's own `og:image` acceptable? (Publishers set `og:image`
  specifically for sharing, which helps, but it is not a licence.)
- **DMCA agent.** The Terms describe a takedown process, but safe harbor under 17
  U.S.C. 512 generally requires designating an agent with the US Copyright Office.
  No agent has been registered. Decide whether to register one.

## 2. YouTube API Services terms

YouTube's developer policies require API clients to have a privacy policy and to
tell users they are bound by YouTube's Terms of Service. The Terms include that
clause and the Privacy Policy links Google's policy and says the API is used only
to read public video data. **Confirm the wording meets YouTube's current
requirements**, which change from time to time.

## 3. The anonymous visitor code

Votes and engagement are keyed by HMAC-SHA256 of IP address and User-Agent under
a random daily salt; the IP is never stored and each earlier day's salt is
deleted (`backend/app/visitors.py`). The documents present this as not
identifying anyone.

- **Does a daily-rotated, salted hash of an IP address count as personal
  information** under the CCPA/CPRA, or under GDPR if EU visitors matter? The IP is
  processed transiently to compute the hash even though it is not stored.
- Is **no consent banner** justified on that basis? (This is the position
  privacy-focused analytics providers take, but it is a legal judgement, not a
  technical one.)

## 4. Public chat -- withdrawn for now

The chat has been switched off (`CHAT_ENABLED` unset): nothing can be posted and
`/comments` returns 404. The documents no longer describe it, so **this section
needs no review unless the chat comes back.**

If it does, the questions were: whether email-based reporting is adequate without
an in-product report or delete tool, and Section 230 considerations for a US
operator, including whether the acceptable-use wording is sufficient.

## 5. Children

The service is not directed at under-13s and does not verify age (doing so would
mean collecting identity data). Confirm this is adequate under COPPA given that
the chat accepts free text from anyone.

## 6. AI disclosure

Previews and "why this one" notes are AI-generated and unreviewed. The documents
and a site-wide footer say so. Check whether any disclosure obligation applies
beyond this, and whether AI-written characterisations of third parties' work
carry misrepresentation risk.

## 7. Vimeo films and podcasts

ONE now also features Vimeo Staff Picks (played in Vimeo's own player with
`dnt=1`) and podcast episodes (streamed from the publisher's audio host through
the browser's own player, only after the visitor presses Listen). It reads
Vimeo's public oEmbed endpoint for titles and thumbnails; it never downloads or
re-hosts audio or video.

- **Vimeo:** confirm that embedding public films through the standard player
  needs nothing beyond Vimeo's own terms, and whether the Terms should name Vimeo
  the way they name YouTube.
- **Podcasts:** playing an episode's public enclosure URL is what every podcast
  app does, but ONE is a website, not an app. Confirm that is fine, and that the
  Privacy Policy's note (audio hosts may measure downloads, including network
  address) is enough disclosure.

## Facts the documents depend on

If any of these change, the documents must change with them:

| Statement | Where it is true |
| --- | --- |
| No cookies; no analytics or ad scripts | Whole frontend; fonts self-hosted via `next/font` |
| YouTube plays in privacy-enhanced mode | `frontend/src/app/page.tsx` embed URL |
| Vimeo plays with do-not-track (`dnt=1`) | `frontend/src/app/page.tsx` embed URL |
| Nothing requested from an audio host before Listen | `frontend/src/app/page.tsx` (`<audio>` renders only after Listen) |
| IP never stored; daily salt deleted | `backend/app/visitors.py` |
| One vote per visitor per pick, changeable | `backend/app/queries.py` `create_feedback` |
| No chat; nothing can be posted | `backend/app/main.py` `CHAT_ENABLED`, and no panel in `page.tsx` |
| At most 3,000 chars of source text, cleared once scored | `backend/app/previews.py`, `ai_scoring.py`, `migrations.py` |
| Crawler honours robots.txt and identifies itself | `backend/app/rss_ingestion.py` |
| Only public content is sent to Gemini, never user data | `backend/app/ai_scoring.py` |

Contact address in the documents: `balmodyco@gmail.com`, shared with Balmody
until ONE has its own name (confirmed by the operator, 9 September 2026).
