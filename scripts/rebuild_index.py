#!/usr/bin/env python3
# Generates ONE new HTML post using posts/topics.json (rotating through topics),
# rebuilds posts/index.json from posts/html/*.html (HTML-only).

import os, json, datetime, re, pathlib, textwrap, sys
import html as html_lib
import traceback

try:
    import requests
    import markdown as md
except Exception:
    print("ERROR: missing deps. Ensure 'requests' and 'markdown' are installed.", file=sys.stderr)
    raise

# ====== Config / Env ======
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DRY_RUN         = os.getenv("DRY_RUN", "")

ROOT       = pathlib.Path(".")
POSTS_DIR  = ROOT / "posts"
HTML_DIR   = POSTS_DIR / "html"
INDEX_PATH = POSTS_DIR / "index.json"
TOPICS     = POSTS_DIR / "topics.json"
STATE      = POSTS_DIR / ".topic_state.json"

# ====== Logging ======
def log(msg: str):
    print(msg, flush=True)

def warn(msg: str):
    print(msg, file=sys.stderr, flush=True)

# ====== Utilities ======
def ensure_structure():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text(json.dumps({"posts": []}, indent=2), encoding="utf-8")
    if not TOPICS.exists():
        raise SystemExit("ERROR: posts/topics.json not found.")

def read_topics():
    data = json.loads(TOPICS.read_text(encoding="utf-8"))
    t = data.get("topics", [])
    if not t:
        raise SystemExit("ERROR: posts/topics.json has no 'topics' array.")
    return t

def get_next_index(total:int)->int:
    if STATE.exists():
        try:
            i = int(json.loads(STATE.read_text(encoding="utf-8")).get("next_index", 0))
        except:
            i = 0
    else:
        i = 0
    return 0 if i < 0 or i >= total else i

def bump_index(i:int,total:int):
    nxt = (i+1) % total
    STATE.write_text(json.dumps({"next_index": nxt}, indent=2), encoding="utf-8")
    log(f"[topic] next_index -> {nxt}")

def slugify(s:str)->str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+","-",s).strip("-")
    return s or "post"

def unique_html_path(date: datetime.date, slug: str) -> pathlib.Path:
    base = HTML_DIR / f"{date:%Y-%m-%d}-{slug}.html"
    if not base.exists():
        return base
    i = 1
    while True:
        p = HTML_DIR / f"{date:%Y-%m-%d}-{slug}-{i}.html"
        if not p.exists():
            return p
        i += 1

def markdown_to_html(md_text:str)->str:
    return md.markdown(md_text, extensions=["extra"])

# ====== HTML Wrapper (Same Website Look) ======
def wrap_html(title:str, excerpt:str, body_html:str)->str:
    year = datetime.date.today().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html_lib.escape(title)} — Discount Smokes</title>
<meta name="description" content="{html_lib.escape(excerpt)}"/>
<link rel="stylesheet" href="../../styles.css"/>
</head>
<body>
<header>
  <div class="container header-inner">
    <div class="brand">
      <a href="../../index.html">
        <h1 class="site-title">Discount Smokes</h1>
      </a>
    </div>
    <div class="top-contact">
      <a href="../../index.html">🏠 Home</a>
      <a href="../../blog.html">📰 Blog</a>
      <a href="tel:+18167121130">📞 Call Now</a>
    </div>
  </div>
</header>

<main class="container">
  <article class="post">
    {body_html}
  </article>
</main>

<footer>© {year} Discount Smokes</footer>
</body>
</html>"""

# ====== 600–800 WORD FALLBACK (No OpenAI Required) ======
def gen_fallback_post(title: str, idea: str) -> str:
    return textwrap.dedent(f"""
Excerpt: Looking for {idea} in Westport, Kansas City? Here’s what to know before you buy.

## {title}

If you're shopping for **{idea}** in Kansas City, especially around Westport, you’ve likely noticed there are plenty of choices. The key is finding something that fits your style, budget, and expectations.

