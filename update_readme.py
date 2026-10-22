import os
import re
import urllib.request
import json
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "mildfriend3-blip")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {"Accept": "application/vnd.github.v3+json", "User-Agent": USERNAME}
if TOKEN:
    HEADERS["Authorization"] = f"token {TOKEN}"

TECH_BADGES = {
    "python": "![Python](https://img.shields.io/badge/Python-0d1117?style=flat-square&logo=python&logoColor=00FF41)",
    "typescript": "![TypeScript](https://img.shields.io/badge/TypeScript-0d1117?style=flat-square&logo=typescript&logoColor=00FF41)",
    "javascript": "![JavaScript](https://img.shields.io/badge/JavaScript-0d1117?style=flat-square&logo=javascript&logoColor=00FF41)",
    "react": "![React](https://img.shields.io/badge/React-0d1117?style=flat-square&logo=react&logoColor=00FF41)",
    "nextjs": "![Next.js](https://img.shields.io/badge/Next.js-0d1117?style=flat-square&logo=nextdotjs&logoColor=00FF41)",
    "nodejs": "![Node.js](https://img.shields.io/badge/Node.js-0d1117?style=flat-square&logo=nodedotjs&logoColor=00FF41)",
    "postgresql": "![PostgreSQL](https://img.shields.io/badge/PostgreSQL-0d1117?style=flat-square&logo=postgresql&logoColor=00FF41)",
    "postgres": "![PostgreSQL](https://img.shields.io/badge/PostgreSQL-0d1117?style=flat-square&logo=postgresql&logoColor=00FF41)",
    "supabase": "![Supabase](https://img.shields.io/badge/Supabase-0d1117?style=flat-square&logo=supabase&logoColor=00FF41)",
    "mongodb": "![MongoDB](https://img.shields.io/badge/MongoDB-0d1117?style=flat-square&logo=mongodb&logoColor=00FF41)",
    "tailwindcss": "![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-0d1117?style=flat-square&logo=tailwindcss&logoColor=00FF41)",
    "html": "![HTML5](https://img.shields.io/badge/HTML5-0d1117?style=flat-square&logo=html5&logoColor=00FF41)",
    "css": "![CSS3](https://img.shields.io/badge/CSS3-0d1117?style=flat-square&logo=css3&logoColor=00FF41)",
    "kotlin": "![Kotlin](https://img.shields.io/badge/Kotlin-0d1117?style=flat-square&logo=kotlin&logoColor=00FF41)",
    "java": "![Java](https://img.shields.io/badge/Java-0d1117?style=flat-square&logo=openjdk&logoColor=00FF41)",
    "c++": "![C++](https://img.shields.io/badge/C++-0d1117?style=flat-square&logo=cplusplus&logoColor=00FF41)",
    "docker": "![Docker](https://img.shields.io/badge/Docker-0d1117?style=flat-square&logo=docker&logoColor=00FF41)",
}

def github_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def score_repo(repo):
    score = 0
    if repo.get("homepage") and repo["homepage"].strip():
        score += 50
    if repo.get("description") and len(repo["description"].strip()) > 10:
        score += 30
    score += repo.get("stargazers_count", 0) * 20
    score += len(repo.get("topics", [])) * 10
    
    pushed_at = repo.get("pushed_at")
    if pushed_at:
        pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        days_old = (datetime.now(timezone.utc) - pushed_dt).days
        score += max(0, 100 - days_old)
    return score

def get_repo_languages(repo_name):
    try:
        return github_get(f"https://api.github.com/repos/{USERNAME}/{repo_name}/languages")
    except Exception:
        return {}

