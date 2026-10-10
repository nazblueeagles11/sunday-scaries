#!/usr/bin/env python3
"""
Builds data/data.json for the Sunday Scaries NFL predictor. No API keys needed.

Sources:
  - nflverse games.csv / standings.csv: schedule, kickoff times (flexed games included),
    final scores, betting lines, division ranks and playoff seeds
  - nflverse weekly player stats: stat leaders and the player to watch
  - ESPN scoreboard: live scores and the final whistle, so results land within minutes

A failed source never wipes the board: anything missing is carried over from the previous
data.json, and a game that has gone final never goes back to unplayed.

Local testing: point SS_GAMES, SS_STANDINGS, SS_STATS or SS_ESPN at files to skip the network.
"""
import csv, datetime, io, json, os, sys, time, urllib.request
from zoneinfo import ZoneInfo

SEASON = 2026
OUT = os.environ.get("SS_OUT", "data/data.json")
ET = ZoneInfo("America/New_York")
NOW = datetime.datetime.now(datetime.timezone.utc)
UA = {"User-Agent": "Mozilla/5.0 (sunday-scaries hobby project)"}
NFLVERSE = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/"
STATS_URL = f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{SEASON}.csv"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype={st}&week={wk}&dates={season}"
ESPN_POST_WEEK = {19: 1, 20: 2, 21: 3, 22: 5}   # ESPN numbers the playoffs 1-5 with the Pro Bowl as 4
FINAL_AFTER = datetime.timedelta(hours=4)       # without ESPN, only trust a score this long after kickoff

