"""
Tests for the database layer (app/queries.py) against a throwaway SQLite file.

Runs without FastAPI, so it works on any Python that can import SQLAlchemy:

    venv/Scripts/python.exe test_queries.py

Covers the read shapes the frontend depends on plus the admin mutations, so a
deployment can be sanity-checked without a browser.
"""
import datetime
import json
import os
import sys
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, queries

failures = []


def hour_now():
    return datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        failures.append(label)


def seed(db):
    now = datetime.datetime.utcnow()
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    featured = models.ContentCandidate(
        id="cand-featured", url="https://youtube.com/watch?v=aaa", source_id="aaa",
        source_type=models.SourceType.YOUTUBE, title="A Featured Video",
        creator_name="Practical Engineering", creator_url="https://youtube.com/c/pe",
        description="d", thumbnail_url="https://img/1.jpg", view_count=1000,
        subscriber_count=500000, upload_date=now - datetime.timedelta(days=30),
        discovered_date=now, status=models.Status.PUBLISHED, theme="Engineering",
        diamond_score=80.0, quality_score=90.0, interestingness_score=85.0,
        rarity_score=100.0, originality_score=70.0, outlier_score=0.0,
        clickbait_penalty=0.0, trustworthiness_score=95.0,
        ai_explanation="Because it is good.",
    )
    queued = models.ContentCandidate(
        id="cand-queued", url="https://quanta.org/a", source_id="https://quanta.org/a",
        source_type=models.SourceType.RSS, title="A Queued Article",
        creator_name="Quanta Magazine", creator_url="https://quanta.org/feed",
        description="d", thumbnail_url="", view_count=None, subscriber_count=None,
        upload_date=now - datetime.timedelta(days=2), discovered_date=now,
        status=models.Status.PENDING_REVIEW, theme="Bioscience",
        diamond_score=88.0, quality_score=92.0, interestingness_score=90.0,
        rarity_score=60.0, originality_score=85.0, outlier_score=0.0,
        clickbait_penalty=5.0, trustworthiness_score=90.0,
        ai_explanation="Rare and excellent.",
    )
    rejected = models.ContentCandidate(
        id="cand-rejected", url="https://youtube.com/watch?v=bbb", source_id="bbb",
        source_type=models.SourceType.YOUTUBE, title="A Rejected Video",
        creator_name="Practical Engineering", creator_url="https://youtube.com/c/pe",
        description="d", thumbnail_url="", view_count=10, subscriber_count=500000,
        upload_date=now, discovered_date=now, status=models.Status.REJECTED,
        theme="Engineering", diamond_score=0.0, trustworthiness_score=10.0,
    )
    # Featured 8 days ago with a recorded outcome: 1000 -> 5000 views = 5x blowup
    old_hour = hour_start - datetime.timedelta(days=8)
    past = models.HourlyOne(
        id="hourly-past", publish_time=old_hour, theme="Engineering",
        candidate_id="cand-featured", editorial_explanation="Because it is good.",
        views_at_feature=1000, views_after_7d=5000, outcome_checked_at=now,
    )
    current = models.HourlyOne(
        id="hourly-now", publish_time=hour_start, theme="Engineering",
        candidate_id="cand-featured", editorial_explanation="Because it is good.",
        views_at_feature=1000,
    )
    db.add_all([featured, queued, rejected, past, current])
    db.add(models.Comment(id="c1", content="hello", display_name="Ada",
                          created_at=now - datetime.timedelta(minutes=5)))
    db.add(models.Comment(id="c2", content="anon msg", display_name=None, created_at=now))
    db.add(models.Feedback(id="f1", hourly_one_id="hourly-past",
                           seen_before=models.SeenBefore.NEVER_SEEN, created_at=now))
    db.add(models.Feedback(id="f2", hourly_one_id="hourly-past",
                           seen_before=models.SeenBefore.KNEW_ALREADY, created_at=now))
    db.commit()


