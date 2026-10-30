"""Offline support-list regressions; applies migrations in memory and checks the actual SQL."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid


WORKER_DIR = Path(__file__).resolve().parents[1]
TICKET_ID = str(uuid.uuid4())
CUSTOMER_ID = str(uuid.uuid4())


def timestamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    worker = (WORKER_DIR / "worker.js").read_text(encoding="utf-8-sig")
    queries = re.findall(r'env.DB.prepare\("([^"\n]+)"\)', worker)
    list_queries = [
        query
        for query in queries
        if " AS customer_spoke_last FROM support_tickets" in query
    ]
    assert len(list_queries) == 1, "Could not uniquely identify the support-list SQL"
    list_query = list_queries[0]
    line_number = worker[:worker.index(list_query)].count("\n") + 1

    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        migrations = sorted((WORKER_DIR / "migrations").glob("*.sql"))
        for migration in migrations:
            db.executescript(migration.read_text(encoding="utf-8-sig"))
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []

        start = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
        db.execute(
            """INSERT INTO customers
               (id, name, contact_name, contact_email, status, created_at, updated_at)
               VALUES (?, 'Review customer', 'Alice', 'alice@example.com',
                       'active', ?, ?)""",
            (CUSTOMER_ID, timestamp(start), timestamp(start)),
        )
        db.execute(
            """INSERT INTO support_tickets
               (id, reference, customer_id, category, subject, message,
                status, created_at, updated_at)
               VALUES (?, 'CH-2026-REVIEW', ?, 'other', 'Support question',
                       'Original question', 'in_progress', ?, ?)""",
            (TICKET_ID, CUSTOMER_ID, timestamp(start), timestamp(start)),
        )
        db.execute(
            """INSERT INTO support_ticket_messages
               (id, ticket_id, author_name, author_email, message, delivery_status,
                created_at, external_message_id)
               VALUES (?, ?, 'Alice', 'alice@example.com', 'Customer reply',
                       'sent', ?, '<review-reply@example.com>')""",
            (str(uuid.uuid4()), TICKET_ID, timestamp(start)),
        )
        before_failed_reply = db.execute(list_query, ("",)).fetchone()["customer_spoke_last"]

        db.execute(
            """INSERT INTO support_ticket_messages
               (id, ticket_id, author_name, author_email, message,
                delivery_status, created_at)
               VALUES (?, ?, 'Support', 'support@example.com', 'Attempted answer',
                       'failed', ?)""",
            (str(uuid.uuid4()), TICKET_ID, timestamp(start + timedelta(minutes=5))),
        )
        after_failed_reply = db.execute(list_query, ("",)).fetchone()["customer_spoke_last"]
        assert before_failed_reply == 1
        assert after_failed_reply == 1, (
            "Failed replies incorrectly clear customer_spoke_last; "
            "the waiting indicator must survive a failed send."
        )

        # The UI's supportAwaiting() uses these same conditions.
        def awaiting(status, customer_spoke_last):
            return status == "new" or (
                status != "closed" and customer_spoke_last == 1
            )

        print(json.dumps({
            "finding": "failed_reply_clears_waiting_indicator",
            "query_location": f"cloudflare/license-worker/worker.js:{line_number}",
            "customer_spoke_last_before": before_failed_reply,
            "customer_spoke_last_after": after_failed_reply,
            "waiting_indicator_before": awaiting("in_progress", before_failed_reply),
            "waiting_indicator_after": awaiting("in_progress", after_failed_reply),
            "regression_passed": True,
        }, indent=2))

        for index in range(500):
            created_at = timestamp(start + timedelta(minutes=10, seconds=index))
            db.execute(
                """INSERT INTO support_tickets
                   (id, reference, customer_id, category, subject, message,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, 'other', 'Another question', 'Question',
                           'new', ?, ?)""",
                (
                    str(uuid.uuid4()), f"CH-2026-REVIEW-{index}", CUSTOMER_ID,
                    created_at, created_at,
                ),
            )
        # Exercise the exact keyset query over more than two result pages.
        tickets = db.execute(list_query, ("",)).fetchall()
        stored_count = db.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0]
        existing_visible = any(ticket["id"] == TICKET_ID for ticket in tickets)
        assert stored_count == 501
        assert len(tickets) == 501 and existing_visible, (
            "The pagination lookahead did not return all expected rows; "
            "check the keyset query."
        )
        print(json.dumps({
            "finding": "list_limit_hides_active_ticket",
            "query_location": f"cloudflare/license-worker/worker.js:{line_number}",
            "stored_tickets": stored_count,
            "returned_tickets": len(tickets),
            "in_progress_ticket_visible": existing_visible,
            "regression_passed": True,
        }, indent=2))
        for i in range(600):
            db.execute("INSERT INTO support_tickets (id, reference, customer_id, category, subject, message, status, created_at, updated_at) VALUES (?, ?, ?, 'other', 'Page test', 'Message', 'new', ?, ?)", (str(uuid.uuid4()), 'CH-PAGE-' + str(i), CUSTOMER_ID, timestamp(start), timestamp(start)))
        cursor, ids = "", []
        while True:
            page = db.execute(list_query, (cursor,)).fetchall()
            ids.extend(row["id"] for row in page[:500])
            if len(page) <= 500: break
            cursor = page[499]["id"]
        assert len(ids) == len(set(ids)) == 1101 and TICKET_ID in ids
        print("PASS: 1101 tickets fetched exactly once across pages")
        print(f"Applied {len(migrations)} migrations; both regression checks passed in memory.")


if __name__ == "__main__":
    main()