At Discount Smokes, we help customers compare options in person so they can make confident decisions. Seeing products side-by-side and asking questions often makes the process easier and faster.

### Why In-Store Shopping Helps

Buying locally allows you to:
- Compare multiple options instantly  
- Ask about what’s popular this week  
- Confirm availability immediately  
- Avoid shipping delays  

Most customers prefer to see and compare items rather than guess from online photos.

### What to Look For

When choosing {idea}, consider:
1. Quality & packaging  
2. Size or format  
3. Price range  
4. Current stock availability  

If you're unsure, simply explain what you're looking for and we’ll help narrow down options quickly.

### Westport Location Advantage

We’re located at **1130 Westport Rd, Kansas City, MO 64111**, making it easy to stop by if you’re already in the area. Inventory changes often, so calling ahead can save time.

Visit Discount Smokes today and let us help you choose confidently.

21+ only. Valid ID required for nicotine purchases.
""").strip()

# ====== OpenAI With Fallback ======
def gen_with_openai_or_fallback(prompt: str, title: str, idea: str) -> str:
    if DRY_RUN or not OPENAI_API_KEY:
        return gen_fallback_post(title, idea)

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role":"system","content":"Write a 600-800 word SEO blog for Discount Smokes. Avoid medical claims."},
                    {"role":"user","content":prompt}
                ],
                "temperature":0.7,
                "max_tokens":1000
            },
            timeout=90
        )

        if r.status_code != 200:
            warn("[openai] fallback triggered")
            return gen_fallback_post(title, idea)

        return r.json()["choices"][0]["message"]["content"]

    except:
        warn("[openai] exception fallback")
        return gen_fallback_post(title, idea)

# ====== Generate One Post ======
def generate_one_post():
    ensure_structure()
    topics = read_topics()
    today  = datetime.date.today()

    i = get_next_index(len(topics))
    topic = topics[i]

    title = topic.get("title") or topic.get("idea") or "Store update"
    idea  = topic.get("idea") or title

    prompt = f"""
Write a 600-800 word blog post about {idea}.
Friendly tone. Local to Kansas City Westport.
Avoid medical claims.
Start with Excerpt:
"""

    content_md = gen_with_openai_or_fallback(prompt, title, idea)

    m = re.search(r"Excerpt:\s*(.+)", content_md, re.IGNORECASE)
    excerpt = m.group(1).strip() if m else "Visit Discount Smokes in Westport."

    body_html = f"<h1>{html_lib.escape(title)}</h1>\n" + markdown_to_html(content_md)

    slug = slugify(title)
    html_path = unique_html_path(today, slug)
    html_path.write_text(wrap_html(title, excerpt, body_html), encoding="utf-8")

    idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    idx.setdefault("posts", [])
    idx["posts"].insert(0, {
        "title": title,
        "date": f"{today:%Y-%m-%d}",
        "url": f"posts/html/{html_path.name}",
        "excerpt": excerpt
    })
    INDEX_PATH.write_text(json.dumps(idx, indent=2), encoding="utf-8")

    bump_index(i, len(topics))
    log(f"[generate] Wrote {html_path}")

# ====== Rebuild Index ======
def rebuild_index():
    files = sorted(list(HTML_DIR.glob("*.html")))
    entries = []

    for file in files:
        name = file.name
        date_iso = name[:10]
        html = file.read_text(encoding="utf-8", errors="replace")
        title_match = re.search(r"<h1>(.*?)</h1>", html)
        title = title_match.group(1) if title_match else name

        entries.append({
            "title": title,
            "date": date_iso,
            "url": f"posts/html/{name}",
            "excerpt": ""
        })

    entries.sort(key=lambda e: e["date"], reverse=True)
    INDEX_PATH.write_text(json.dumps({"posts": entries}, indent=2), encoding="utf-8")
    log("[rebuild] done")

# ====== Main ======
def main():
    ensure_structure()
    generate_one_post()
    rebuild_index()
    log("[done] success")

if __name__ == "__main__":
    main()
