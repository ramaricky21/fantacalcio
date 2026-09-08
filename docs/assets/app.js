const DATA_URL = "data/fantacalcio.json";

async function loadData() {
  const r = await fetch(DATA_URL, {cache: "no-store"});
  if (!r.ok) throw new Error("Impossibile caricare i dati.");
  return await r.json();
}
function qs(name) { return new URLSearchParams(location.search).get(name); }
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => (
    {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]
  ));
}
function img(path, cls="small-logo") {
  return `<img class="${cls}" src="${esc(path || 'assets/logos/default-logo.svg')}" alt="">`;
}
function seasonById(data, id) {
  return data.seasons.find(s => Number(s.id) === Number(id));
}
function currentSeason(data) {
  const selected = seasonById(data, data.current_season_id);
  if (selected && (selected.archive_mode || "full") === "full") return selected;
  return data.seasons.find(s => (s.archive_mode || "full") === "full");
}
function teamById(season, id) {
  return season?.teams.find(t => Number(t.id) === Number(id));
}
function statsText(match, teamId) {
  const stats = (match.stats || []).filter(x => Number(x.team_id) === Number(teamId) && (x.goals || x.assists));
  if (!stats.length) return "";
  return stats.map(s => {
    const bits = [];
    if (s.goals) bits.push(`${s.goals} gol`);
    if (s.assists) bits.push(`${s.assists} assist`);
    return `${esc(s.player_name)}: ${bits.join(", ")}`;
  }).join(" · ");
}

async function renderHome(data) {
  document.title = data.league_name;
  document.getElementById("league-name").textContent = data.league_name;
  const season = currentSeason(data);
  if (!season) {
    document.getElementById("radial-home").classList.add("hidden");
    const e = document.getElementById("empty-state");
    e.classList.remove("hidden");
    e.innerHTML = "<h1>Fantacalcio</h1><p>Il sito è pronto. L'amministratore deve ancora creare la prima stagione.</p>";
    return;
  }
  document.getElementById("season-name").textContent = season.name;
  document.getElementById("league-center").href = `league.html?season=${season.id}`;

  const wrap = document.getElementById("radial-teams");
  const n = season.teams.length;
  const radiusX = 39, radiusY = 40;
  wrap.innerHTML = season.teams.map((t,i) => {
    const angle = -Math.PI/2 + (2*Math.PI*i/Math.max(n,1));
    const left = 50 + radiusX*Math.cos(angle);
    const top = 50 + radiusY*Math.sin(angle);
    return `<a class="radial-team" style="left:${left}%;top:${top}%"
       href="team.html?team=${t.id}&season=${season.id}">
       ${img(t.logo,"")}
       <span>${esc(t.name)}</span>
    </a>`;
  }).join("");
}

function standingsTable(season) {
  const rows = season.standings.map(x => `
    <tr>
      <td><strong>${x.position}</strong></td>
      <td class="team-cell">${img(x.logo)}<a href="team.html?team=${x.team_id}&season=${season.id}">${esc(x.name)}</a></td>
      <td>${x.played}</td><td>${x.wins}</td><td>${x.draws}</td><td>${x.losses}</td>
      <td>${x.gf}</td><td>${x.ga}</td><td>${x.gd > 0 ? "+" : ""}${x.gd}</td>
      <td><strong>${x.points}</strong></td>
    </tr>`).join("");
  return `<thead><tr>
    <th>#</th><th>Squadra</th><th>PG</th><th>V</th><th>N</th><th>P</th>
    <th>GF</th><th>GS</th><th>DR</th><th>Pt</th>
  </tr></thead><tbody>${rows}</tbody>`;
}
function calendarHtml(season) {
  const groups = {};
  season.matches.forEach(m => (groups[m.round_no] ||= []).push(m));
  const rounds = Object.keys(groups).sort((a,b)=>Number(a)-Number(b));
  if (!rounds.length) return `<p class="muted">Nessuna partita inserita.</p>`;
  return rounds.map(r => `
    <div class="round">
      <h3>Giornata ${esc(r)}</h3>
      ${groups[r].map(m => `
        <div class="match">
          <a class="home" href="team.html?team=${m.home_team_id}&season=${season.id}">${esc(m.home_name)}</a>
          <span class="score">${m.home_score} - ${m.away_score}</span>
          <a class="away" href="team.html?team=${m.away_team_id}&season=${season.id}">${esc(m.away_name)}</a>
          ${(m.match_date || m.stats?.length) ? `<div class="match-details">
            ${m.match_date ? esc(m.match_date) + (m.stats?.length ? " · " : "") : ""}
            ${statsText(m,m.home_team_id)}
            ${(statsText(m,m.home_team_id) && statsText(m,m.away_team_id)) ? " | " : ""}
            ${statsText(m,m.away_team_id)}
          </div>` : ""}
        </div>`).join("")}
    </div>`).join("");
}
function championsHtml(data) {
  if (!data.champions_history.length) return `<p class="muted">Nessun vincitore ancora registrato.</p>`;
  return data.champions_history.map(c => `
    <div class="card">
      ${img(c.logo,"card-logo")}
      <h3>${esc(c.season_name)}</h3>
      <p><strong>${esc(c.team_name)}</strong></p>
      <p class="muted">Fantallenatore: ${esc(c.coach_name || "-")}</p>
    </div>`).join("");
}
function palmaresHtml(data) {
  if (!data.palmares.length) return `<p class="muted">Il palmarès apparirà dopo il primo campione registrato.</p>`;
  return data.palmares.map((p,i) => `
    <div class="ranking-row">
      <span class="medal">${i===0?"🥇":i===1?"🥈":i===2?"🥉":(i+1)+"°"}</span>
      <span>${img(p.logo)}<strong>${esc(p.name)}</strong></span>
      <strong>${"🏆".repeat(Math.min(Number(p.titles),8))} ${p.titles}</strong>
    </div>`).join("");
}

