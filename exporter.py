from pathlib import Path
from datetime import datetime
import json
from database import connect, get_setting

BASE_DIR = Path(__file__).resolve().parent
OUT_FILE = BASE_DIR / "docs" / "data" / "fantacalcio.json"

def _standings(conn, season_id):
    teams = conn.execute(
        """
        SELECT t.id, t.name, COALESCE(NULLIF(st.logo_path,''), t.logo_path) AS logo_path, st.coach_name
        FROM season_teams st
        JOIN teams t ON t.id = st.team_id
        WHERE st.season_id=?
        ORDER BY t.name COLLATE NOCASE
        """,
        (season_id,),
    ).fetchall()

    table = {
        t["id"]: {
            "team_id": t["id"], "name": t["name"], "logo": t["logo_path"],
            "coach": t["coach_name"], "played": 0, "wins": 0, "draws": 0,
            "losses": 0, "gf": 0, "ga": 0, "gd": 0, "points": 0
        }
        for t in teams
    }

    matches = conn.execute(
        "SELECT * FROM matches WHERE season_id=? ORDER BY round_no, id", (season_id,)
    ).fetchall()

    for m in matches:
        h = table.get(m["home_team_id"])
        a = table.get(m["away_team_id"])
        if not h or not a:
            continue
        hs, aas = m["home_score"], m["away_score"]
        h["played"] += 1
        a["played"] += 1
        h["gf"] += hs
        h["ga"] += aas
        a["gf"] += aas
        a["ga"] += hs
        if hs > aas:
            h["wins"] += 1
            a["losses"] += 1
            h["points"] += 3
        elif hs < aas:
            a["wins"] += 1
            h["losses"] += 1
            a["points"] += 3
        else:
            h["draws"] += 1
            a["draws"] += 1
            h["points"] += 1
            a["points"] += 1

    result = list(table.values())
    for x in result:
        x["gd"] = x["gf"] - x["ga"]

    result.sort(key=lambda x: (-x["points"], -x["gf"], -x["gd"], x["name"].lower()))
    for pos, x in enumerate(result, 1):
        x["position"] = pos
    return result

def build_data():
    with connect() as conn:
        league_name = get_setting("league_name", "La Mia Lega")
        current_season_id = get_setting("current_season_id", "")
        try:
            current_season_id = int(current_season_id)
        except (TypeError, ValueError):
            current_season_id = None

        seasons_rows = conn.execute(
            "SELECT * FROM seasons ORDER BY id DESC"
        ).fetchall()

        seasons = []
        for s in seasons_rows:
            sid = s["id"]
            season_teams = conn.execute(
                """
                SELECT t.id, t.name, COALESCE(NULLIF(st.logo_path,''), t.logo_path) AS logo_path, st.coach_name
                FROM season_teams st
                JOIN teams t ON t.id=st.team_id
                WHERE st.season_id=?
                ORDER BY t.name COLLATE NOCASE
                """,
                (sid,),
            ).fetchall()

            teams = []
            for t in season_teams:
                roster_rows = conn.execute(
                    """
                    SELECT p.id, p.name, r.role,
                           COALESCE(SUM(pms.goals),0) AS goals,
                           COALESCE(SUM(pms.assists),0) AS assists
                    FROM rosters r
                    JOIN players p ON p.id=r.player_id
                    LEFT JOIN player_match_stats pms
                      ON pms.player_id=p.id
                     AND pms.team_id=r.team_id
                     AND pms.match_id IN (SELECT id FROM matches WHERE season_id=?)
                    WHERE r.season_id=? AND r.team_id=?
                    GROUP BY p.id, p.name, r.role
                    ORDER BY r.role, p.name COLLATE NOCASE
                    """,
                    (sid, sid, t["id"]),
                ).fetchall()
                teams.append({
                    "id": t["id"],
                    "name": t["name"],
                    "logo": t["logo_path"],
                    "coach": t["coach_name"],
                    "roster": [dict(r) for r in roster_rows],
                })

            match_rows = conn.execute(
                """
                SELECT m.*, ht.name AS home_name, at.name AS away_name,
                       ht.logo_path AS home_logo, at.logo_path AS away_logo
                FROM matches m
                JOIN teams ht ON ht.id=m.home_team_id
                JOIN teams at ON at.id=m.away_team_id
                WHERE m.season_id=?
                ORDER BY m.round_no, m.id
                """,
                (sid,),
            ).fetchall()

            matches = []
            for m in match_rows:
                stats = conn.execute(
                    """
                    SELECT pms.*, p.name AS player_name, t.name AS team_name
                    FROM player_match_stats pms
                    JOIN players p ON p.id=pms.player_id
                    JOIN teams t ON t.id=pms.team_id
                    WHERE pms.match_id=?
                    ORDER BY t.name, p.name
                    """,
                    (m["id"],),
                ).fetchall()
                md = dict(m)
                md["stats"] = [dict(x) for x in stats]
                matches.append(md)

            champion = conn.execute(
                """
                SELECT c.*, t.name AS team_name,
                       COALESCE(NULLIF(st.logo_path,''), t.logo_path) AS logo
                FROM champions c
                JOIN teams t ON t.id=c.team_id
                LEFT JOIN season_teams st ON st.season_id=c.season_id AND st.team_id=c.team_id
                WHERE c.season_id=?
                """,
                (sid,),
            ).fetchone()

            seasons.append({
                "id": sid,
                "name": s["name"],
                "archive_mode": s["archive_mode"] if "archive_mode" in s.keys() else "full",
                "teams": teams,
                "matches": matches,
                "standings": _standings(conn, sid),
                "champion": dict(champion) if champion else None,
            })

        palmares_rows = conn.execute(
            """
            SELECT t.id AS team_id, t.name, t.logo_path AS logo,
                   COUNT(*) AS titles
            FROM champions c
            JOIN teams t ON t.id=c.team_id
            GROUP BY t.id, t.name, t.logo_path
            ORDER BY titles DESC, t.name COLLATE NOCASE
            """
        ).fetchall()

        champions_history = conn.execute(
            """
            SELECT s.id AS season_id, s.name AS season_name,
                   t.id AS team_id, t.name AS team_name,
                   COALESCE(NULLIF(st.logo_path,''), t.logo_path) AS logo, c.coach_name
            FROM champions c
            JOIN seasons s ON s.id=c.season_id
            JOIN teams t ON t.id=c.team_id
            LEFT JOIN season_teams st ON st.season_id=c.season_id AND st.team_id=c.team_id
            ORDER BY s.id DESC
            """
        ).fetchall()

    return {
        "league_name": league_name,
        "current_season_id": current_season_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seasons": seasons,
        "champions_history": [dict(x) for x in champions_history],
        "palmares": [dict(x) for x in palmares_rows],
    }

def export_site_data():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = build_data()
    OUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return OUT_FILE