def build_project_cards(repos):
    cards_md = []
    filtered = [
        r for r in repos
        if r["name"].lower() not in {USERNAME.lower(), "green-activity-log", "mildfriend", "kashishmalik"}
        and not r.get("archived", False)
    ]
    ranked = sorted(filtered, key=score_repo, reverse=True)[:6]

    if not ranked:
        return "_No public projects found yet._"

    cards_md.append('<table>')
    for i in range(0, len(ranked), 2):
        cards_md.append('  <tr>')
        for repo in ranked[i:i+2]:
            name = repo["name"]
            html_url = repo["html_url"]
            desc = repo.get("description") or "Active repository with live commit tracking and automated CI/CD pipelines."
            homepage = (repo.get("homepage") or "").strip()
            topics = [t.lower() for t in repo.get("topics", [])]
            langs_dict = get_repo_languages(name)
            repo_langs = [l.lower() for l in langs_dict.keys()]

            badges = []
            seen = set()
            for key in repo_langs + topics:
                if key in TECH_BADGES and key not in seen:
                    badges.append(TECH_BADGES[key])
                    seen.add(key)
            if not badges:
                badges.append(TECH_BADGES["python"])

            badges_str = " ".join(badges[:5])

            live_stats = (
                f'<img src="https://img.shields.io/github/last-commit/{USERNAME}/{name}?style=flat-square&color=00FF41&labelColor=0d1117&label=Last%20Commit" /> '
                f'<img src="https://img.shields.io/github/commit-activity/m/{USERNAME}/{name}?style=flat-square&color=2ea043&labelColor=0d1117&label=Commits" /> '
                f'<img src="https://img.shields.io/github/stars/{USERNAME}/{name}?style=flat-square&color=10B981&labelColor=0d1117" />'
            )

            buttons = f'<a href="{html_url}"><img src="https://img.shields.io/badge/💻_Source_Code-0d1117?style=for-the-badge&logo=github&logoColor=00FF41&labelColor=0d1117&color=2ea043" /></a>'
            if homepage:
                if not homepage.startswith("http"):
                    homepage = "https://" + homepage
                buttons = (
                    f'<a href="{homepage}"><img src="https://img.shields.io/badge/🟢_LIVE_DEMO-00FF41?style=for-the-badge&logo=vercel&logoColor=0d1117&labelColor=00FF41&color=00FF41" /></a> '
                    + buttons
                )

            card_html = f"""    <td width="50%" valign="top">
      <h3>🚀 <a href="{html_url}">{name}</a></h3>
      <p>{desc}</p>
      <p>{badges_str}</p>
      <p>{live_stats}</p>
      <p>{buttons}</p>
    </td>"""
            cards_md.append(card_html)

        if len(ranked[i:i+2]) == 1:
            cards_md.append('    <td width="50%"></td>')
        cards_md.append('  </tr>')
    cards_md.append('</table>')
    return "\n".join(cards_md)

def calculate_language_percentages(repos):
    totals = {}
    valid_repos = [
        r for r in repos
        if r["name"].lower() not in {USERNAME.lower(), "green-activity-log", "mildfriend"}
        and not r.get("archived", False)
    ]

    for index, repo in enumerate(valid_repos):
        langs = get_repo_languages(repo["name"])
        if not langs:
            continue
        repo_total_bytes = sum(langs.values())
        if repo_total_bytes == 0:
            continue

        recency_multiplier = 3.5 if index < 3 else 1.0

        for lang, bytes_count in langs.items():
            if lang == "Jupyter Notebook":
                lang = "Python"
            if lang in {"HTML", "CSS"}:
                continue
            repo_share = (bytes_count / repo_total_bytes) * 100.0 * recency_multiplier
            totals[lang] = totals.get(lang, 0.0) + repo_share

    total_score = sum(totals.values())
    if total_score == 0:
        return {"Python": 100.0}

    sorted_langs = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    percentages = {}
    for lang, score in sorted_langs:
        percentages[lang] = round((score / total_score) * 100, 1)
    return percentages

def build_live_languages(percentages):
    badges = []
    for lang, pct in list(percentages.items())[:6]:
        safe_lang = urllib.parse.quote(lang)
        badges.append(
            f'<img src="https://img.shields.io/badge/{safe_lang}-{pct}%25-00FF41?style=for-the-badge&labelColor=0d1117&color=2ea043" />'
        )
    return '<p align="center">\n  ' + '\n  '.join(badges) + '\n</p>'

def build_unified_card(percentages):
    """Generates a clean text/progress breakdown list to replace the conflicting third-party card."""
    lines = ['<div align="center">', '  <table width="100%">', '    <tr>']
    items = list(percentages.items())[:6]
    
    # Split into 2 columns for a clean look
    mid = (len(items) + 1) // 2
    for col_items in [items[:mid], items[mid:]]:
        lines.append('      <td width="50%" valign="top">')
        for lang, pct in col_items:
            bar_blocks = int(pct / 10)
            bar = "🟩" * bar_blocks + "⬛" * (10 - bar_blocks)
            lines.append(f'        <b>{lang}</b> ({pct}%)<br>{bar}<br><br>')
        lines.append('      </td>')
    lines.append('    </tr>')
    lines.append('  </table>')
    lines.append('</div>')
    return "\n".join(lines)

def replace_section(content, marker_name, new_block):
    pattern = rf"(<!-- {marker_name}_START -->).*?(<!-- {marker_name}_END -->)"
    replacement = f"\\1\n{new_block}\n\\2"
    return re.sub(pattern, replacement, content, flags=re.DOTALL)

def main():
    repos = github_get(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated")
    projects_md = build_project_cards(repos)
    percentages = calculate_language_percentages(repos)
    langs_md = build_live_languages(percentages)
    unified_card_md = build_unified_card(percentages)

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    readme = replace_section(readme, "LIVE_PROJECTS", projects_md)
    readme = replace_section(readme, "LIVE_LANGS", langs_md)
    readme = replace_section(readme, "UNIFIED_LANG_CARD", unified_card_md)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

if __name__ == "__main__":
    main()