def main():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    engine = create_engine("sqlite:///" + path, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    try:
        seed(db)

        print("\n/hourly")
        hourly = queries.get_hourly(db)
        check("serves the current hour", hourly["hourly"]["id"] == "hourly-now")
        check("not flagged stale", hourly["is_stale"] is False)
        check("includes candidate title", hourly["candidate"]["title"] == "A Featured Video")
        check("theme is a plain string", isinstance(hourly["hourly"]["theme"], str),
              repr(hourly["hourly"]["theme"]))
        check("publish_time is a plain string", isinstance(hourly["hourly"]["publish_time"], str))
        check("exposes source_id for the embed", hourly["candidate"]["source_id"] == "aaa")

        print("\n/comments")
        comments = queries.get_comments(db)
        check("returns today's comments", len(comments) == 2, str(len(comments)))
        check("oldest first for display", comments[0]["content"] == "hello")
        check("keeps display name", comments[0]["display_name"] == "Ada")
        check("anonymous stays null", comments[1]["display_name"] is None)

        created = queries.create_comment(db, "  a new one  ", "  Grace  ")
        check("trims content", created["content"] == "a new one")
        check("trims display name", created["display_name"] == "Grace")
        try:
            queries.create_comment(db, "   ")
            check("rejects empty comment", False)
        except ValueError:
            check("rejects empty comment", True)
        try:
            queries.create_comment(db, "x" * 501)
            check("rejects overlong comment", False)
        except ValueError:
            check("rejects overlong comment", True)

        print("\n/feedback")
        vote = queries.create_feedback(db, "hourly-now", "NEVER_SEEN")
        check("records a vote", vote["seen_before"] == "NEVER_SEEN", str(vote))
        try:
            queries.create_feedback(db, "hourly-now", "BOGUS")
            check("rejects bad enum value", False)
        except ValueError:
            check("rejects bad enum value", True)

        print("\n/archive")
        archive = queries.get_archive(db)
        check("lists both past picks", len(archive) == 2, str(len(archive)))
        check("newest first", archive[0]["hourly_id"] == "hourly-now")
        check("joins candidate data", archive[0]["title"] == "A Featured Video")

        print("\n/admin/queue")
        queue = queries.get_queue(db)
        check("only pending-review candidates", [c["id"] for c in queue] == ["cand-queued"],
              str([c["id"] for c in queue]))
        check("includes score breakdown", queue[0]["rarity_score"] == 60.0)

        print("\n/admin/outcomes")
        outcomes = queries.get_outcomes(db)
        past_row = [o for o in outcomes if o["hourly_id"] == "hourly-past"][0]
        check("computes growth ratio", past_row["growth_ratio"] == 5.0, str(past_row["growth_ratio"]))
        check("tallies never-seen", past_row["never_seen"] == 1)
        check("tallies knew-already", past_row["knew_already"] == 1)
        check("carries frozen scores", past_row["quality_score"] == 90.0)
        pending_row = [o for o in outcomes if o["hourly_id"] == "hourly-now"][0]
        check("no ratio before the 7-day check", pending_row["growth_ratio"] is None)

        print("\n/admin/sources")
        stats = {s["creator_name"]: s for s in queries.get_source_stats(db)}
        pe = stats["Practical Engineering"]
        check("counts candidates per source", pe["candidates"] == 2, str(pe["candidates"]))
        check("counts rejections", pe["rejected"] == 1, str(pe["rejected"]))
        check("averages diamond score", pe["avg_diamond"] == 40.0, str(pe["avg_diamond"]))
        check("counts featured picks", pe["picks_featured"] == 2, str(pe["picks_featured"]))
        check("flags blowups", pe["blowups"] == 1, str(pe["blowups"]))
        # 2 never-seen (one seeded on hourly-past, one cast above on hourly-now)
        # against 1 knew-already, all on Practical Engineering picks.
        check("never-seen rate", pe["never_seen_rate"] == 0.67, str(pe["never_seen_rate"]))
        check("source with no picks still listed", stats["Quanta Magazine"]["picks_featured"] == 0)
        check("avg growth ratio", pe["avg_growth_ratio"] == 5.0, str(pe["avg_growth_ratio"]))

        print("\n/admin/schedule (override)")
        result = queries.feature_candidate(db, "cand-queued")
        check("reuses the current hour slot", result["hourly_id"] == "hourly-now")
        db.expire_all()
        check("displaced candidate returns to queue",
              db.query(models.ContentCandidate).get("cand-featured").status == models.Status.PENDING_REVIEW)
        check("new pick is published",
              db.query(models.ContentCandidate).get("cand-queued").status == models.Status.PUBLISHED)
        current = db.query(models.HourlyOne).get("hourly-now")
        check("resets outcome tracking", current.views_after_7d is None and current.outcome_checked_at is None)
        check("theme follows the new pick", current.theme == "Bioscience")
        check("hourly now serves the override",
              queries.get_hourly(db)["candidate"]["title"] == "A Queued Article")

        print("\nadmin auth")
        os.environ["ADMIN_TOKEN"] = "test-secret"
        os.environ["ADMIN_USERNAME"] = "michael"
        os.environ["ADMIN_PASSWORD"] = "correct horse"
        from app import auth
        check("configured when credentials are set", auth.is_configured() is True)
        check("accepts the right credentials", auth.check_credentials("michael", "correct horse"))
        check("rejects a wrong password", not auth.check_credentials("michael", "nope"))
        check("rejects a wrong username", not auth.check_credentials("eve", "correct horse"))
        session_token, _ = auth.issue_token()
        check("issued token verifies", auth.verify_token(session_token))
        check("raw ADMIN_TOKEN still works for scripts", auth.verify_token("test-secret"))
        check("rejects a tampered token", not auth.verify_token(session_token[:-4] + "beef"))
        check("rejects junk", not auth.verify_token("garbage"))
        check("rejects empty", not auth.verify_token(""))

        # The simple setup: username and password only, no ADMIN_TOKEN at all.
        os.environ.pop("ADMIN_TOKEN", None)
        check("configured with just username and password", auth.is_configured() is True)
        derived_token, _ = auth.issue_token()
        check("session works with a derived signing key", auth.verify_token(derived_token))
        check("no raw-token bypass when ADMIN_TOKEN is unset", not auth.verify_token("test-secret"))
        os.environ["ADMIN_PASSWORD"] = "a new password"
        check("changing the password signs existing sessions out", not auth.verify_token(derived_token))
        os.environ["ADMIN_PASSWORD"] = "correct horse"
        os.environ.pop("ADMIN_USERNAME", None)
        check("not configured without a username", auth.is_configured() is False)
        os.environ["ADMIN_USERNAME"] = "michael"

        print("\n24-hour schedule runway")
        slots = queries.get_schedule(db, 24)
        check("returns 24 slots", len(slots) == 24, str(len(slots)))
        check("first slot is the current hour", slots[0]["is_current_hour"] is True)
        check("current hour shows its pick", slots[0]["title"] is not None)
        check("later slots start empty", slots[5]["hourly_id"] is None)

        future_hour = slots[3]["publish_time"]
        queries.feature_candidate(db, "cand-queued", future_hour)
        refreshed = queries.get_schedule(db, 24)
        check("candidate lands in the chosen future hour",
              refreshed[3]["title"] == "A Queued Article", str(refreshed[3]["title"]))
        # The live view must still serve the current hour, not the future booking
        check("a future pick is not served as live",
              queries.get_hourly(db)["hourly"]["id"] != refreshed[3]["hourly_id"])

        queries.unschedule(db, refreshed[3]["hourly_id"])
        check("unschedule frees the slot", queries.get_schedule(db, 24)[3]["hourly_id"] is None)
        check("unscheduled candidate returns to the queue",
              db.query(models.ContentCandidate).get("cand-queued").status == models.Status.PENDING_REVIEW)
        # Restore the status the later sections expect: this candidate is still
        # the current hour's published pick from the override test above.
        db.query(models.ContentCandidate).get("cand-queued").status = models.Status.PUBLISHED
        db.commit()
        try:
            queries.feature_candidate(db, "cand-queued", "2020-01-01T00:00:00")
            check("refuses to schedule into the past", False)
        except ValueError:
            check("refuses to schedule into the past", True)
        try:
            queries.unschedule(db, "hourly-past")
            check("refuses to unschedule an already published hour", False)
        except ValueError:
            check("refuses to unschedule an already published hour", True)

        print("\npreview and thumbnail exposure")
        # Attach the preview to whichever candidate is actually live right now,
        # so this does not depend on which earlier test scheduled what.
        live_id = queries.get_hourly(db)["candidate"]["id"]
        live_row = db.query(models.ContentCandidate).get(live_id)
        live_row.preview_text = "The opening two sentences of the piece."
        live_row.tone = "Fascinating"
        db.commit()
        payload = queries.get_hourly(db)["candidate"]
        check("hourly exposes preview_text", payload["preview_text"] is not None)
        check("hourly exposes tone", payload["tone"] == "Fascinating")
        arch = [a for a in queries.get_archive(db) if a["title"] == "A Featured Video"][0]
        check("archive exposes preview_text", "preview_text" in arch)
        check("queue exposes thumbnail and preview",
              all("thumbnail_url" in c and "preview_text" in c for c in queries.get_queue(db, 50)))

        print("\nURL safety (third-party feed links)")
        evil = models.ContentCandidate(
            id="cand-evil", url="javascript:alert(document.cookie)", source_id="x",
            source_type=models.SourceType.RSS, title="Malicious Feed Item",
            creator_name="Bad Feed", creator_url="javascript:void(0)",
            thumbnail_url="javascript:alert(1)", description="d",
            discovered_date=datetime.datetime.utcnow(),
            status=models.Status.PENDING_REVIEW, theme="Curious",
            diamond_score=99.0, ai_explanation="Trust me.",
        )
        db.add(evil)
        db.add(models.HourlyOne(id="hourly-evil", publish_time=hour_now() - datetime.timedelta(days=1),
                                theme="Curious", candidate_id="cand-evil"))
        db.commit()

        evil_queue = [c for c in queries.get_queue(db, 50) if c["id"] == "cand-evil"][0]
        check("queue strips javascript: url", evil_queue["url"] is None, repr(evil_queue["url"]))
        evil_archive = [a for a in queries.get_archive(db) if a["hourly_id"] == "hourly-evil"][0]
        check("archive strips javascript: url", evil_archive["url"] is None, repr(evil_archive["url"]))
        check("archive strips javascript: creator_url", evil_archive["creator_url"] is None)
        check("archive strips javascript: thumbnail", evil_archive["thumbnail_url"] is None)
        pinned_evil = queries.get_pick(db, "hourly-evil")
        check("permalink strips javascript: url", pinned_evil["candidate"]["url"] is None)
        check("safe http urls survive", queries.get_pick(db, "hourly-past")["candidate"]["url"]
              == "https://youtube.com/watch?v=aaa")

        # Keep it out of the way of the scheduling checks below.
        db.query(models.HourlyOne).filter(models.HourlyOne.id == "hourly-evil").delete()
        db.query(models.ContentCandidate).filter(
            models.ContentCandidate.id == "cand-evil").update({"status": models.Status.REJECTED})
        db.commit()

        print("\n/pick (permalinks)")
        pinned = queries.get_pick(db, "hourly-past")
        check("returns the requested hour", pinned["hourly"]["id"] == "hourly-past")
        check("flagged as a permalink", pinned["is_permalink"] is True)
        check("never flagged stale", pinned["is_stale"] is False)
        check("carries the candidate", pinned["candidate"]["title"] == "A Featured Video")
        try:
            queries.get_pick(db, "no-such-id")
            check("unknown id raises NotFound", False)
        except queries.NotFound:
            check("unknown id raises NotFound", True)

        print("\nlazy scheduling")
        # Clear this hour, leave a scored candidate waiting, and confirm a plain
        # read fills the slot -- the free-tier case where no scheduler thread ran.
        db.query(models.HourlyOne).filter(models.HourlyOne.id == "hourly-now").delete()
        db.commit()
        waiting = db.query(models.ContentCandidate).get("cand-featured")
        waiting.status = models.Status.PENDING_REVIEW
        db.commit()

        os.environ["LAZY_SCHEDULING"] = "1"
        result = queries.get_hourly(db)
        check("read fills the empty hour", result["is_stale"] is False, str(result["is_stale"]))
        check("features the waiting candidate", result["candidate"]["title"] == "A Featured Video")
        check("candidate is marked published",
              db.query(models.ContentCandidate).get("cand-featured").status == models.Status.PUBLISHED)
        check("snapshots views at feature",
              db.query(models.HourlyOne).filter(
                  models.HourlyOne.publish_time == hour_now()).first().views_at_feature == 1000)

        # A second read must not create a duplicate for the same hour.
        before = db.query(models.HourlyOne).count()
        queries.get_hourly(db)
        check("second read does not double-schedule",
              db.query(models.HourlyOne).count() == before, str(db.query(models.HourlyOne).count()))

        # With nothing left to promote it must fall back rather than raise.
        db.query(models.HourlyOne).filter(models.HourlyOne.publish_time == hour_now()).delete()
        db.query(models.ContentCandidate).update({models.ContentCandidate.status: models.Status.REJECTED})
        db.commit()
        fallback = queries.get_hourly(db)
        check("falls back to the latest pick when nothing is pending", fallback["is_stale"] is True)

        os.environ["LAZY_SCHEDULING"] = "0"
        db.query(models.HourlyOne).filter(models.HourlyOne.publish_time == hour_now()).delete()
        db.commit()
        disabled = queries.get_hourly(db)
        check("respects LAZY_SCHEDULING=0", disabled["is_stale"] is True)
        os.environ.pop("LAZY_SCHEDULING", None)

        print("\n/status")
        st = queries.get_status(db)
        check("reports config block", "database" in st["config"])
        check("reports candidates by status", isinstance(st["content"]["candidates_by_status"], dict))
        check("reports ready_to_feature", isinstance(st["content"]["ready_to_feature"], int))
        check("reports schedule block", "current_hour_filled" in st["schedule"])
        check("leaks no secrets", "DATABASE_URL" not in json.dumps(st)
              and "GEMINI_API_KEY" not in json.dumps(st))
        check("flags lazy scheduling state",
              isinstance(st["config"]["lazy_scheduling_enabled"], bool))

        print("\n/admin/reject")
        queries.reject_candidate(db, "cand-featured")
        db.expire_all()
        check("marks rejected",
              db.query(models.ContentCandidate).get("cand-featured").status == models.Status.REJECTED)
        for missing in ("feature_candidate", "reject_candidate"):
            try:
                getattr(queries, missing)(db, "does-not-exist")
                check("%s raises NotFound" % missing, False)
            except queries.NotFound:
                check("%s raises NotFound" % missing, True)
    finally:
        db.close()
        engine.dispose()
        try:
            os.remove(path)
        except OSError:
            pass

    print("")
    if failures:
        print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("All query-layer checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