# abbr: [display abbr, full name, nickname, conf, division, badge bg, badge text, accent]
TEAMS = {
    "ARI": ["ARI", "Arizona Cardinals", "Cardinals", "NFC", "West", "#97233F", "#FFFFFF", "#C4364F"],
    "ATL": ["ATL", "Atlanta Falcons", "Falcons", "NFC", "South", "#A71930", "#FFFFFF", "#D2253A"],
    "BAL": ["BAL", "Baltimore Ravens", "Ravens", "AFC", "North", "#241773", "#FFFFFF", "#6B54D6"],
    "BUF": ["BUF", "Buffalo Bills", "Bills", "AFC", "East", "#00338D", "#FFFFFF", "#2E6BE6"],
    "CAR": ["CAR", "Carolina Panthers", "Panthers", "NFC", "South", "#0085CA", "#FFFFFF", "#1D9BE0"],
    "CHI": ["CHI", "Chicago Bears", "Bears", "NFC", "North", "#0B162A", "#FFFFFF", "#E0561C"],
    "CIN": ["CIN", "Cincinnati Bengals", "Bengals", "AFC", "North", "#FB4F14", "#000000", "#FB4F14"],
    "CLE": ["CLE", "Cleveland Browns", "Browns", "AFC", "North", "#FF3C00", "#311D00", "#FF5A1F"],
    "DAL": ["DAL", "Dallas Cowboys", "Cowboys", "NFC", "East", "#003594", "#FFFFFF", "#3D73E0"],
    "DEN": ["DEN", "Denver Broncos", "Broncos", "AFC", "West", "#FB4F14", "#002244", "#FB6A2A"],
    "DET": ["DET", "Detroit Lions", "Lions", "NFC", "North", "#0076B6", "#FFFFFF", "#1A93D9"],
    "GB":  ["GB", "Green Bay Packers", "Packers", "NFC", "North", "#203731", "#FFB612", "#3E9A62"],
    "HOU": ["HOU", "Houston Texans", "Texans", "AFC", "South", "#03202F", "#FFFFFF", "#C8233A"],
    "IND": ["IND", "Indianapolis Colts", "Colts", "AFC", "South", "#002C5F", "#FFFFFF", "#3F78C2"],
    "JAX": ["JAX", "Jacksonville Jaguars", "Jaguars", "AFC", "South", "#006778", "#FFFFFF", "#11A1B3"],
    "KC":  ["KC", "Kansas City Chiefs", "Chiefs", "AFC", "West", "#E31837", "#FFFFFF", "#F0304B"],
    "LA":  ["LAR", "Los Angeles Rams", "Rams", "NFC", "West", "#003594", "#FFD100", "#FFD100"],
    "LAC": ["LAC", "Los Angeles Chargers", "Chargers", "AFC", "West", "#0080C6", "#FFFFFF", "#24A3E8"],
    "LV":  ["LV", "Las Vegas Raiders", "Raiders", "AFC", "West", "#000000", "#A5ACAF", "#B8BFC2"],
    "MIA": ["MIA", "Miami Dolphins", "Dolphins", "AFC", "East", "#008E97", "#FFFFFF", "#12B2BC"],
    "MIN": ["MIN", "Minnesota Vikings", "Vikings", "NFC", "North", "#4F2683", "#FFC62F", "#7E4FC4"],
    "NE":  ["NE", "New England Patriots", "Patriots", "AFC", "East", "#002244", "#FFFFFF", "#D3253C"],
    "NO":  ["NO", "New Orleans Saints", "Saints", "NFC", "South", "#101820", "#D3BC8D", "#D3BC8D"],
    "NYG": ["NYG", "New York Giants", "Giants", "NFC", "East", "#0B2265", "#FFFFFF", "#3558C4"],
    "NYJ": ["NYJ", "New York Jets", "Jets", "AFC", "East", "#125740", "#FFFFFF", "#22986A"],
    "PHI": ["PHI", "Philadelphia Eagles", "Eagles", "NFC", "East", "#004C54", "#FFFFFF", "#11909A"],
    "PIT": ["PIT", "Pittsburgh Steelers", "Steelers", "AFC", "North", "#101820", "#FFB612", "#FFB612"],
    "SF":  ["SF", "San Francisco 49ers", "49ers", "NFC", "West", "#AA0000", "#FFFFFF", "#D42222"],
    "SEA": ["SEA", "Seattle Seahawks", "Seahawks", "NFC", "West", "#002244", "#69BE28", "#69BE28"],
    "TB":  ["TB", "Tampa Bay Buccaneers", "Buccaneers", "NFC", "South", "#D50A0A", "#FFFFFF", "#E8262A"],
    "TEN": ["TEN", "Tennessee Titans", "Titans", "AFC", "South", "#0C2340", "#4B92DB", "#4B92DB"],
    "WAS": ["WAS", "Washington Commanders", "Commanders", "NFC", "East", "#5A1414", "#FFB612", "#B8433E"],
}
STADIUM_FIX = {"Reliant Stadium": "NRG Stadium"}
FIELDS = ["id", "w", "k", "a", "h", "sa", "sh", "ot", "sp", "tl", "mla", "mlh", "std", "neu", "div", "gt", "st", "clk"]


def log(msg):
    print(msg, file=sys.stderr)