async function renderLeague(data) {
  const selected = Number(qs("season") || data.current_season_id);
  const season = seasonById(data, selected) || currentSeason(data);
  if (!season) return;
  document.title = `${data.league_name} - ${season.name}`;
  document.getElementById("header-league").textContent = data.league_name;
  document.getElementById("league-title").textContent = data.league_name;
  document.getElementById("league-season").textContent = `Stagione ${season.name}`;
  document.getElementById("standings-table").innerHTML = standingsTable(season);
  document.getElementById("calendar").innerHTML = calendarHtml(season);

  const fullSeasons = data.seasons.filter(s => (s.archive_mode || "full") === "full");
  document.getElementById("archive").innerHTML = fullSeasons.map(s => `
    <a class="card" href="league.html?season=${s.id}">
      <h3>${esc(s.name)}</h3>
      <p>${s.matches.length} partite registrate</p>
      ${s.champion ? `<p>🏆 ${esc(s.champion.team_name)}</p>` : `<p class="muted">Vincitore non registrato</p>`}
    </a>`).join("");

  document.getElementById("champions-history").innerHTML = championsHtml(data);
  document.getElementById("palmares").innerHTML = palmaresHtml(data);
}

function ranking(items, key) {
  const arr = [...items].sort((a,b) => Number(b[key]) - Number(a[key]) || a.name.localeCompare(b.name));
  const positive = arr.filter(x => Number(x[key]) > 0);
  if (!positive.length) return `<p class="muted">Nessun dato ancora registrato.</p>`;
  return positive.map((p,i)=>`
    <div class="ranking-row">
      <span class="medal">${i+1}°</span>
      <span>${esc(p.name)}</span>
      <strong>${p[key]}</strong>
    </div>`).join("");
}

async function renderTeam(data) {
  const sid = Number(qs("season") || data.current_season_id);
  const season = seasonById(data,sid) || currentSeason(data);
  const tid = Number(qs("team"));
  const team = teamById(season,tid);
  if (!season || !team) {
    document.querySelector("main").innerHTML = `<div class="panel"><h1>Squadra non trovata</h1><a href="index.html">Torna alla home</a></div>`;
    return;
  }
  document.title = `${team.name} - ${season.name}`;
  document.getElementById("back-league").href = `league.html?season=${season.id}`;
  document.getElementById("team-logo").src = team.logo || "assets/logos/default-logo.svg";
  document.getElementById("team-title").textContent = team.name;
  document.getElementById("team-coach").textContent = `Fantallenatore: ${team.coach || "-"}`;
  document.getElementById("team-season").textContent = `Stagione ${season.name}`;

  document.getElementById("roster-table").innerHTML = `
    <thead><tr><th>Giocatore</th><th>Ruolo</th><th>Gol</th><th>Assist</th></tr></thead>
    <tbody>${team.roster.map(p=>`
      <tr><td class="team-cell">${esc(p.name)}</td><td>${esc(p.role)}</td><td>${p.goals}</td><td>${p.assists}</td></tr>
    `).join("")}</tbody>`;

  document.getElementById("scorers").innerHTML = ranking(team.roster,"goals");
  document.getElementById("assists").innerHTML = ranking(team.roster,"assists");

  const matches = season.matches.filter(m => Number(m.home_team_id)===tid || Number(m.away_team_id)===tid);
  document.getElementById("team-matches").innerHTML = matches.length ? matches.map(m => {
    const isHome = Number(m.home_team_id)===tid;
    const gf = isHome ? m.home_score : m.away_score;
    const ga = isHome ? m.away_score : m.home_score;
    const outcome = gf>ga ? "V" : gf<ga ? "P" : "N";
    const details = statsText(m,tid);
    return `<div class="match">
      <span class="home">Giornata ${m.round_no}</span>
      <span class="score">${esc(m.home_name)} ${m.home_score} - ${m.away_score} ${esc(m.away_name)}</span>
      <strong class="away">${outcome}</strong>
      ${details ? `<div class="match-details">${details}</div>` : ""}
    </div>`;
  }).join("") : `<p class="muted">Nessuna partita registrata.</p>`;
}

(async function(){
  try {
    const data = await loadData();
    const page = document.body.dataset.page;
    if (page === "home") await renderHome(data);
    if (page === "league") await renderLeague(data);
    if (page === "team") await renderTeam(data);
  } catch (e) {
    console.error(e);
    const main = document.querySelector("main");
    if (main) main.innerHTML = `<div class="empty"><h1>Errore caricamento dati</h1><p>${esc(e.message)}</p></div>`;
  }
})();
