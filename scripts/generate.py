#!/usr/bin/env python3
"""Generate terminal-style SVG panels for the GitHub profile README.

Outputs (in ./assets): terminal_stats.svg, terminal_skills.svg, terminal_projects.svg
Data: public GitHub REST API + the public contributions calendar. A GITHUB_TOKEN
(optional) only raises rate limits. Standard library only.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

USER = os.environ.get("GH_USER", "priyanshuu-x")
OUT = Path(__file__).resolve().parent.parent / "assets"
TOKEN = os.environ.get("GITHUB_TOKEN")

# palette (GitHub-dark terminal)
BG, BORDER, FG, DIM = "#0d1117", "#30363d", "#c9d1d9", "#6e7681"
GREEN, CYAN, MAGENTA, AMBER, BLUE = "#3fb950", "#56d4dd", "#d2a8ff", "#e3b341", "#79c0ff"
HEAT = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FONT = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'DejaVu Sans Mono',monospace"
CW = 7.8  # approx glyph width at 13px, used only for pill sizing

SKILLS = {
    "ai/": ["agents", "rag", "mcp", "evals", "langchain", "langgraph", "langsmith"],
    "core/": ["python", "pytorch", "sql", "fastapi"],
    "ops/": ["docker", "security"],
}
PROJECTS = [
    ("PaperPilot", "RAG over 20 arXiv papers: cited answers, 0.89 groundedness (DeepEval), refuses off-topic.", "rag · langgraph · fastapi · langsmith"),
    ("TicketPilot", "4-agent LangGraph support system with MCP tools: 19/19 correct, 0 wrong refunds in evals.", "agents · mcp · langgraph · evals"),
    ("PayPal-hackathon", "ProofCheck: verifies refund & dispute evidence against PayPal's real records.", "agents · mcp · fastapi · security"),
]


def get(url, accept=None):
    h = {"User-Agent": "profile-readme-generator"}
    if accept:
        h["Accept"] = accept
    if TOKEN and "api.github.com" in url:
        h["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        return r.read().decode()


def api(path):
    return json.loads(get(f"https://api.github.com{path}"))


def esc(s):
    return html.escape(str(s), quote=True)


def fetch_stats():
    user = api(f"/users/{USER}")
    repos, page = [], 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = Counter()
    for r in own:
        try:
            for k, v in api(f"/repos/{USER}/{r['name']}/languages").items():
                langs[k] += v
        except Exception:
            if r.get("language"):
                langs[r["language"]] += 1
    prs = commits = None
    try:
        prs = api(f"/search/issues?q=author:{USER}+type:pr&per_page=1")["total_count"]
    except Exception:
        pass
    try:
        commits = api(f"/search/commits?q=author:{USER}&per_page=1")["total_count"]
    except Exception:
        pass
    return {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in own),
        "prs": prs,
        "commits": commits,
        "langs": langs,
        "since": user["created_at"][:4],
    }


def fetch_calendar():
    page = get(f"https://github.com/users/{USER}/contributions")
    counts = {}
    for m in re.finditer(r'for="(contribution-day-component-\d+-\d+)"[^>]*>\s*([^<]*)', page):
        n = re.match(r"(\d+) contribution", m.group(2).strip())
        counts[m.group(1)] = int(n.group(1)) if n else 0
    days = []
    for m in re.finditer(r"<td[^>]*data-date=\"([\d-]+)\"[^>]*id=\"([^\"]+)\"[^>]*data-level=\"(\d)\"", page):
        days.append((dt.date.fromisoformat(m.group(1)), int(m.group(3)), counts.get(m.group(2), 0)))
    days.sort()
    return days


def streaks(days):
    longest = cur = 0
    for _, _, c in days:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    current = 0
    for i, (_, _, c) in enumerate(reversed(days)):
        if c > 0:
            current += 1
        elif i > 0:  # today may still be empty; any earlier gap ends the streak
            break
    return current, longest


def window(title, w, h, body, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">
<style>
text{{font-family:{FONT};font-size:13px;fill:{FG}}}
.d{{fill:{DIM}}} .g{{fill:{GREEN}}} .c{{fill:{CYAN}}} .m{{fill:{MAGENTA}}} .a{{fill:{AMBER}}} .b{{fill:{BLUE}}} .bold{{font-weight:700}}
.cur{{animation:blink 1.1s steps(1) infinite}} @keyframes blink{{50%{{opacity:0}}}}
.fade{{opacity:0;animation:in .5s ease forwards}} @keyframes in{{to{{opacity:1}}}}
.grow{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:gr .9s ease forwards}} @keyframes gr{{to{{transform:scaleX(1)}}}}
{extra_css}
@media (prefers-reduced-motion:reduce){{.cur,.fade,.grow{{animation:none;opacity:1;transform:none}}}}
</style>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<path d="M0.5 11a10 10 0 0 1 10-10h{w-21}a10 10 0 0 1 10 10v26H0.5z" fill="#161b22"/>
<line x1="0.5" y1="37.5" x2="{w-0.5}" y2="37.5" stroke="{BORDER}"/>
<circle cx="22" cy="19" r="5.5" fill="#ff5f56"/><circle cx="42" cy="19" r="5.5" fill="#ffbd2e"/><circle cx="62" cy="19" r="5.5" fill="#27c93f"/>
<text x="{w/2}" y="23" text-anchor="middle" class="d">{esc(title)}</text>
{body}
</svg>
"""


