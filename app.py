from pathlib import Path
import shutil
import subprocess
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from database import init_db, connect, get_setting, set_setting
from exporter import export_site_data
from backup_manager import create_rotating_backup, backup_list, restore_backup
from publisher import publish_to_github, PublishError

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
LOGO_DIR = DOCS_DIR / "assets" / "logos"

ROLES = ["P", "D", "C", "A"]

class FantacalcioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestione Fantacalcio")
        self.geometry("1120x760")
        self.minsize(980, 680)
        init_db()

        self.preview_process = None
        self._build_header()
        self._build_tabs()
        self.refresh_all()

    # ---------- UI generale ----------
    def _build_header(self):
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")

        ttk.Label(
            bar, text="GESTIONE FANTACALCIO",
            font=("Arial", 18, "bold")
        ).pack(side="left")

        ttk.Button(
            bar, text="🌐 Anteprima locale", command=self.preview_site
        ).pack(side="right", padx=(8, 0))

        ttk.Button(
            bar, text="💾 SALVA E PUBBLICA", command=self.save_and_publish
        ).pack(side="right")

    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tab_settings = ttk.Frame(self.nb, padding=12)
        self.tab_seasons = ttk.Frame(self.nb, padding=12)
        self.tab_teams = ttk.Frame(self.nb, padding=12)
        self.tab_rosters = ttk.Frame(self.nb, padding=12)
        self.tab_matches = ttk.Frame(self.nb, padding=12)
        self.tab_stats = ttk.Frame(self.nb, padding=12)
        self.tab_champions = ttk.Frame(self.nb, padding=12)
        self.tab_backup = ttk.Frame(self.nb, padding=12)

        for frame, title in [
            (self.tab_settings, "Configurazione"),
            (self.tab_seasons, "Stagioni"),
            (self.tab_teams, "Squadre"),
            (self.tab_rosters, "Rose"),
            (self.tab_matches, "Partite"),
            (self.tab_stats, "Gol / Assist"),
            (self.tab_champions, "Albo d'Oro"),
            (self.tab_backup, "Backup"),
        ]:
            self.nb.add(frame, text=title)

        self._settings_tab()
        self._seasons_tab()
        self._teams_tab()
        self._rosters_tab()
        self._matches_tab()
        self._stats_tab()
        self._champions_tab()
        self._backup_tab()

    def _tree(self, parent, columns, headings, widths=None, height=15):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
        for i, col in enumerate(columns):
            tree.heading(col, text=headings[i])
            tree.column(col, width=(widths[i] if widths else 130), anchor="center")
        tree.pack(fill="both", expand=True, pady=8)
        return tree

    def _combo(self, parent, variable, width=28):
        return ttk.Combobox(parent, textvariable=variable, state="readonly", width=width)

    # ---------- Configurazione ----------
    def _settings_tab(self):
        f = self.tab_settings
        ttk.Label(f, text="Nome della lega", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.league_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.league_var, width=45).grid(row=1, column=0, sticky="w", pady=(4, 18))

        ttk.Label(f, text="Stagione corrente", font=("Arial", 11, "bold")).grid(row=2, column=0, sticky="w")
        self.current_season_var = tk.StringVar()
        self.current_season_combo = self._combo(f, self.current_season_var, 42)
        self.current_season_combo.grid(row=3, column=0, sticky="w", pady=(4, 18))

        ttk.Button(f, text="Salva configurazione", command=self.save_settings).grid(row=4, column=0, sticky="w")

        ttk.Label(
            f,
            text=(
                "Questi dati vengono usati nel sito pubblico. La stagione corrente è quella "
                "mostrata automaticamente nella home."
            ),
            wraplength=780
        ).grid(row=5, column=0, sticky="w", pady=20)

    def save_settings(self):
        name = self.league_var.get().strip() or "La Mia Lega"
        set_setting("league_name", name)
        sid = self._id_from_combo(self.current_season_var.get())
        set_setting("current_season_id", sid or "")
        export_site_data()
        messagebox.showinfo("Salvato", "Configurazione salvata.")

    # ---------- Stagioni ----------
    def _seasons_tab(self):
        f = self.tab_seasons
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Nuova stagione (es. 2026/2027)").pack(side="left")
        self.new_season_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.new_season_var, width=20).pack(side="left", padx=8)
        ttk.Button(top, text="Aggiungi", command=self.add_season).pack(side="left")
        ttk.Button(top, text="Elimina selezionata", command=self.delete_season).pack(side="right")

        self.seasons_tree = self._tree(
            f, ("id", "name"), ("ID", "Stagione"), (80, 240)
        )

    def add_season(self):
        name = self.new_season_var.get().strip()
        if not name:
            return messagebox.showwarning("Dato mancante", "Inserisci il nome della stagione.")
        try:
            with connect() as conn:
                cur = conn.execute("INSERT INTO seasons(name, archive_mode) VALUES(?, 'full')", (name,))
                sid = cur.lastrowid
            if not get_setting("current_season_id"):
                set_setting("current_season_id", sid)
            self.new_season_var.set("")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def delete_season(self):
        sel = self.seasons_tree.selection()
        if not sel:
            return
        item = self.seasons_tree.item(sel[0], "values")
        sid, name = int(item[0]), item[1]
        if not messagebox.askyesno(
            "Conferma",
            f"Eliminare la stagione {name}?\nVerranno eliminati anche rose, partite e statistiche di quella stagione."
        ):
            return
        with connect() as conn:
            conn.execute("DELETE FROM seasons WHERE id=?", (sid,))
        if str(sid) == get_setting("current_season_id"):
            set_setting("current_season_id", "")
        self.refresh_all()

    # ---------- Squadre ----------
    def _teams_tab(self):
        f = self.tab_teams
        form = ttk.LabelFrame(f, text="Aggiungi / assegna squadra a una stagione", padding=10)
        form.pack(fill="x")

        self.team_season_var = tk.StringVar()
        self.team_name_var = tk.StringVar()
        self.team_coach_var = tk.StringVar()
        self.team_logo_var = tk.StringVar()

        ttk.Label(form, text="Stagione").grid(row=0, column=0, sticky="w")
        self.team_season_combo = self._combo(form, self.team_season_var)
        self.team_season_combo.grid(row=1, column=0, padx=(0, 10))
        self.team_season_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_teams())

        ttk.Label(form, text="Nome squadra").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.team_name_var, width=25).grid(row=1, column=1, padx=(0, 10))

        ttk.Label(form, text="Fantallenatore").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.team_coach_var, width=25).grid(row=1, column=2, padx=(0, 10))

        ttk.Label(form, text="Stemma").grid(row=0, column=3, sticky="w")
        ttk.Entry(form, textvariable=self.team_logo_var, width=28).grid(row=1, column=3)
        ttk.Button(form, text="Scegli...", command=self.choose_logo).grid(row=1, column=4, padx=6)
        ttk.Button(form, text="Salva squadra", command=self.add_team).grid(row=1, column=5, padx=6)
        ttk.Button(form, text="Carica selezionata per modifica", command=self.load_selected_team).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10,0))

        ttk.Button(f, text="Rimuovi dalla stagione", command=self.remove_team_from_season).pack(anchor="e", pady=(8, 0))
        self.teams_tree = self._tree(
            f,
            ("season", "team_id", "team", "coach", "logo"),
            ("Stagione", "ID", "Squadra", "Fantallenatore", "Stemma"),
            (130, 60, 210, 210, 300),
        )

    def choose_logo(self):
        path = filedialog.askopenfilename(
            title="Scegli lo stemma",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.webp *.gif *.svg"), ("Tutti i file", "*.*")]
        )
        if path:
            self.team_logo_var.set(path)

    def add_team(self):
        sid = self._id_from_combo(self.team_season_var.get())
        name = self.team_name_var.get().strip()
        coach = self.team_coach_var.get().strip()
        if not sid or not name:
            return messagebox.showwarning("Dati mancanti", "Seleziona una stagione e inserisci il nome della squadra.")
        try:
            with connect() as conn:
                season_check = conn.execute(
                    "SELECT archive_mode FROM seasons WHERE id=?", (sid,)
                ).fetchone()
                if not season_check or season_check["archive_mode"] != "full":
                    return messagebox.showwarning(
                        "Stagione non utilizzabile",
                        "Le stagioni create solo per l'Albo d'Oro non possono ricevere "
                        "squadre, rose o partite. Crea/seleziona una stagione completa."
                    )
                t = conn.execute("SELECT id, logo_path FROM teams WHERE name=? COLLATE NOCASE", (name,)).fetchone()
                if t:
                    tid = t["id"]
                else:
                    cur = conn.execute("INSERT INTO teams(name) VALUES(?)", (name,))
                    tid = cur.lastrowid

                rel = ""
                logo_src = self.team_logo_var.get().strip()
                if logo_src:
                    src = Path(logo_src)
                    ext = src.suffix.lower() or ".png"
                    dest = LOGO_DIR / f"team_{sid}_{tid}{ext}"
                    LOGO_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    rel = dest.relative_to(DOCS_DIR).as_posix()
                    # Manteniamo anche un logo generale di riserva.
                    conn.execute("UPDATE teams SET logo_path=? WHERE id=?", (rel, tid))

                conn.execute(
                    """
                    INSERT INTO season_teams(season_id, team_id, coach_name, logo_path)
                    VALUES(?,?,?,?)
                    ON CONFLICT(season_id,team_id) DO UPDATE SET
                        coach_name=excluded.coach_name,
                        logo_path=CASE WHEN excluded.logo_path <> '' THEN excluded.logo_path ELSE season_teams.logo_path END
                    """,
                    (sid, tid, coach, rel),
                )
            self.team_name_var.set("")
            self.team_coach_var.set("")
            self.team_logo_var.set("")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def load_selected_team(self):
        sel = self.teams_tree.selection()
        if not sel:
            return messagebox.showwarning("Selezione mancante", "Seleziona una squadra dalla tabella.")
        vals = self.teams_tree.item(sel[0], "values")
        season_name, team_name, coach = vals[0], vals[2], vals[3]
        sid = self._season_id_by_name(season_name)
        if not sid:
            return
        self.team_season_var.set(self._combo_text(sid, season_name))
        self.team_name_var.set(team_name)
        self.team_coach_var.set(coach)
        self.team_logo_var.set("")
        messagebox.showinfo(
            "Squadra caricata",
            "Modifica fantallenatore e/o scegli un nuovo stemma, poi premi 'Salva squadra'."
        )

    def remove_team_from_season(self):
        sel = self.teams_tree.selection()
        if not sel:
            return
        vals = self.teams_tree.item(sel[0], "values")
        season_name, tid = vals[0], int(vals[1])
        sid = self._season_id_by_name(season_name)
        if not sid:
            return
        if not messagebox.askyesno("Conferma", f"Rimuovere {vals[2]} dalla stagione {season_name}?"):
            return
        try:
            with connect() as conn:
                conn.execute("DELETE FROM season_teams WHERE season_id=? AND team_id=?", (sid, tid))
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    # ---------- Rose ----------
    def _rosters_tab(self):
        f = self.tab_rosters
        form = ttk.LabelFrame(f, text="Aggiungi giocatore alla rosa", padding=10)
        form.pack(fill="x")

        self.roster_season_var = tk.StringVar()
        self.roster_team_var = tk.StringVar()
        self.player_name_var = tk.StringVar()
        self.player_role_var = tk.StringVar(value="P")

        ttk.Label(form, text="Stagione").grid(row=0, column=0, sticky="w")
        self.roster_season_combo = self._combo(form, self.roster_season_var)
        self.roster_season_combo.grid(row=1, column=0, padx=(0,10))
        self.roster_season_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_team_combos())

        ttk.Label(form, text="Squadra").grid(row=0, column=1, sticky="w")
        self.roster_team_combo = self._combo(form, self.roster_team_var)
        self.roster_team_combo.grid(row=1, column=1, padx=(0,10))

        ttk.Label(form, text="Giocatore").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.player_name_var, width=25).grid(row=1, column=2, padx=(0,10))

        ttk.Label(form, text="Ruolo").grid(row=0, column=3, sticky="w")
        ttk.Combobox(form, textvariable=self.player_role_var, values=ROLES, state="readonly", width=6).grid(row=1, column=3, padx=(0,10))

        ttk.Button(form, text="Aggiungi", command=self.add_roster_player).grid(row=1, column=4)
        ttk.Button(f, text="Rimuovi giocatore", command=self.remove_roster_player).pack(anchor="e", pady=(8,0))

        self.roster_tree = self._tree(
            f, ("season", "team", "player_id", "player", "role"),
            ("Stagione", "Squadra", "ID", "Giocatore", "Ruolo"),
            (130, 220, 60, 240, 70)
        )

    def add_roster_player(self):
        sid = self._id_from_combo(self.roster_season_var.get())
        tid = self._id_from_combo(self.roster_team_var.get())
        name = self.player_name_var.get().strip()
        role = self.player_role_var.get().strip()
        if not sid or not tid or not name:
            return messagebox.showwarning("Dati mancanti", "Compila stagione, squadra e giocatore.")
        try:
            with connect() as conn:
                p = conn.execute("SELECT id FROM players WHERE name=? COLLATE NOCASE", (name,)).fetchone()
                if p:
                    pid = p["id"]
                else:
                    pid = conn.execute("INSERT INTO players(name) VALUES(?)", (name,)).lastrowid
                conn.execute(
                    """
                    INSERT INTO rosters(season_id,team_id,player_id,role)
                    VALUES(?,?,?,?)
                    ON CONFLICT(season_id,player_id)
                    DO UPDATE SET team_id=excluded.team_id, role=excluded.role
                    """,
                    (sid, tid, pid, role),
                )
            self.player_name_var.set("")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def remove_roster_player(self):
        sel = self.roster_tree.selection()
        if not sel:
            return
        vals = self.roster_tree.item(sel[0], "values")
        sid = self._season_id_by_name(vals[0])
        pid = int(vals[2])
        with connect() as conn:
            conn.execute("DELETE FROM rosters WHERE season_id=? AND player_id=?", (sid, pid))
        self.refresh_all()

    # ---------- Partite ----------
    def _matches_tab(self):
        f = self.tab_matches
        form = ttk.LabelFrame(f, text="Inserisci partita", padding=10)
        form.pack(fill="x")

        self.match_season_var = tk.StringVar()
        self.match_round_var = tk.StringVar()
        self.match_date_var = tk.StringVar()
        self.match_home_var = tk.StringVar()
        self.match_away_var = tk.StringVar()
        self.match_hs_var = tk.StringVar(value="0")
        self.match_as_var = tk.StringVar(value="0")

        labels = ["Stagione", "Giornata", "Data (opz.)", "Casa", "Trasferta", "Gol casa", "Gol trasferta"]
        vars_ = [self.match_season_var, self.match_round_var, self.match_date_var, self.match_home_var, self.match_away_var, self.match_hs_var, self.match_as_var]
        for i, lab in enumerate(labels):
            ttk.Label(form, text=lab).grid(row=0, column=i, sticky="w", padx=3)
            if i == 0:
                w = self._combo(form, vars_[i], 18)
                self.match_season_combo = w
                w.bind("<<ComboboxSelected>>", lambda e: self.refresh_team_combos())
            elif i in (3,4):
                w = self._combo(form, vars_[i], 18)
                if i == 3: self.match_home_combo = w
                else: self.match_away_combo = w
            else:
                w = ttk.Entry(form, textvariable=vars_[i], width=12)
            w.grid(row=1, column=i, padx=3)

        ttk.Button(form, text="Aggiungi partita", command=self.add_match).grid(row=1, column=7, padx=8)
        ttk.Button(f, text="Elimina partita", command=self.delete_match).pack(anchor="e", pady=(8,0))

        self.matches_tree = self._tree(
            f,
            ("id","season","round","date","home","score","away"),
            ("ID","Stagione","Giornata","Data","Casa","Ris.","Trasferta"),
            (60,120,80,110,190,80,190)
        )

    def add_match(self):
        sid = self._id_from_combo(self.match_season_var.get())
        hid = self._id_from_combo(self.match_home_var.get())
        aid = self._id_from_combo(self.match_away_var.get())
        try:
            rnd = int(self.match_round_var.get())
            hs = int(self.match_hs_var.get())
            aas = int(self.match_as_var.get())
            if rnd < 1 or hs < 0 or aas < 0:
                raise ValueError
        except ValueError:
            return messagebox.showwarning("Valori non validi", "Giornata e risultati devono essere numeri interi validi.")
        if not sid or not hid or not aid or hid == aid:
            return messagebox.showwarning("Dati mancanti", "Seleziona stagione e due squadre diverse.")
        try:
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO matches(season_id,round_no,match_date,home_team_id,away_team_id,home_score,away_score)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (sid, rnd, self.match_date_var.get().strip(), hid, aid, hs, aas),
                )
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def delete_match(self):
        sel = self.matches_tree.selection()
        if not sel:
            return
        mid = int(self.matches_tree.item(sel[0], "values")[0])
        if messagebox.askyesno("Conferma", "Eliminare la partita e le sue statistiche giocatori?"):
            with connect() as conn:
                conn.execute("DELETE FROM matches WHERE id=?", (mid,))
            self.refresh_all()

    # ---------- Gol / Assist ----------
    def _stats_tab(self):
        f = self.tab_stats
        form = ttk.LabelFrame(f, text="Statistiche giocatore nella partita", padding=10)
        form.pack(fill="x")

        self.stat_season_var = tk.StringVar()
        self.stat_match_var = tk.StringVar()
        self.stat_team_var = tk.StringVar()
        self.stat_player_var = tk.StringVar()
        self.stat_goals_var = tk.StringVar(value="0")
        self.stat_assists_var = tk.StringVar(value="0")

        ttk.Label(form, text="Stagione").grid(row=0,column=0,sticky="w")
        self.stat_season_combo = self._combo(form,self.stat_season_var,18)
        self.stat_season_combo.grid(row=1,column=0,padx=3)
        self.stat_season_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_stat_matches())

        ttk.Label(form, text="Partita").grid(row=0,column=1,sticky="w")
        self.stat_match_combo = self._combo(form,self.stat_match_var,42)
        self.stat_match_combo.grid(row=1,column=1,padx=3)
        self.stat_match_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_stat_teams())

        ttk.Label(form, text="Squadra").grid(row=0,column=2,sticky="w")
        self.stat_team_combo = self._combo(form,self.stat_team_var,20)
        self.stat_team_combo.grid(row=1,column=2,padx=3)
        self.stat_team_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_stat_players())

        ttk.Label(form, text="Giocatore").grid(row=0,column=3,sticky="w")
        self.stat_player_combo = self._combo(form,self.stat_player_var,24)
        self.stat_player_combo.grid(row=1,column=3,padx=3)

        ttk.Label(form, text="Gol").grid(row=0,column=4,sticky="w")
        ttk.Entry(form,textvariable=self.stat_goals_var,width=7).grid(row=1,column=4,padx=3)

        ttk.Label(form, text="Assist").grid(row=0,column=5,sticky="w")
        ttk.Entry(form,textvariable=self.stat_assists_var,width=7).grid(row=1,column=5,padx=3)

        ttk.Button(form,text="Salva / aggiorna",command=self.save_player_stat).grid(row=1,column=6,padx=8)
        ttk.Button(f,text="Elimina statistica",command=self.delete_player_stat).pack(anchor="e",pady=(8,0))

        self.stats_tree = self._tree(
            f, ("id","season","round","match","team","player","goals","assists"),
            ("ID","Stagione","G.","Partita","Squadra","Giocatore","Gol","Assist"),
            (55,110,55,290,170,190,60,60)
        )

    def save_player_stat(self):
        mid = self._id_from_combo(self.stat_match_var.get())
        tid = self._id_from_combo(self.stat_team_var.get())
        pid = self._id_from_combo(self.stat_player_var.get())
        try:
            goals = int(self.stat_goals_var.get())
            assists = int(self.stat_assists_var.get())
            if goals < 0 or assists < 0:
                raise ValueError
        except ValueError:
            return messagebox.showwarning("Valori non validi","Gol e assist devono essere numeri interi >= 0.")
        if not mid or not tid or not pid:
            return messagebox.showwarning("Dati mancanti","Seleziona partita, squadra e giocatore.")
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO player_match_stats(match_id,team_id,player_id,goals,assists)
                VALUES(?,?,?,?,?)
                ON CONFLICT(match_id,player_id)
                DO UPDATE SET team_id=excluded.team_id, goals=excluded.goals, assists=excluded.assists
                """,
                (mid,tid,pid,goals,assists)
            )
        self.refresh_all()

    def delete_player_stat(self):
        sel = self.stats_tree.selection()
        if not sel:
            return
        sid = int(self.stats_tree.item(sel[0],"values")[0])
        with connect() as conn:
            conn.execute("DELETE FROM player_match_stats WHERE id=?", (sid,))
        self.refresh_all()

    # ---------- Campioni ----------
    def _champions_tab(self):
        f = self.tab_champions
        form = ttk.LabelFrame(f, text="Vincitore della stagione", padding=10)
        form.pack(fill="x")

        self.champ_season_var = tk.StringVar()
        self.champ_team_var = tk.StringVar()
        self.champ_coach_var = tk.StringVar()

        ttk.Label(form,text="Stagione").grid(row=0,column=0,sticky="w")
        self.champ_season_combo = self._combo(form,self.champ_season_var)
        self.champ_season_combo.grid(row=1,column=0,padx=5)
        self.champ_season_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_team_combos())

        ttk.Label(form,text="Squadra vincitrice").grid(row=0,column=1,sticky="w")
        self.champ_team_combo = self._combo(form,self.champ_team_var)
        self.champ_team_combo.grid(row=1,column=1,padx=5)
        self.champ_team_combo.bind("<<ComboboxSelected>>", lambda e: self.fill_champion_coach())

        ttk.Label(form,text="Fantallenatore").grid(row=0,column=2,sticky="w")
        ttk.Entry(form,textvariable=self.champ_coach_var,width=28).grid(row=1,column=2,padx=5)

        ttk.Button(form,text="Salva vincitore",command=self.save_champion).grid(row=1,column=3,padx=8)

        self.champ_tree = self._tree(
            f, ("season","team","coach"), ("Stagione","Squadra vincitrice","Fantallenatore"),
            (180,280,260)
        )

        hist = ttk.LabelFrame(
            f,
            text="Aggiungi direttamente un vecchio vincitore (senza partite/rosa/classifica)",
            padding=10
        )
        hist.pack(fill="x", pady=(18,0))

        self.hist_season_var = tk.StringVar()
        self.hist_team_var = tk.StringVar()
        self.hist_coach_var = tk.StringVar()
        self.hist_logo_var = tk.StringVar()

        ttk.Label(hist, text="Stagione (es. 2021/2022)").grid(row=0,column=0,sticky="w")
        ttk.Entry(hist,textvariable=self.hist_season_var,width=20).grid(row=1,column=0,padx=(0,8))
        ttk.Label(hist,text="Squadra vincitrice").grid(row=0,column=1,sticky="w")
        ttk.Entry(hist,textvariable=self.hist_team_var,width=25).grid(row=1,column=1,padx=(0,8))
        ttk.Label(hist,text="Fantallenatore").grid(row=0,column=2,sticky="w")
        ttk.Entry(hist,textvariable=self.hist_coach_var,width=25).grid(row=1,column=2,padx=(0,8))
        ttk.Label(hist,text="Stemma (facoltativo)").grid(row=0,column=3,sticky="w")
        ttk.Entry(hist,textvariable=self.hist_logo_var,width=28).grid(row=1,column=3)
        ttk.Button(hist,text="Scegli...",command=self.choose_historical_logo).grid(row=1,column=4,padx=5)
        ttk.Button(hist,text="Aggiungi all'Albo d'Oro",command=self.add_historical_champion).grid(row=1,column=5,padx=5)

    def choose_historical_logo(self):
        path = filedialog.askopenfilename(
            title="Scegli lo stemma storico",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.webp *.gif *.svg"), ("Tutti i file", "*.*")]
        )
        if path:
            self.hist_logo_var.set(path)

    def add_historical_champion(self):
        season_name = self.hist_season_var.get().strip()
        team_name = self.hist_team_var.get().strip()
        coach = self.hist_coach_var.get().strip()
        logo_src = self.hist_logo_var.get().strip()
        if not season_name or not team_name:
            return messagebox.showwarning("Dati mancanti", "Inserisci almeno stagione e squadra vincitrice.")
        try:
            with connect() as conn:
                sr = conn.execute("SELECT id, archive_mode FROM seasons WHERE name=?", (season_name,)).fetchone()
                if sr:
                    sid = sr["id"]
                    has_matches = conn.execute("SELECT 1 FROM matches WHERE season_id=? LIMIT 1", (sid,)).fetchone()
                    if not has_matches:
                        conn.execute("UPDATE seasons SET archive_mode='honor_only' WHERE id=?", (sid,))
                else:
                    sid = conn.execute(
                        "INSERT INTO seasons(name, archive_mode) VALUES(?, 'honor_only')",
                        (season_name,)
                    ).lastrowid

                tr = conn.execute("SELECT id FROM teams WHERE name=? COLLATE NOCASE", (team_name,)).fetchone()
                if tr:
                    tid = tr["id"]
                else:
                    tid = conn.execute("INSERT INTO teams(name) VALUES(?)", (team_name,)).lastrowid

                rel = ""
                if logo_src:
                    src = Path(logo_src)
                    ext = src.suffix.lower() or ".png"
                    dest = LOGO_DIR / f"historical_{sid}_{tid}{ext}"
                    LOGO_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    rel = dest.relative_to(DOCS_DIR).as_posix()

                conn.execute(
                    """
                    INSERT INTO season_teams(season_id,team_id,coach_name,logo_path)
                    VALUES(?,?,?,?)
                    ON CONFLICT(season_id,team_id) DO UPDATE SET
                        coach_name=excluded.coach_name,
                        logo_path=CASE WHEN excluded.logo_path <> '' THEN excluded.logo_path ELSE season_teams.logo_path END
                    """,
                    (sid,tid,coach,rel)
                )
                conn.execute(
                    """
                    INSERT INTO champions(season_id,team_id,coach_name)
                    VALUES(?,?,?)
                    ON CONFLICT(season_id) DO UPDATE SET
                        team_id=excluded.team_id, coach_name=excluded.coach_name
                    """,
                    (sid,tid,coach)
                )

            self.hist_season_var.set("")
            self.hist_team_var.set("")
            self.hist_coach_var.set("")
            self.hist_logo_var.set("")
            self.refresh_all()
            messagebox.showinfo(
                "Albo d'Oro aggiornato",
                "Vincitore storico aggiunto. Verrà conteggiato nel Palmarès senza creare una pagina archivio vuota."
            )
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def fill_champion_coach(self):
        sid = self._id_from_combo(self.champ_season_var.get())
        tid = self._id_from_combo(self.champ_team_var.get())
        if not sid or not tid:
            return
        with connect() as conn:
            r = conn.execute(
                "SELECT coach_name FROM season_teams WHERE season_id=? AND team_id=?",
                (sid,tid)
            ).fetchone()
        self.champ_coach_var.set(r["coach_name"] if r else "")

    def save_champion(self):
        sid = self._id_from_combo(self.champ_season_var.get())
        tid = self._id_from_combo(self.champ_team_var.get())
        coach = self.champ_coach_var.get().strip()
        if not sid or not tid:
            return messagebox.showwarning("Dati mancanti","Seleziona stagione e squadra vincitrice.")
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO champions(season_id,team_id,coach_name)
                VALUES(?,?,?)
                ON CONFLICT(season_id)
                DO UPDATE SET team_id=excluded.team_id, coach_name=excluded.coach_name
                """,(sid,tid,coach)
            )
        self.refresh_all()

    # ---------- Backup ----------
    def _backup_tab(self):
        f = self.tab_backup
        ttk.Label(
            f,
            text=(
                "Il programma mantiene soltanto due backup automatici. "
                "Ogni nuovo backup sovrascrive il più vecchio dei due."
            ),
            wraplength=800
        ).pack(anchor="w")

        self.backup_tree = self._tree(
            f, ("file","date","size"), ("File","Data backup","Dimensione"),
            (220,220,160), height=7
        )

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Button(bar,text="Crea backup adesso",command=self.manual_backup).pack(side="left")
        ttk.Button(bar,text="Ripristina backup selezionato",command=self.restore_selected_backup).pack(side="left",padx=8)
        ttk.Button(bar,text="Apri cartella backup",command=self.open_backup_folder).pack(side="left")

    def manual_backup(self):
        p = create_rotating_backup()
        self.refresh_backups()
        messagebox.showinfo("Backup creato", f"Creato:\n{p.name}")

    def restore_selected_backup(self):
        sel = self.backup_tree.selection()
        if not sel:
            return messagebox.showwarning("Seleziona backup","Seleziona uno dei due backup.")
        filename = self.backup_tree.item(sel[0],"values")[0]
        path = BASE_DIR / "backups" / filename
        if not messagebox.askyesno(
            "ATTENZIONE",
            f"Ripristinare {filename}?\nIl database corrente verrà sostituito."
        ):
            return
        try:
            restore_backup(path)
            export_site_data()
            self.refresh_all()
            messagebox.showinfo("Ripristino completato","Backup ripristinato correttamente.")
        except Exception as e:
            messagebox.showerror("Errore ripristino",str(e))

    def open_backup_folder(self):
        path = BASE_DIR / "backups"
        path.mkdir(exist_ok=True)
        if sys.platform.startswith("win"):
            os_startfile = getattr(__import__("os"), "startfile", None)
            if os_startfile:
                os_startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    # ---------- Pubblicazione / anteprima ----------
    def save_and_publish(self):
        try:
            # Prima salva la configurazione attualmente visibile.
            set_setting("league_name", self.league_var.get().strip() or "La Mia Lega")
            sid = self._id_from_combo(self.current_season_var.get())
            set_setting("current_season_id", sid or "")

            backup = create_rotating_backup()
            export_site_data()
            self.refresh_backups()

            try:
                msg = publish_to_github()
                messagebox.showinfo(
                    "Operazione completata",
                    f"Backup creato: {backup.name}\n{msg}"
                )
            except PublishError as e:
                messagebox.showwarning(
                    "Backup creato, pubblicazione non riuscita",
                    f"Il backup è stato creato correttamente ({backup.name}).\n\n"
                    f"GitHub non è stato aggiornato:\n{e}"
                )
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def preview_site(self):
        try:
            export_site_data()
            if self.preview_process is None or self.preview_process.poll() is not None:
                self.preview_process = subprocess.Popen(
                    [sys.executable, "-m", "http.server", "8000", "--directory", str(DOCS_DIR)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            webbrowser.open("http://127.0.0.1:8000/")
        except Exception as e:
            messagebox.showerror("Errore anteprima", str(e))

    # ---------- Refresh ----------
    def refresh_all(self):
        self.refresh_seasons()
        self.refresh_teams()
        self.refresh_rosters()
        self.refresh_matches()
        self.refresh_stats()
        self.refresh_champions()
        self.refresh_backups()
        self.refresh_team_combos()
        self.refresh_stat_matches()
        self.league_var.set(get_setting("league_name","La Mia Lega"))

        cur = get_setting("current_season_id","")
        if cur:
            with connect() as conn:
                s = conn.execute("SELECT id,name FROM seasons WHERE id=?", (cur,)).fetchone()
            self.current_season_var.set(self._combo_text(s["id"],s["name"]) if s else "")
        else:
            self.current_season_var.set("")

        try:
            export_site_data()
        except Exception:
            pass

    def refresh_seasons(self):
        with connect() as conn:
            seasons = conn.execute(
                "SELECT id,name,archive_mode FROM seasons ORDER BY id DESC"
            ).fetchall()

        full_seasons = [s for s in seasons if s["archive_mode"] == "full"]
        full_values = [self._combo_text(s["id"], s["name"]) for s in full_seasons]

        # Le stagioni "solo Albo d'Oro" NON devono comparire nei menu usati
        # per squadre, rose, partite e statistiche.
        for c in [
            getattr(self,"current_season_combo",None),
            getattr(self,"team_season_combo",None),
            getattr(self,"roster_season_combo",None),
            getattr(self,"match_season_combo",None),
            getattr(self,"stat_season_combo",None),
            getattr(self,"champ_season_combo",None),
        ]:
            if c is not None:
                c["values"] = full_values

        # Nel tab Stagioni mostriamo comunque tutto, indicando il tipo.
        self._replace_tree(
            self.seasons_tree,
            [
                (
                    s["id"],
                    s["name"] if s["archive_mode"] == "full"
                    else f'{s["name"]}  [solo Albo d\'Oro]'
                )
                for s in seasons
            ]
        )

    def refresh_teams(self):
        sid = self._id_from_combo(self.team_season_var.get())

        # Se non è ancora stata scelta una stagione nel tab Squadre,
        # usa automaticamente la stagione corrente (ma solo se è completa).
        if not sid:
            try:
                current_sid = int(get_setting("current_season_id", "") or 0)
            except ValueError:
                current_sid = 0

            if current_sid:
                with connect() as conn:
                    s = conn.execute(
                        "SELECT id,name FROM seasons WHERE id=? AND archive_mode='full'",
                        (current_sid,)
                    ).fetchone()
                if s:
                    sid = s["id"]
                    self.team_season_var.set(self._combo_text(s["id"], s["name"]))

        if not sid:
            self._replace_tree(self.teams_tree, [])
            return

        with connect() as conn:
            data = conn.execute(
                """
                SELECT s.name season,t.id,t.name team,st.coach_name,
                       COALESCE(NULLIF(st.logo_path,''), t.logo_path) AS logo_path
                FROM season_teams st
                JOIN seasons s ON s.id=st.season_id
                JOIN teams t ON t.id=st.team_id
                WHERE st.season_id=? AND s.archive_mode='full'
                ORDER BY t.name COLLATE NOCASE
                """,
                (sid,)
            ).fetchall()

        self._replace_tree(self.teams_tree, [
            (r["season"],r["id"],r["team"],r["coach_name"],r["logo_path"]) for r in data
        ])

    def refresh_rosters(self):
        with connect() as conn:
            data = conn.execute(
                """
                SELECT s.name season,t.name team,p.id,p.name player,r.role
                FROM rosters r
                JOIN seasons s ON s.id=r.season_id
                JOIN teams t ON t.id=r.team_id
                JOIN players p ON p.id=r.player_id
                ORDER BY s.id DESC,t.name,p.name
                """
            ).fetchall()
        self._replace_tree(self.roster_tree, [
            (r["season"],r["team"],r["id"],r["player"],r["role"]) for r in data
        ])

    def refresh_matches(self):
        with connect() as conn:
            data = conn.execute(
                """
                SELECT m.id,s.name season,m.round_no,m.match_date,
                       ht.name home,m.home_score,m.away_score,at.name away
                FROM matches m
                JOIN seasons s ON s.id=m.season_id
                JOIN teams ht ON ht.id=m.home_team_id
                JOIN teams at ON at.id=m.away_team_id
                ORDER BY s.id DESC,m.round_no,m.id
                """
            ).fetchall()
        self._replace_tree(self.matches_tree, [
            (r["id"],r["season"],r["round_no"],r["match_date"],r["home"],
             f'{r["home_score"]} - {r["away_score"]}',r["away"]) for r in data
        ])

    def refresh_stats(self):
        with connect() as conn:
            data = conn.execute(
                """
                SELECT pms.id,s.name season,m.round_no,
                       ht.name || ' ' || m.home_score || ' - ' || m.away_score || ' ' || at.name AS match_text,
                       t.name team,p.name player,pms.goals,pms.assists
                FROM player_match_stats pms
                JOIN matches m ON m.id=pms.match_id
                JOIN seasons s ON s.id=m.season_id
                JOIN teams ht ON ht.id=m.home_team_id
                JOIN teams at ON at.id=m.away_team_id
                JOIN teams t ON t.id=pms.team_id
                JOIN players p ON p.id=pms.player_id
                ORDER BY s.id DESC,m.round_no,p.name
                """
            ).fetchall()
        self._replace_tree(self.stats_tree, [
            (r["id"],r["season"],r["round_no"],r["match_text"],r["team"],r["player"],r["goals"],r["assists"])
            for r in data
        ])

    def refresh_champions(self):
        with connect() as conn:
            data = conn.execute(
                """
                SELECT s.name season,t.name team,c.coach_name
                FROM champions c
                JOIN seasons s ON s.id=c.season_id
                JOIN teams t ON t.id=c.team_id
                ORDER BY s.id DESC
                """
            ).fetchall()
        self._replace_tree(self.champ_tree, [
            (r["season"],r["team"],r["coach_name"]) for r in data
        ])

    def refresh_backups(self):
        if not hasattr(self,"backup_tree"):
            return
        rows = []
        for b in backup_list():
            rows.append((
                b["path"].name,
                b["modified"].strftime("%d/%m/%Y %H:%M:%S"),
                f'{b["size"]/1024:.1f} KB'
            ))
        self._replace_tree(self.backup_tree,rows)

    def refresh_team_combos(self):
        pairs = [
            ("roster", self.roster_season_var, getattr(self,"roster_team_combo",None)),
            ("match_home", self.match_season_var, getattr(self,"match_home_combo",None)),
            ("match_away", self.match_season_var, getattr(self,"match_away_combo",None)),
            ("champ", self.champ_season_var, getattr(self,"champ_team_combo",None)),
        ]
        for _, season_var, combo in pairs:
            if combo is None:
                continue
            sid = self._id_from_combo(season_var.get())
            combo["values"] = self._teams_for_season(sid)

    def refresh_stat_matches(self):
        if not hasattr(self,"stat_match_combo"):
            return
        sid = self._id_from_combo(self.stat_season_var.get())
        vals = []
        if sid:
            with connect() as conn:
                rows = conn.execute(
                    """
                    SELECT m.id,m.round_no,ht.name home,m.home_score,m.away_score,at.name away
                    FROM matches m
                    JOIN teams ht ON ht.id=m.home_team_id
                    JOIN teams at ON at.id=m.away_team_id
                    WHERE m.season_id=?
                    ORDER BY m.round_no,m.id
                    """,(sid,)
                ).fetchall()
            vals = [self._combo_text(r["id"],f'G{r["round_no"]} - {r["home"]} {r["home_score"]}-{r["away_score"]} {r["away"]}') for r in rows]
        self.stat_match_combo["values"] = vals
        self.stat_match_var.set("")
        self.stat_team_var.set("")
        self.stat_player_var.set("")

    def refresh_stat_teams(self):
        mid = self._id_from_combo(self.stat_match_var.get())
        vals = []
        if mid:
            with connect() as conn:
                m = conn.execute(
                    """
                    SELECT ht.id hid,ht.name home,at.id aid,at.name away
                    FROM matches m
                    JOIN teams ht ON ht.id=m.home_team_id
                    JOIN teams at ON at.id=m.away_team_id
                    WHERE m.id=?
                    """,(mid,)
                ).fetchone()
            if m:
                vals=[self._combo_text(m["hid"],m["home"]),self._combo_text(m["aid"],m["away"])]
        self.stat_team_combo["values"]=vals
        self.stat_team_var.set("")
        self.stat_player_var.set("")

    def refresh_stat_players(self):
        sid = self._id_from_combo(self.stat_season_var.get())
        tid = self._id_from_combo(self.stat_team_var.get())
        vals=[]
        if sid and tid:
            with connect() as conn:
                rows=conn.execute(
                    """
                    SELECT p.id,p.name
                    FROM rosters r JOIN players p ON p.id=r.player_id
                    WHERE r.season_id=? AND r.team_id=?
                    ORDER BY p.name COLLATE NOCASE
                    """,(sid,tid)
                ).fetchall()
            vals=[self._combo_text(r["id"],r["name"]) for r in rows]
        self.stat_player_combo["values"]=vals
        self.stat_player_var.set("")

    # ---------- helpers ----------
    @staticmethod
    def _combo_text(id_, label):
        return f"{id_} | {label}"

    @staticmethod
    def _id_from_combo(text):
        try:
            return int(str(text).split("|",1)[0].strip())
        except (ValueError,AttributeError):
            return None

    def _season_id_by_name(self,name):
        with connect() as conn:
            r=conn.execute("SELECT id FROM seasons WHERE name=?",(name,)).fetchone()
        return r["id"] if r else None

    def _teams_for_season(self,sid):
        if not sid:
            return []
        with connect() as conn:
            rows=conn.execute(
                """
                SELECT t.id,t.name FROM season_teams st
                JOIN teams t ON t.id=st.team_id
                WHERE st.season_id=? ORDER BY t.name COLLATE NOCASE
                """,(sid,)
            ).fetchall()
        return [self._combo_text(r["id"],r["name"]) for r in rows]

    @staticmethod
    def _replace_tree(tree, rows):
        for item in tree.get_children():
            tree.delete(item)
        for r in rows:
            tree.insert("","end",values=r)

if __name__ == "__main__":
    FantacalcioApp().mainloop()