def fetch(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            log(f"retrying {url}: {e}")
            time.sleep(4 * (i + 1))


def source(env, url):
    path = os.environ.get(env)
    if path:
        with open(path, "rb") as fh:
            return fh.read()
    return fetch(url)


def num(s, as_int=False):
    if s in (None, "", "NA"):
        return None
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return int(round(v)) if as_int else (int(v) if v == int(v) else v)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_games(raw):
    games = {}
    for r in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        if r["season"] != str(SEASON) or r["away_team"] not in TEAMS or r["home_team"] not in TEAMS:
            continue
        k = datetime.datetime.strptime(f'{r["gameday"]} {r["gametime"] or "13:00"}', "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(datetime.timezone.utc)
        sa, sh = num(r["away_score"], True), num(r["home_score"], True)
        if sa is None or sh is None:
            sa = sh = None
            st = "pre"
        else:
            st = "post" if NOW >= k + FINAL_AFTER else "in"
        games[r["game_id"]] = {
            "id": r["game_id"], "w": int(r["week"]), "k": iso(k), "a": r["away_team"], "h": r["home_team"],
            "sa": sa, "sh": sh, "ot": 1 if (r["overtime"] == "1" and st == "post") else 0,
            "sp": num(r["spread_line"]), "tl": num(r["total_line"]),
            "mla": num(r["away_moneyline"], True), "mlh": num(r["home_moneyline"], True),
            "std": STADIUM_FIX.get(r["stadium"], r["stadium"]), "neu": 1 if r["location"] == "Neutral" else 0,
            "div": 1 if r["div_game"] == "1" else 0, "gt": r["game_type"], "st": st, "clk": "",
            "_espn": (r.get("espn") or "").strip(),
        }
    return games


def espn_events(gt, week):
    st, wk = (2, week) if gt == "REG" else (3, ESPN_POST_WEEK.get(week))
    if wk is None:
        return []
    path = os.environ.get("SS_ESPN")
    data = json.load(open(path)) if path else json.loads(fetch(ESPN_URL.format(st=st, wk=wk, season=SEASON)))
    events = data.get("events")
    if events is None:   # some responses nest events under the league object
        events = ((data.get("leagues") or [{}])[0] or {}).get("events") or []
    return events


def apply_espn(games):
    """Overlay live scores and final whistles from ESPN for weeks being played around now."""
    by_espn = {g["_espn"]: g for g in games.values() if g["_espn"]}
    active = sorted({(g["gt"], g["w"]) for g in games.values()
                     if abs((parse_iso(g["k"]) - NOW).total_seconds()) < 36 * 3600})
    touched = 0
    for gt, week in active:
        try:
            events = espn_events(gt, week)
        except Exception as e:
            log(f"WARNING: ESPN scoreboard failed for {gt} week {week}: {e}")
            continue
        for ev in events:
            g = by_espn.get(str(ev.get("id")))
            if not g or g["st"] == "post":   # nflverse already has the final; it is the curated source
                continue
            stype = ((ev.get("status") or {}).get("type") or {})
            state, done = stype.get("state"), bool(stype.get("completed"))
            comp = (ev.get("competitions") or [{}])[0] or {}
            score = {c.get("homeAway"): num(c.get("score"), True) for c in comp.get("competitors") or []}
            home, away = score.get("home"), score.get("away")
            if home is None or away is None:
                continue
            detail = str(stype.get("shortDetail") or stype.get("detail") or "")
            if state == "post" and done:
                g.update(sa=away, sh=home, st="post", clk="", ot=1 if "OT" in detail.upper() else 0)
                touched += 1
            elif state == "in":
                g.update(sa=away, sh=home, st="in", clk=detail[:24] or "Live", ot=0)
                touched += 1
    return touched


def load_divranks(raw):
    out = {}
    for r in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        if r["season"] == str(SEASON) and r["team"] in TEAMS:
            out[r["team"]] = [num(r["div_rank"], True) or 0, num(r["seed"], True) or 0]
    return out


def load_leaders(raw, games):
    weeks = {}
    for g in games.values():
        if g["gt"] == "REG":
            weeks.setdefault(g["w"], []).append(g["st"] == "post")
    recent = set(sorted(w for w, d in weeks.items() if all(d))[-3:])
    P = {}
    for r in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        if r.get("season_type") != "REG" or r.get("team") not in TEAMS:
            continue
        p = P.setdefault(r["player_id"], {"n": r["player_display_name"], "pos": r["position"], "t": r["team"], "lw": 0, "s": {}, "hot": []})
        w = int(r["week"])
        if w >= p["lw"]:
            p["lw"], p["t"] = w, r["team"]
        f = lambda c: num(r.get(c)) or 0
        for key, val in (("py", f("passing_yards")), ("ptd", f("passing_tds")), ("ry", f("rushing_yards")),
                         ("rcy", f("receiving_yards")), ("rec", f("receptions")),
                         ("td", f("rushing_tds") + f("receiving_tds") + f("special_teams_tds")),
                         ("sk", f("def_sacks")), ("int", f("def_interceptions"))):
            p["s"][key] = p["s"].get(key, 0) + val
        if w in recent:
            p["hot"].append(f("fantasy_points_ppr"))

    def top(key, n=8):
        out = []
        for p in sorted(P.values(), key=lambda p: -p["s"].get(key, 0))[:n]:
            v = p["s"].get(key, 0)
            if v > 0:
                out.append({"n": p["n"], "t": p["t"], "p": p["pos"], "v": round(v, 1) if v != int(v) else int(v)})
        return out

    hot = sorted((p for p in P.values() if len(p["hot"]) >= 2), key=lambda p: -sum(p["hot"]) / len(p["hot"]))
    lead = {"passYds": top("py"), "passTd": top("ptd"), "rushYds": top("ry"), "recYds": top("rcy"), "rec": top("rec"),
            "tds": top("td"), "sacks": top("sk"), "ints": top("int"), "hotWeeks": sorted(recent),
            "hot": [{"n": p["n"], "t": p["t"], "p": p["pos"], "v": round(sum(p["hot"]) / len(p["hot"]), 1)} for p in hot[:8]]}
    if hot:
        w = hot[0]
        nxt = sorted((g for g in games.values() if g["st"] == "pre" and w["t"] in (g["a"], g["h"])), key=lambda g: g["k"])
        lead["watch"] = {"n": w["n"], "t": w["t"], "p": w["pos"], "v": round(sum(w["hot"]) / len(w["hot"]), 1),
                         "ry": int(w["s"].get("ry", 0)), "rcy": int(w["s"].get("rcy", 0)), "py": int(w["s"].get("py", 0)),
                         "td": int(w["s"].get("td", 0)),
                         "next": ({"opp": nxt[0]["h"] if nxt[0]["a"] == w["t"] else nxt[0]["a"], "home": nxt[0]["h"] == w["t"],
                                   "k": nxt[0]["k"]} if nxt else None)}
    return lead


def main():
    previous = {}
    try:
        with open(OUT) as fh:
            previous = json.load(fh)
    except Exception:
        pass

    try:
        games = load_games(source("SS_GAMES", NFLVERSE + "games.csv"))
    except Exception as e:
        sys.exit(f"games.csv unavailable, keeping the old data.json: {e}")
    if len(games) < 200:
        sys.exit(f"only {len(games)} games parsed, keeping the old data.json")

    live = apply_espn(games)

    # never let a hiccup in either feed take a final score away
    kept = 0
    prev_fields = previous.get("fields") or FIELDS
    for row in previous.get("games") or []:
        old = dict(zip(prev_fields, row))
        g = games.get(old.get("id"))
        final_before = old.get("st") == "post" or (old.get("st") is None and old.get("sa") is not None)
        if g and final_before and g["st"] != "post" and old.get("sa") is not None and old.get("sh") is not None:
            g.update(sa=old["sa"], sh=old["sh"], ot=old.get("ot") or 0, st="post", clk="")
            kept += 1

    try:
        div = load_divranks(source("SS_STANDINGS", NFLVERSE + "standings.csv"))
    except Exception as e:
        log(f"WARNING: standings unavailable, keeping previous: {e}")
        div = previous.get("div") or {}
    try:
        leaders = load_leaders(source("SS_STATS", STATS_URL), games)
    except Exception as e:
        log(f"WARNING: player stats unavailable, keeping previous: {e}")
        leaders = previous.get("leaders") or {}

    rows = [[g[f] for f in FIELDS] for g in sorted(games.values(), key=lambda g: (g["k"], g["id"]))]
    out = {"updated": iso(NOW), "season": SEASON, "teams": TEAMS, "div": div, "leaders": leaders,
           "fields": FIELDS, "games": rows}
    same = lambda d: json.dumps({k: v for k, v in d.items() if k != "updated"}, sort_keys=True)
    if previous and same(previous) == same(out):
        out["updated"] = previous.get("updated", out["updated"])   # nothing changed: no commit needed
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    finals = sum(1 for g in games.values() if g["st"] == "post")
    in_play = sum(1 for g in games.values() if g["st"] == "in")
    print(f"Wrote {OUT}: {len(games)} games, {finals} final, {in_play} in progress, "
          f"{live} touched by ESPN, {kept} finals carried over")


if __name__ == "__main__":
    main()