def prompt(y, cmd, delay=0.0):
    return (f'<g class="fade" style="animation-delay:{delay}s"><text x="24" y="{y}"><tspan class="g bold">priyanshu@github</tspan>'
            f'<tspan class="d">:</tspan><tspan class="b">~</tspan><tspan class="d">$ </tspan>{esc(cmd)}</text></g>')


def stats_svg(s, days):
    W = 860
    cur, longest = streaks(days)
    total = sum(c for _, _, c in days)
    fmt = lambda v: "n/a" if v is None else f"{v:,}"
    rows = [
        ("repos", fmt(s["repos"])), ("followers", fmt(s["followers"])), ("stars", fmt(s["stars"])),
        ("pull requests", fmt(s["prs"])), ("commits", fmt(s["commits"])),
        ("contributions / 12mo", fmt(total)), ("current streak", f"{cur} days"), ("longest streak", f"{longest} days"),
    ]
    b = [prompt(66, f"gh stats --user {USER}")]
    y = 94
    for i, (k, v) in enumerate(rows):
        b.append(f'<g class="fade" style="animation-delay:{0.15+i*0.07:.2f}s"><text x="40" y="{y}" class="d">{esc(k)}</text>'
                 f'<text x="230" y="{y}" class="a bold">{esc(v)}</text></g>')
        y += 22
    # languages (right column)
    lx = 420
    b.append(f'<text x="{lx}" y="94" class="m bold"># top languages</text>')
    tot = sum(s["langs"].values()) or 1
    top = [(n, v) for n, v in s["langs"].most_common(5) if v / tot >= 0.01]
    colors = [GREEN, CYAN, MAGENTA, AMBER, BLUE]
    for i, (name, v) in enumerate(top):
        yy = 120 + i * 26
        pct = v / tot * 100
        bw = max(4, 250 * pct / 100 / (top[0][1] / tot))  # scale to the biggest
        b.append(f'<text x="{lx}" y="{yy+11}">{esc(name)}</text>'
                 f'<rect x="{lx+130}" y="{yy}" width="250" height="14" rx="3" fill="#161b22"/>'
                 f'<rect class="grow" style="animation-delay:{0.3+i*0.12:.2f}s" x="{lx+130}" y="{yy}" width="{bw:.0f}" height="14" rx="3" fill="{colors[i]}"/>'
                 f'<text x="{lx+392}" y="{yy+11}" class="d">{pct:.0f}%</text>')
    H = 94 + 22 * len(rows) + 22
    b.append(f'<text x="24" y="{H-16}"><tspan class="g bold">priyanshu@github</tspan><tspan class="d">:</tspan><tspan class="b">~</tspan><tspan class="d">$ </tspan><tspan class="cur g">█</tspan></text>')
    return window(f"{USER}@github: ~/stats", W, H, "\n".join(b))


def skills_svg():
    W = 860
    b = [prompt(66, "ls -R ~/skills")]
    y = 100
    colors = [GREEN, CYAN, MAGENTA]
    for gi, (group, items) in enumerate(SKILLS.items()):
        b.append(f'<g class="fade" style="animation-delay:{0.2+gi*0.25:.2f}s"><text x="40" y="{y+17}" class="a bold">{esc(group)}</text>')
        x = 130
        for it in items:
            pw = len(it) * CW + 26
            col = colors[gi]
            b.append(f'<rect x="{x:.0f}" y="{y}" width="{pw:.0f}" height="26" rx="13" fill="{col}" fill-opacity="0.10" stroke="{col}" stroke-opacity="0.7"/>'
                     f'<text x="{x+pw/2:.0f}" y="{y+17}" text-anchor="middle">{esc(it)}</text>')
            x += pw + 10
        b.append("</g>")
        y += 44
    H = y + 34
    b.append(f'<text x="24" y="{H-16}"><tspan class="g bold">priyanshu@github</tspan><tspan class="d">:</tspan><tspan class="b">~</tspan><tspan class="d">$ </tspan><tspan class="cur g">█</tspan></text>')
    return window(f"{USER}@github: ~/skills", W, H, "\n".join(b))


