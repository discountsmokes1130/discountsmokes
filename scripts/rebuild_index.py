#!/usr/bin/env python3
# Auto-generates ONE new HTML post from posts/topics.json
# Uses OpenAI if available, otherwise FREE long-form fallback (600–800 words)
# Rebuilds posts/index.json from posts/html/*.html

import os, json, datetime, re, pathlib, textwrap, sys, traceback, random
import html as html_lib

try:
    import requests
    import markdown as md
except Exception:
    print("ERROR: missing deps. Ensure 'requests' and 'markdown' are installed.", file=sys.stderr)
    raise

# ================= CONFIG =================
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DRY_RUN         = os.getenv("DRY_RUN", "")

ROOT       = pathlib.Path(".")
POSTS_DIR  = ROOT / "posts"
HTML_DIR   = POSTS_DIR / "html"
INDEX_PATH = POSTS_DIR / "index.json"
TOPICS     = POSTS_DIR / "topics.json"
STATE      = POSTS_DIR / ".topic_state.json"

# ================= LOGGING =================
def log(msg): print(msg, flush=True)
def warn(msg): print(msg, file=sys.stderr, flush=True)

# ================= SETUP =================
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
        raise SystemExit("ERROR: topics.json has no topics.")
    return t

def get_next_index(total):
    if STATE.exists():
        try:
            return int(json.loads(STATE.read_text()).get("next_index", 0))
        except:
            return 0
    return 0

def bump_index(i, total):
    STATE.write_text(json.dumps({"next_index": (i+1)%total}, indent=2))

def slugify(s):
    return re.sub(r"[^a-z0-9]+","-",s.lower()).strip("-")

def unique_html_path(date, slug):
    base = HTML_DIR / f"{date:%Y-%m-%d}-{slug}.html"
    if not base.exists(): return base
    i = 1
    while True:
        p = HTML_DIR / f"{date:%Y-%m-%d}-{slug}-{i}.html"
        if not p.exists(): return p
        i += 1

def markdown_to_html(md_text):
    return md.markdown(md_text, extensions=["extra"])

# ================= FREE FALLBACK (600–800 words) =================
def gen_fallback_post(title, idea, category):
    random.seed(f"{datetime.date.today()}::{title}")

    store_name = "Discount Smokes"
    address = "1130 Westport Rd, Kansas City, MO 64111"
    phone_display = "(816) 712-1130"
    phone_link = "+18167121130"
    directions = "https://www.google.com/maps?q=1130+Westport+Rd,+Kansas+City,+MO+64111"

    hooks = [
        f"If you're shopping in Westport and looking for the right **{idea}**, this guide is for you.",
        f"Customers in Kansas City regularly ask us about **{idea}** — here’s what matters most.",
        f"Choosing the right **{idea}** doesn’t have to be complicated. Let’s break it down.",
        f"Looking for quality **{idea}** near Westport? Here’s a practical, local guide."
    ]

    hook = random.choice(hooks)

    tips = random.sample([
        "Ask what’s new this week — inventory rotates often.",
        "Compare options side by side before deciding.",
        "Start simple if you're trying something new.",
        "Call ahead to confirm availability.",
        "Bring a photo if replacing something."
    ], 3)

    return f"""
Excerpt: {hook} Visit {store_name} in Westport for friendly service and updated inventory.

## {title}

{hook}

At {store_name}, located in the heart of Westport, Kansas City, we help customers make confident buying decisions every day. Whether you're new or experienced, understanding your options makes a big difference.

### Why People Choose Discount Smokes

Our customers value:

- Wide product selection
- Fair everyday pricing
- Knowledgeable and helpful staff
- Easy in-and-out Westport location

When it comes to **{idea}**, availability can change quickly. Seeing products in person helps you compare quality, design, and price before making a decision.

### What to Look For

Here are smart things to check when shopping for **{idea}**:

- Brand reliability and build quality
- Size and packaging differences
- Price-to-value comparison
- Current in-store availability

If you're unsure, our staff will walk you through options without pressure.

### Smart Shopping Tips

- {tips[0]}
- {tips[1]}
- {tips[2]}

### Local Convenience

We’re located at **{address}**, making it easy to stop by if you're already in Westport. Many customers combine their visit with dining or errands nearby.

Buying local means better service, real-time answers, and no waiting for shipping.

### Visit or Call Today

📍 Address: {address}  
📞 Call Now: [{phone_display}](tel:{phone_link})  
🗺 Directions: [Open in Google Maps]({directions})

Stop in today and explore your options.

**21+ only. Valid ID required for nicotine purchases.**
""".strip()

# ================= OPENAI OR FALLBACK =================
def generate_content(prompt, title, idea, category):
    if DRY_RUN or not OPENAI_API_KEY:
        warn("[fallback] Using FREE fallback content.")
        return gen_fallback_post(title, idea, category)

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role":"system","content":"You write SEO-friendly, persuasive retail blog posts."},
                    {"role":"user","content":prompt}
                ],
                "temperature":0.7,
                "max_tokens":900
            },
            timeout=90
        )

        if r.status_code == 429:
            warn("[openai] quota exceeded -> fallback mode")
            return gen_fallback_post(title, idea, category)

        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        warn(f"[openai error] {e} -> fallback")
        return gen_fallback_post(title, idea, category)

# ================= HTML WRAPPER =================
def wrap_html(title, excerpt, body_html):
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
<main class="container">
<article class="post">
<h1>{html_lib.escape(title)}</h1>
{body_html}
</article>
</main>
<footer>© {year} Discount Smokes</footer>
</body>
</html>"""

# ================= GENERATE POST =================
def generate_one_post():
    ensure_structure()
    topics = read_topics()
    today = datetime.date.today()

    i = get_next_index(len(topics))
    topic = topics[i]

    title = topic.get("title") or topic.get("idea") or "Store Update"
    idea = topic.get("idea") or title
    category = topic.get("category","General")

    prompt = f"Write a 700-word persuasive retail blog post about {idea}."

    content_md = generate_content(prompt, title, idea, category)

    m = re.search(r"Excerpt:\s*(.+)", content_md)
    excerpt = m.group(1) if m else "Visit Discount Smokes in Westport."

    slug = slugify(title)
    html_path = unique_html_path(today, slug)

    html_path.write_text(
        wrap_html(title, excerpt, markdown_to_html(content_md)),
        encoding="utf-8"
    )

    idx = json.loads(INDEX_PATH.read_text())
    idx["posts"].insert(0,{
        "title": title,
        "date": str(today),
        "url": f"posts/html/{html_path.name}",
        "excerpt": excerpt,
        "category": category
    })
    INDEX_PATH.write_text(json.dumps(idx, indent=2))

    bump_index(i, len(topics))
    log(f"[generated] {html_path}")

# ================= REBUILD INDEX =================
def rebuild_index():
    entries=[]
    for file in HTML_DIR.glob("*.html"):
        name=file.name
        date=name.split("-")[0]
        entries.append({
            "title": name.replace(".html","").split("-",3)[-1].replace("-"," ").title(),
            "date": date,
            "url": f"posts/html/{name}",
            "excerpt": "Visit Discount Smokes in Westport.",
            "category":"General"
        })
    entries.sort(key=lambda e:e["date"], reverse=True)
    INDEX_PATH.write_text(json.dumps({"posts":entries},indent=2))
    log("[index rebuilt]")

# ================= MAIN =================
def main():
    try:
        generate_one_post()
        rebuild_index()
        log("[done]")
    except Exception as e:
        warn(f"[fatal] {e}")
        warn(traceback.format_exc())
        raise SystemExit(1)

if __name__ == "__main__":
    main()
