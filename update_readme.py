#!/usr/bin/env python3
"""Regenerate the profile README's live sections.

Two sections are generated between markers in README.md:

    <!-- LIVE_PROJECTS_START --> ... <!-- LIVE_PROJECTS_END -->
    <!-- LIVE_LANGS_START --> ... <!-- LIVE_LANGS_END -->
    <!-- UNIFIED_LANG_CARD_START --> ... <!-- UNIFIED_LANG_CARD_END -->

The projects showcase is a ranked, filtered list, not a dump of every repo:

  * worthy  - it has a real description (its own, or the first real sentence of
              its README), it is not empty, and it has been committed to in the
              last 90 days. Anything else is hidden.
  * ranked  - by commits in the last 30 days first, then 90 days, then how
              recently it was pushed. A new project that you actually work on
              rises to the top on its own; a dormant one drops off.

Overrides live in projects.json:

    {"hide": ["repo-a"], "pin": ["repo-b"], "max_cards": 6,
     "stale_days": 180, "min_size_kb": 20, "min_description": 25}

`pin` shows a repo first and skips the worthiness test; `hide` removes it
permanently. Both are by repository name, case-insensitive.

Standard library only - this runs on a bare Actions runner.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "mildfriend3-blip")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = os.environ.get("README_PATH", "README.md")
CONFIG_PATH = os.environ.get("PROJECTS_CONFIG", "projects.json")

HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": USERNAME}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

DEFAULTS = {
    "hide": [],
    "pin": [],
    "max_cards": 6,
    "stale_days": 180,
    "min_size_kb": 20,
    "min_description": 25,
}

# --------------------------------------------------------------------------- #
# theme
# --------------------------------------------------------------------------- #
FG = "00FF41"
DIM = "0d1117"

# Inline <img> badges, not markdown: these sit inside an HTML table, where
# GitHub does not parse markdown at all. Markdown here renders as literal text.
LANG_BADGES = {
    "python": ("Python", "python"),
    "typescript": ("TypeScript", "typescript"),
    "javascript": ("JavaScript", "javascript"),
    "react": ("React", "react"),
    "next.js": ("Next.js", "nextdotjs"),
    "node.js": ("Node.js", "nodedotjs"),
    "postgresql": ("PostgreSQL", "postgresql"),
    "supabase": ("Supabase", "supabase"),
    "mongodb": ("MongoDB", "mongodb"),
    "tailwind": ("Tailwind", "tailwindcss"),
    "html": ("HTML5", "html5"),
    "css": ("CSS3", "css3"),
    "kotlin": ("Kotlin", "kotlin"),
    "java": ("Java", "openjdk"),
    "go": ("Go", "go"),
    "rust": ("Rust", "rust"),
    "c++": ("C++", "cplusplus"),
    "shell": ("Shell", "gnubash"),
    "dockerfile": ("Docker", "docker"),
    "open policy agent": ("OPA", "openpolicyagent"),
    "procfile": ("Heroku", "heroku"),
    "makefile": ("Make", "gnu"),
    "powershell": ("PowerShell", "powershell"),
    "c": ("C", "c"),
    "c#": ("C#", "dotnet"),
    "sql": ("SQL", "postgresql"),
}


def lang_badge(name):
    """An inline shield for one language, or None if it is not worth a badge."""
    key = name.lower()
    label, logo = LANG_BADGES.get(key, (name, None))
    label = urllib.parse.quote(label.replace("-", "--").replace(" ", "_"))
    logo_part = f"&logo={logo}" if logo else ""
    return (
        f'<img alt="{label}" src="https://img.shields.io/badge/{label}-{DIM}'
        f'?style=flat-square{logo_part}&logoColor={FG}" />'
    )


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# --------------------------------------------------------------------------- #
# github
# --------------------------------------------------------------------------- #
def github_get(path):
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        print(f"  ! {url} -> HTTP {exc.code}", file=sys.stderr)
        return None
    except Exception as exc:  # noqa: BLE001 - a single repo must not kill the run
        print(f"  ! {url} -> {type(exc).__name__}", file=sys.stderr)
        return None


def commits_since(repo, days):
    since = (datetime.now(timezone.utc) - timedelta_days(days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = github_get(f"/repos/{USERNAME}/{repo}/commits?since={since}&per_page=100")
    return len(data) if isinstance(data, list) else 0


def timedelta_days(days):
    from datetime import timedelta

    return timedelta(days=days)


def languages(repo):
    data = github_get(f"/repos/{USERNAME}/{repo}/languages")
    if not isinstance(data, dict) or not data:
        return []
    total = sum(v for v in data.values() if isinstance(v, (int, float))) or 1
    pairs = [(k, v * 100.0 / total) for k, v in data.items() if isinstance(v, (int, float))]
    return [k for k, _ in sorted(pairs, key=lambda p: -p[1])]


README_NOISE = re.compile(r"(!\[[^\]]*\]\([^)]*\))|(\[[^\]]*\]\([^)]*\))|(<[^>]+>)|(```.*?```)|(<!--.*?-->)", re.S)


def readme_summary(repo):
    """First real sentence of a repo's README, or '' if there is nothing usable."""
    data = github_get(f"/repos/{USERNAME}/{repo}/readme")
    if not isinstance(data, dict):
        return ""
    try:
        import base64

        text = base64.b64decode(data.get("content", "")).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    text = README_NOISE.sub(" ", text)
    text = re.sub(r"[#>*_`|]", " ", text)
    for line in text.splitlines():
        line = " ".join(line.split())
        if len(line) >= 45 and not line.lower().startswith(("http", "table of contents")):
            return line[:200].rstrip(" .") + "."
    return ""