def projects_svg():
    W = 860
    b = [prompt(66, "ls -l ~/projects")]
    y = 98
    accents = [CYAN, MAGENTA, GREEN]
    for i, (name, desc, tags) in enumerate(PROJECTS):
        col = accents[i % len(accents)]
        b.append(f'<g class="fade" style="animation-delay:{0.2+i*0.25:.2f}s">'
                 f'<text x="40" y="{y}"><tspan class="d">drwxr-xr-x  </tspan><tspan fill="{col}" class="bold">{esc(name)}/</tspan></text>'
                 f'<text x="64" y="{y+20}">{esc(desc)}</text>'
                 f'<text x="64" y="{y+40}" style="font-size:12px;fill:{col};fill-opacity:0.8">[{esc(tags)}]</text></g>')
        y += 74
    H = y + 18
    b.append(f'<text x="24" y="{H-16}"><tspan class="g bold">priyanshu@github</tspan><tspan class="d">:</tspan><tspan class="b">~</tspan><tspan class="d">$ </tspan><tspan class="cur g">█</tspan></text>')
    return window(f"{USER}@github: ~/projects", W, H, "\n".join(b))

ABOUT = [
    ("working_on", "multi-agent RAG systems, MCP tool servers, and their evals & guardrails", CYAN),
    ("exploring", "agent evals, MCP, production, observability", GREEN),
    ("status", "open to AI engineer roles & internships", MAGENTA),
    ("education", "B.Tech CSE, Bennett University (exp. May 2027)", BLUE),
    ("contact", "priyanshuuux@gmail.com", AMBER),
]


def about_svg():
    W = 860
    b = [prompt(66, "cat ~/about.md")]
    y = 98
    for i, (k, v, col) in enumerate(ABOUT):
        b.append(f'<g class="fade" style="animation-delay:{0.2+i*0.25:.2f}s"><text x="40" y="{y}"><tspan class="d">&gt; </tspan>'
                 f'<tspan fill="{col}" class="bold">{k}</tspan><tspan class="d">: </tspan><tspan>{esc(v)}</tspan></text></g>')
        y += 28
    H = y + 30
    b.append(f'<text x="24" y="{H-16}"><tspan class="g bold">priyanshu@github</tspan><tspan class="d">:</tspan><tspan class="b">~</tspan><tspan class="d">$ </tspan><tspan class="cur g">█</tspan></text>')
    return window(f"{USER}@github: ~/about", W, H, "\n".join(b))


def pill_svg(label, color):
    w = int((len(label) + 5) * CW + 46)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="34" viewBox="0 0 {w} 34" role="img" aria-label="{esc(label)}">'
            f'<style>text{{font-family:{FONT};font-size:13px;fill:{FG}}}</style>'
            f'<rect x="0.5" y="0.5" width="{w-1}" height="33" rx="8" fill="{BG}" stroke="{color}" stroke-opacity="0.8"/>'
            f'<text x="14" y="21" fill="{color}" style="fill:{color};font-weight:700">$</text>'
            f'<text x="28" y="21">open {esc(label)}</text></svg>\n')


BANNER = [
    "██████╗ ██████╗ ██╗██╗   ██╗ █████╗ ███╗   ██╗███████╗██╗  ██╗██╗   ██╗",
    "██╔══██╗██╔══██╗██║╚██╗ ██╔╝██╔══██╗████╗  ██║██╔════╝██║  ██║██║   ██║",
    "██████╔╝██████╔╝██║ ╚████╔╝ ███████║██╔██╗ ██║███████╗███████║██║   ██║",
    "██╔═══╝ ██╔══██╗██║  ╚██╔╝  ██╔══██║██║╚██╗██║╚════██║██╔══██║██║   ██║",
    "██║     ██║  ██║██║   ██║   ██║  ██║██║ ╚████║███████║██║  ██║╚██████╔╝",
    "╚═╝     ╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ",
]
TAGLINE = "AI Engineer · Generative AI / LLM Applications"
TAGS = "multi-agent RAG · MCP · evals · guardrails"


