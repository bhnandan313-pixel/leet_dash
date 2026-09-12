# LeetCode friends leaderboard

Static leaderboard: username + display name in, ranking + difficulty
breakdown + topic tags + streak + a solved-over-time graph out. No login,
no backend server — just LeetCode's own public data, a daily cron job, and
a static page.

## How it works

1. `data/usernames.json` lists who to track.
2. `fetch_leetcode.py` queries LeetCode's GraphQL endpoint for each username
   and writes the result into `data/leaderboard.json`, appending one
   history point per day (for the graph).
3. `.github/workflows/update.yml` runs that script once a day via GitHub
   Actions and commits the updated JSON back to the repo.
4. `index.html` reads `data/leaderboard.json` and renders the leaderboard.
   Click a row to expand top topics for that person.

## Setup

1. Push this repo to GitHub.
2. Edit `data/usernames.json` with real LeetCode usernames + display names.
3. Enable GitHub Pages (Settings → Pages → deploy from `main` / root).
4. Go to the Actions tab → "Update LeetCode leaderboard" → **Run workflow**
   to seed `data/leaderboard.json` for the first time (don't wait for the
   cron — it's set to run daily at 00:30 UTC).
5. Visit your Pages URL. Share that link with friends — no login needed to view.

## Known fragility (read before you're surprised by it)

- LeetCode's GraphQL endpoint is **unofficial and undocumented**. It can
  change shape or start rate-limiting/blocking scripted requests at any
  time. If the Action starts failing, check the workflow run logs first —
  the fix is usually a query field name change or an extra header.
- The graph only gets a new data point once a day (whenever the cron runs),
  not in real time.
- Streak is derived from `submissionCalendar`, which only reflects activity
  visible from LeetCode's side — private/paid-only nuances aside, it should
  match what a user sees on their own profile heatmap.