# --------------------------------------------------------------------------- #
# ranking
# --------------------------------------------------------------------------- #
def days_since(iso):
    if not iso:
        return 10_000
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, (datetime.now(timezone.utc) - when).days)


def score(project):
    """Activity first: a project you commit to outranks an old one with a demo."""
    s = 0
    s += project["commits_30"] * 10
    s += project["commits_90"] * 3
    s += max(0, 30 - days_since(project["pushed_at"]))  # freshness, 0-30
    s += project["stars"] * 15
    s += 8 if project["homepage"] else 0
    s += min(len(project["description"]) // 20, 5)
    s += min(len(project["topics"]) * 2, 6)
    return s


def evaluate(repos, cfg):
    hide = {n.lower() for n in cfg["hide"]}
    pin = [n.lower() for n in cfg["pin"]]
    keep, dropped = [], []

    for repo in repos:
        name = repo["name"]
        low = name.lower()

        if low == USERNAME.lower():
            dropped.append((name, "profile repository"))
            continue
        if low in hide:
            dropped.append((name, "hidden in projects.json"))
            continue
        if repo.get("fork"):
            dropped.append((name, "fork"))
            continue
        if repo.get("archived") or repo.get("disabled"):
            dropped.append((name, "archived or disabled"))
            continue
        if repo.get("is_template"):
            dropped.append((name, "template"))
            continue

        pinned = low in pin
        size_kb = int(repo.get("size") or 0)
        if size_kb < cfg["min_size_kb"] and not pinned:
            dropped.append((name, f"only {size_kb} KB, nothing to show"))
            continue

        description = (repo.get("description") or "").strip()
        if len(description) < cfg["min_description"]:
            description = readme_summary(name)
        if len(description) < cfg["min_description"] and not pinned:
            dropped.append((name, "no description and no usable README opening"))
            continue

        c30 = commits_since(name, 30)
        c90 = commits_since(name, 90)

        if c90 == 0 and not pinned:
            dropped.append((name, "no commits in 90 days"))
            continue
        if days_since(repo.get("pushed_at")) > cfg["stale_days"] and not pinned:
            dropped.append((name, f"untouched for {days_since(repo.get('pushed_at'))} days"))
            continue

        homepage = (repo.get("homepage") or "").strip()
        if homepage and not homepage.startswith("http"):
            homepage = "https://" + homepage

        keep.append(
            {
                "name": name,
                "url": repo["html_url"],
                "description": description or "No description yet.",
                "homepage": homepage,
                "stars": int(repo.get("stargazers_count") or 0),
                "topics": repo.get("topics") or [],
                "pushed_at": repo.get("pushed_at"),
                "commits_30": c30,
                "commits_90": c90,
                "languages": languages(name),
                "pinned": pinned,
                "score": score(
                    {
                        "commits_30": c30,
                        "commits_90": c90,
                        "pushed_at": repo.get("pushed_at"),
                        "stars": int(repo.get("stargazers_count") or 0),
                        "homepage": homepage,
                        "description": description or "",
                        "topics": repo.get("topics") or [],
                    }
                ),
            }
        )

    def order(p):
        pin_index = pin.index(p["name"].lower()) if p["name"].lower() in pin else 99
        return (pin_index, -p["score"], -(p["commits_30"]))

    keep.sort(key=order)
    return keep, dropped


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def render_card(p):
    badges = " ".join(b for b in (lang_badge(l) for l in p["languages"][:3]) if b)
    stats = (
        f'<img alt="last commit" src="https://img.shields.io/github/last-commit/{USERNAME}/{p["name"]}'
        f'?style=flat-square&color={FG}&labelColor={DIM}&label=Last%20Commit" /> '
        f'<img alt="commit activity" src="https://img.shields.io/github/commit-activity/m/{USERNAME}/{p["name"]}'
        f'?style=flat-square&color=2ea043&labelColor={DIM}&label=Commits" /> '
        f'<img alt="stars" src="https://img.shields.io/github/stars/{USERNAME}/{p["name"]}'
        f'?style=flat-square&color=10B981&labelColor={DIM}" />'
    )
    buttons = (
        f'<a href="{p["url"]}"><img alt="source code" '
        f'src="https://img.shields.io/badge/Source_Code-{DIM}?style=for-the-badge&logo=github'
        f'&logoColor={FG}&labelColor={DIM}&color=2ea043" /></a>'
    )
    if p["homepage"]:
        buttons = (
            f'<a href="{esc(p["homepage"])}"><img alt="live demo" '
            f'src="https://img.shields.io/badge/Live_Demo-{FG}?style=for-the-badge&logo=vercel'
            f'&logoColor={DIM}&labelColor={FG}&color={FG}" /></a> ' + buttons
        )
    return f"""    <td width="50%" valign="top">
      <h3><a href="{p["url"]}">{esc(p["name"])}</a></h3>
      <p>{esc(p["description"])}</p>
      <p>{badges}</p>
      <p>{stats}</p>
      <p>{buttons}</p>
    </td>"""


def render_projects(projects):
    if not projects:
        return (
            "_No project currently passes the showcase test: a real description and a "
            "commit in the last 90 days. Push something and it appears here._"
        )

    rows = ['<table>']
    for i in range(0, len(projects), 2):
        rows.append("  <tr>")
        pair = projects[i : i + 2]
        for p in pair:
            rows.append(render_card(p))
        if len(pair) == 1:
            rows.append(
                f"""    <td width="50%" valign="top">
      <h3><a href="https://github.com/{USERNAME}?tab=repositories">All repositories</a></h3>
      <p>The full list, including the ones this showcase hides: archived, dormant, and repositories without a description.</p>
      <p><a href="https://github.com/{USERNAME}?tab=repositories"><img alt="all repositories" src="https://img.shields.io/badge/Browse_All-{DIM}?style=for-the-badge&logo=github&logoColor={FG}&labelColor={DIM}" /></a></p>
    </td>"""
            )
        rows.append("  </tr>")
    rows.append("</table>")
    rows.append("")
    rows.append(
        f"<sub>Ranked by commits in the last 30 days, then 90 days, then recency. "
        f"Last rebuilt {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}.</sub>"
    )
    return "\n".join(rows)


# --------------------------------------------------------------------------- #
# language sections (unchanged behaviour, kept for the existing markers)
# --------------------------------------------------------------------------- #
def calculate_language_percentages(repos):
    totals = {}
    valid = [
        r
        for r in repos
        if r["name"].lower() != USERNAME.lower() and not r.get("archived", False)
    ]
    for index, repo in enumerate(valid):
        data = github_get(f"/repos/{USERNAME}/{repo['name']}/languages")
        if not isinstance(data, dict) or not data:
            continue
        total = sum(data.values())
        if total == 0:
            continue
        multiplier = 3.5 if index < 3 else 1.0
        for lang, count in data.items():
            if lang == "Jupyter Notebook":
                lang = "Python"
            if lang in {"HTML", "CSS"}:
                continue
            totals[lang] = totals.get(lang, 0.0) + (count / total) * 100.0 * multiplier

    grand = sum(totals.values())
    if grand == 0:
        return {"Python": 100.0}
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    return {lang: round(v / grand * 100, 1) for lang, v in ranked}


def build_live_languages(percentages):
    badges = []
    for lang, pct in list(percentages.items())[:6]:
        safe = urllib.parse.quote(lang)
        badges.append(
            f'<img alt="{esc(lang)}" src="https://img.shields.io/badge/{safe}-{pct}%25-{FG}'
            f'?style=for-the-badge&labelColor={DIM}&color=2ea043" />'
        )
    return '<p align="center">\n  ' + "\n  ".join(badges) + "\n</p>"


def build_unified_card(percentages):
    lines = ['<div align="center">', '  <table width="100%">', "    <tr>"]
    items = list(percentages.items())[:6]
    mid = (len(items) + 1) // 2
    for column in (items[:mid], items[mid:]):
        lines.append('      <td width="50%" valign="top">')
        for lang, pct in column:
            filled = int(pct / 10)
            bar = "🟩" * filled + "⬛" * (10 - filled)
            lines.append(f"        <b>{esc(lang)}</b> ({pct}%)<br>{bar}<br><br>")
        lines.append("      </td>")
    lines.append("    </tr>")
    lines.append("  </table>")
    lines.append("</div>")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def replace_section(content, marker, block):
    pattern = rf"(<!-- {marker}_START -->).*?(<!-- {marker}_END -->)"
    if not re.search(pattern, content, flags=re.S):
        print(f"  ! marker {marker} not found in README, skipped", file=sys.stderr)
        return content
    return re.sub(pattern, lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", content, flags=re.S)


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    return cfg


def main():
    cfg = load_config()
    repos = github_get(f"/users/{USERNAME}/repos?per_page=100&sort=pushed") or []
    if not isinstance(repos, list):
        print("could not list repositories", file=sys.stderr)
        return 1

    projects, dropped = evaluate(repos, cfg)
    projects = projects[: int(cfg["max_cards"])]

    print(f"repositories seen: {len(repos)}")
    for p in projects:
        print(f"  shown  {p['name']:<34} score={p['score']:<5} commits30={p['commits_30']:<3} commits90={p['commits_90']}")
    for name, why in dropped:
        print(f"  hidden {name:<34} {why}")

    percentages = calculate_language_percentages(repos)

    with open(README, encoding="utf-8") as fh:
        readme = fh.read()
    readme = replace_section(readme, "LIVE_PROJECTS", render_projects(projects))
    readme = replace_section(readme, "LIVE_LANGS", build_live_languages(percentages))
    readme = replace_section(readme, "UNIFIED_LANG_CARD", build_unified_card(percentages))
    with open(README, "w", encoding="utf-8") as fh:
        fh.write(readme)

    print(f"README rebuilt: {len(projects)} project card(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
