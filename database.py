from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.sqlite3"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    archive_mode TEXT NOT NULL DEFAULT 'full',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    logo_path TEXT NOT NULL DEFAULT 'assets/logos/default-logo.svg'
);

CREATE TABLE IF NOT EXISTS season_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    coach_name TEXT NOT NULL DEFAULT '',
    logo_path TEXT NOT NULL DEFAULT '',
    UNIQUE(season_id, team_id),
    FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS rosters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    UNIQUE(season_id, player_id),
    FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    round_no INTEGER NOT NULL,
    match_date TEXT NOT NULL DEFAULT '',
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    CHECK(home_team_id <> away_team_id),
    FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    FOREIGN KEY(home_team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY(away_team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS player_match_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    goals INTEGER NOT NULL DEFAULT 0 CHECK(goals >= 0),
    assists INTEGER NOT NULL DEFAULT 0 CHECK(assists >= 0),
    UNIQUE(match_id, player_id),
    FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS champions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL UNIQUE,
    team_id INTEGER NOT NULL,
    coach_name TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);
"""

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _column_exists(conn, table, column):
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())

def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)

        # Migrazioni automatiche per chi aggiorna una versione già usata.
        if not _column_exists(conn, "seasons", "archive_mode"):
            conn.execute("ALTER TABLE seasons ADD COLUMN archive_mode TEXT NOT NULL DEFAULT 'full'")
        if not _column_exists(conn, "season_teams", "logo_path"):
            conn.execute("ALTER TABLE season_teams ADD COLUMN logo_path TEXT NOT NULL DEFAULT ''")

        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('league_name', 'La Mia Lega')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('current_season_id', '')"
        )

def get_setting(key, default=""):
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

def rows(query, params=()):
    with connect() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]

def row(query, params=()):
    with connect() as conn:
        result = conn.execute(query, params).fetchone()
        return dict(result) if result else None
