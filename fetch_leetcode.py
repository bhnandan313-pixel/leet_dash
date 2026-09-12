"""
Fetches stats for every username in data/usernames.json from LeetCode's
public (unofficial) GraphQL endpoint, and writes/updates data/leaderboard.json.

This endpoint is undocumented and can change or start blocking without notice.
If it breaks, the fix is almost always: update the query below to match
LeetCode's current schema, or add/rotate headers.
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
USERNAMES_FILE = ROOT / "data" / "usernames.json"
LEADERBOARD_FILE = ROOT / "data" / "leaderboard.json"

GRAPHQL_URL = "https://leetcode.com/graphql/"

QUERY = """
query getUserStats($username: String!) {
  matchedUser(username: $username) {
    username
    profile {
      ranking
      realName
    }
    submitStats: submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
    tagProblemCounts {
      advanced { tagName tagSlug problemsSolved }
      intermediate { tagName tagSlug problemsSolved }
      fundamental { tagName tagSlug problemsSolved }
    }
    submissionCalendar
  }
}
"""


def fetch_user(username: str) -> dict | None:
    payload = json.dumps({
        "query": QUERY,
        "variables": {"username": username},
    }).encode("utf-8")

    req = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            # LeetCode's endpoint rejects requests without a plausible referer.
            "Referer": f"https://leetcode.com/{username}/",
            "User-Agent": "Mozilla/5.0 (leaderboard-fetch-script)",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  ! request failed for {username}: {e}")
        return None

    matched = body.get("data", {}).get("matchedUser")
    if matched is None:
        print(f"  ! no such LeetCode user: {username}")
        return None
    return matched


def compute_streak(submission_calendar_raw: str) -> int:
    """submissionCalendar is a JSON string: {unix_day_start: submissions_that_day}."""
    if not submission_calendar_raw:
        return 0
    calendar = json.loads(submission_calendar_raw)
    active_days = set()
    for ts_str, count in calendar.items():
        if int(count) > 0:
            day = datetime.fromtimestamp(int(ts_str), tz=timezone.utc).date()
            active_days.add(day)

    if not active_days:
        return 0

    today = datetime.now(timezone.utc).date()
    # Streak counts backward from today OR yesterday (so it doesn't zero out
    # just because today's problem hasn't been solved yet).
    cursor = today if today in active_days else today.fromordinal(today.toordinal() - 1)
    if cursor not in active_days:
        return 0

    streak = 0
    while cursor in active_days:
        streak += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return streak


def difficulty_breakdown(submit_stats: dict) -> dict:
    out = {"Easy": 0, "Medium": 0, "Hard": 0, "All": 0}
    for entry in submit_stats.get("acSubmissionNum", []):
        if entry["difficulty"] in out:
            out[entry["difficulty"]] = entry["count"]
    return out


def tag_breakdown(tag_counts: dict) -> list:
    tags = []
    for bucket in ("fundamental", "intermediate", "advanced"):
        for t in tag_counts.get(bucket, []) or []:
            if t["problemsSolved"] > 0:
                tags.append({"tag": t["tagName"], "solved": t["problemsSolved"]})
    tags.sort(key=lambda x: -x["solved"])
    return tags


def load_existing() -> dict:
    if LEADERBOARD_FILE.exists():
        return json.loads(LEADERBOARD_FILE.read_text())
    return {"users": {}}


def main():
    tracked = json.loads(USERNAMES_FILE.read_text())
    board = load_existing()
    today_str = datetime.now(timezone.utc).date().isoformat()

    for entry in tracked:
        username = entry["username"]
        display_name = entry.get("display_name", username)
        print(f"Fetching {username} ...")

        data = fetch_user(username)
        if data is None:
            continue

        diffs = difficulty_breakdown(data["submitStats"])
        tags = tag_breakdown(data.get("tagProblemCounts", {}) or {})
        streak = compute_streak(data.get("submissionCalendar"))

        user_record = board["users"].setdefault(username, {
            "display_name": display_name,
            "history": {},
        })
        user_record["display_name"] = display_name
        user_record["current"] = {
            "total_solved": diffs["All"],
            "easy": diffs["Easy"],
            "medium": diffs["Medium"],
            "hard": diffs["Hard"],
            "streak": streak,
            "top_tags": tags[:8],
        }
        # One snapshot per day, keyed by date, so re-runs same day overwrite
        # instead of piling up duplicate points on the graph.
        user_record["history"][today_str] = diffs["All"]

        time.sleep(1)  # be polite to LeetCode's endpoint

    board["last_updated"] = datetime.now(timezone.utc).isoformat()
    LEADERBOARD_FILE.write_text(json.dumps(board, indent=2))
    print(f"Wrote {LEADERBOARD_FILE}")


if __name__ == "__main__":
    main()
