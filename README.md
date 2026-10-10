# Sunday Scaries · NFL Predictor

Score predictions for the rest of the 2026 NFL season (Week 5 through the Super Bowl).

- **Predictions:** pick the score of every game. Picks lock at kickoff, and everyone's picks show once a game is locked.
- **Scoring:** 10 for an exact score · 5 for the right winner with the margin within 3 · 3 for the right winner · 0 otherwise.
- **Leaderboard:** season table with pick records, plus weekly winners.
- **Live scores:** in-progress games show the score and clock, plus what your pick would earn if it ended now.
- **Stats:** league leaders and a player to watch.
- **Final Standings:** order all eight divisions before the Week 6 kickoff (Thu 15 Oct, 8:15 PM ET). 3 points per team minus places off, +3 for each division winner, +3 for each perfect division (max 144).
- **By Team:** which clubs each player reads best.

Schedule, flexed kickoff times, betting lines, standings and stats come from [nflverse](https://github.com/nflverse); live scores come from ESPN. A GitHub Action refreshes `data/data.json` every hour, and every 15 minutes during game windows.

## One-time setup (about 15 minutes)

### 1. Turn on GitHub Pages
Repo **Settings → Pages**. Under *Build and deployment*, set Source to **Deploy from a branch**, pick **main** and **/(root)**, and save.
After a minute the site is live at `https://YOUR-USERNAME.github.io/sunday-scaries/`. It runs in demo mode until step 3.

### 2. Check the data updater
Open the **Actions** tab. If GitHub asks, enable workflows. Open **Update Data** and press **Run workflow** once.
It should finish green and commit a fresh `data/data.json`. If it fails with a permission error, go to
**Settings → Actions → General → Workflow permissions**, choose **Read and write permissions**, save, and run it again.

### 3. Set up sign-in (Firebase, free)
1. Go to [console.firebase.google.com](https://console.firebase.google.com), add a project (any name, Google Analytics off).
2. **Build → Authentication → Get started**, choose **Email/Password**, enable it, save.
3. Still in Authentication, open **Settings → Authorized domains** and add `YOUR-USERNAME.github.io`.
4. **Build → Firestore Database → Create database**. Pick a US location and start in **production mode**.
5. In Firestore, open the **Rules** tab, replace everything with the contents of [`firestore.rules`](firestore.rules), and **Publish**.
6. Click the gear icon → **Project settings**. Under *Your apps*, add a **Web** app (`</>`), give it a nickname, skip hosting.
   Firebase shows a `firebaseConfig` block.
7. Back on GitHub, open [`config.js`](config.js), tap the pencil icon, paste those six values over the placeholders, and commit.

Reload the site: the demo banner disappears and **Sign in** works. Share the link; friends tap **Sign in → Create account**.

**Shortcut:** if Jeet is up for it, you can use his PL predictor's Firebase project instead, so everyone's existing login
works on both sites. Put his config in `config.js`; he adds your `github.io` domain to his authorized domains and merges the
`nfl_picks` and `nfl_tables` blocks from `firestore.rules` into his rules. Display names are shared through the same `users` collection.

## Good to know
- Picks lock in the browser at kickoff, same as the PL site. The Final Standings lock is also enforced by the Firestore rules.
- Nothing needs touching during the season. Flexed games, Week 18 times and playoff matchups appear on their own as nflverse publishes them.
- To change the scoring, look for `pickPoints` in `index.html`. To move the standings deadline, change `STANDINGS_LOCK` there and the timestamp in `firestore.rules`.

## Files
| File | What it does |
| --- | --- |
| `index.html` | The whole site |
| `config.js` | Your Firebase settings |
| `data/data.json` | Schedule, scores, lines, standings and stats, rewritten by the Action |
| `scripts/fetch_data.py` | Builds `data.json` from nflverse and ESPN, no API keys needed |
| `.github/workflows/update-data.yml` | Runs the script on a schedule and commits the result |
| `firestore.rules` | Who can read and write what in Firestore |