def banner_svg():
    W = 860
    cw, ch = 9.0, 17.0
    tl = len(BANNER[0]) * cw
    x0 = (W - tl) / 2
    b = [prompt(66, "figlet priyanshu", 0.0)]
    y0 = 88
    # Looping "load" effect: the wordmark is split into 8-column chunks that reveal left to right
    # while a scan line sweeps across; the cycle repeats every CYCLE seconds.
    CYCLE, CHUNK = 12, 8
    chunks = {}
    for i, line in enumerate(BANNER):
        for j, c in enumerate(line):
            x, y = x0 + j * cw, y0 + i * ch
            if c == "█":
                r = f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw+0.3}" height="{ch+0.3}" fill="url(#bg)"/>'
            elif c != " ":
                r = f'<rect x="{x+1.5:.1f}" y="{y+1.5:.1f}" width="{cw-3}" height="{ch-3}" fill="{CYAN}" fill-opacity="0.22"/>'
            else:
                continue
            chunks.setdefault(j // CHUNK, []).append(r)
    for k in sorted(chunks):
        b.append(f'<g class="ld" style="animation-delay:{k*0.12:.2f}s">{"".join(chunks[k])}</g>')
    bh = len(BANNER) * ch
    b.append(f'<rect class="scan" x="{x0:.1f}" y="{y0-4}" width="3" height="{bh+8}" rx="1.5" fill="{CYAN}"/>')
    y = y0 + len(BANNER) * ch + 34
    b.append(f'<text class="fade bold" style="animation-delay:1.1s" x="{W/2}" y="{y}" text-anchor="middle">{esc(TAGLINE)}</text>')
    b.append(f'<text class="fade d" style="animation-delay:1.3s" x="{W/2}" y="{y+22}" text-anchor="middle">{esc(TAGS)}</text>')
    H = y + 62
    b.append(f'<text x="24" y="{H-16}"><tspan class="g bold">priyanshu@github</tspan><tspan class="d">:</tspan><tspan class="b">~</tspan><tspan class="d">$ </tspan><tspan class="cur g">█</tspan></text>')
    sweep = tl - 3
    css = (f".ld{{opacity:0;animation:ld {CYCLE}s linear infinite both}}"
           f"@keyframes ld{{0%{{opacity:0}}3%{{opacity:1}}90%{{opacity:1}}94%{{opacity:0}}100%{{opacity:0}}}}"
           f".scan{{opacity:0;filter:drop-shadow(0 0 4px {CYAN});animation:scan {CYCLE}s linear infinite both}}"
           f"@keyframes scan{{0%{{transform:translateX(0);opacity:1}}9.5%{{transform:translateX({sweep:.0f}px);opacity:1}}10%{{transform:translateX({sweep:.0f}px);opacity:0}}100%{{opacity:0}}}}"
           f"@media (prefers-reduced-motion:reduce){{.ld{{animation:none;opacity:1}}.scan{{display:none}}}}")
    svg = window(f"{USER}@github: ~", W, H, "\n".join(b), css)
    defs = (f'<defs><linearGradient id="bg" gradientUnits="userSpaceOnUse" x1="{x0:.1f}" x2="{x0+tl:.1f}" y1="0" y2="0"><stop offset="0" stop-color="{GREEN}"/>'
            f'<stop offset="0.5" stop-color="{CYAN}"/><stop offset="1" stop-color="{MAGENTA}"/></linearGradient></defs>')
    return svg.replace("</style>", "</style>\n" + defs, 1)


def main():
    OUT.mkdir(exist_ok=True)
    s, days = fetch_stats(), fetch_calendar()
    (OUT / "terminal_stats.svg").write_text(stats_svg(s, days), encoding="utf-8")
    (OUT / "terminal_banner.svg").write_text(banner_svg(), encoding="utf-8")
    (OUT / "terminal_about.svg").write_text(about_svg(), encoding="utf-8")
    (OUT / "social_linkedin.svg").write_text(pill_svg("linkedin", BLUE), encoding="utf-8")
    (OUT / "social_email.svg").write_text(pill_svg("email", AMBER), encoding="utf-8")
    (OUT / "terminal_skills.svg").write_text(skills_svg(), encoding="utf-8")
    (OUT / "terminal_projects.svg").write_text(projects_svg(), encoding="utf-8")
    for (name, _, _), col in zip(PROJECTS, [CYAN, MAGENTA, GREEN]):
        (OUT / f"link_{name.lower()}.svg").write_text(pill_svg(name, col), encoding="utf-8")
    print("ok", {k: v for k, v in s.items() if k != "langs"}, s["langs"].most_common(5), len(days))


if __name__ == "__main__":
    main()
