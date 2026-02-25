#!/usr/bin/env python3
# Generates ONE new HTML post using posts/topics.json (rotating through topics),
# rebuilds posts/index.json from posts/html/*.html (HTML-only),
# and injects the footer Subscribe form (Sheet.best).

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
SHEETBEST_URL   = os.getenv("SHEETBEST_URL", "").strip()

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
        log(f"[init] Created {INDEX_PATH}")
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
        except Exception:
            i = 0
    else:
        i = 0
    return 0 if i < 0 or i >= total else i

def bump_index(i:int,total:int):
    STATE.write_text(json.dumps({"next_index": (i+1)%total}, indent=2), encoding="utf-8")
    log(f"[topic] next_index -> {(i+1)%total}")

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

# ====== Subscribe block ======
def subscribe_block():
    url_js = json.dumps(SHEETBEST_URL or "")
    note = "" if SHEETBEST_URL else "<div style='color:#ef4444;font-size:12px;margin-top:6px'>Subscribe service not configured.</div>"
    return f"""
<section class="container" style="max-width:1080px;margin:24px auto 8px;padding:0 16px;">
<form id="subscribe-form" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
<label for="sub-email" style="font-weight:600;">Subscribe for new posts:</label>
<input id="sub-email" type="email" required placeholder="you@example.com"
style="flex:1;min-width:220px;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px"/>
<button type="submit" style="padding:10px 14px;border-radius:10px;background:#e63946;color:#fff;border:0;cursor:pointer;">
Subscribe
</button>
<span id="sub-msg" style="font-size:13px;color:#6b7280;"></span>
</form>
{note}
</section>
"""

# ====== HTML wrapper ======
def wrap_html(title:str, excerpt:str, body_html:str)->str:
    year = datetime.date.today().year
    title_esc   = html_lib.escape(title, quote=True)
    excerpt_esc = html_lib.escape(excerpt, quote=True)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title_esc} — Discount Smokes</title>
<meta name="description" content="{excerpt_esc}"/>
<meta name="excerpt" content="{excerpt_esc}"/>
</head>
<body>
<main>
<article class="post">
{body_html}
</article>
</main>
{subscribe_block()}
<footer>© {year} Discount Smokes. All Rights Reserved.</footer>
</body>
</html>"""

# ====== 600–800 WORD SALES-FOCUSED FALLBACK ======
def gen_fallback_post(title: str, idea: str, category: str) -> str:
    store = "Discount Smokes"
    address = "1130 Westport Rd, Kansas City, MO 64111"

    return textwrap.dedent(f"""
Excerpt: Looking for {idea} in Westport, Kansas City? Here’s what you should know before you buy.

## {title}

If you're shopping for **{idea}** in Kansas City, especially around Westport, you’ve probably noticed there are a lot of options available. Online listings can be overwhelming, and product descriptions don’t always tell the full story. That’s why many local customers prefer to stop by **{store}** in person — to compare options, ask questions, and make a confident decision.

At our Westport location, we focus on helping customers find the right match for their preferences and budget. We keep our approach simple: clear information, helpful guidance, and straightforward answers. No hype — just practical advice.

### Why Buying In-Store Makes a Difference

Shopping locally gives you advantages that online stores simply can’t offer:

- You can compare products side by side.
- You can ask about what’s popular right now.
- You can see size, packaging, and presentation in person.
- You avoid waiting for shipping or dealing with returns.

Most customers appreciate being able to make a decision immediately instead of guessing from a product page.

### What to Consider Before You Buy {idea}

When selecting {idea}, here are a few important factors:

1. **Quality & Packaging** – Clean presentation and consistent packaging often reflect attention to detail.
2. **Size & Format** – Choose something that fits your usage and comfort level.
3. **Value for Money** – The most expensive option isn’t always the best one.
4. **Availability** – Inventory changes regularly, so it helps to check what’s in stock.

If you’re unsure what fits your needs best, our team can guide you quickly. Just explain what you’re looking for and what you want to avoid.

### Local Kansas City Advantage

Being located at **{address}**, we serve customers from all over Kansas City. Westport shoppers often stop by while they’re already in the area, making it convenient and quick.

If you're planning to visit specifically for {idea}, calling ahead can save time and confirm availability. That way you know exactly what to expect when you walk in.

### Simple Tips That Help Customers

- Bring a photo if you’re replacing something specific.
- Ask what’s new this week — inventory rotates often.
- Compare two options before deciding.
- If you’re new, start simple and adjust later.

These small steps make a big difference in choosing the right product.

### Visit Discount Smokes Today

If you’re in Kansas City and looking for **{idea}**, stop by and see what’s available today. We’re happy to answer questions and help you compare options without pressure.

📍 {address}  
📞 Call to check availability before visiting  
🗺 Easy access in the heart of Westport  

**21+ only. Valid ID required for nicotine purchases.**
""").strip()

# ====== OpenAI WITH AUTO FALLBACK ======
def gen_with_openai_or_fallback(prompt: str, title: str, idea: str, category: str) -> str:
    if DRY_RUN or not OPENAI_API_KEY:
        warn("[openai] fallback mode")
        return gen_fallback_post(title, idea, category)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "Write a 600-800 word SEO blog for Discount Smokes in Kansas City. Avoid medical claims."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=90)
        if r.status_code != 200:
            warn("[openai] non-200 -> fallback")
            return gen_fallback_post(title, idea, category)
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        warn("[openai] exception -> fallback")
        return gen_fallback_post(title, idea, category)

# ====== Generate One Post ======
def generate_one_post():
    ensure_structure()
    topics = read_topics()
    today  = datetime.date.today()

    i = get_next_index(len(topics))
    topic = topics[i]

    category = topic.get("category", "General")
    title = topic.get("title") or topic.get("idea") or "Store update"
    idea  = topic.get("idea") or title

    log(f"[topic] total={len(topics)} current_index={i}")

    content_prompt = f"""
Write a 600-800 word blog post about {idea}.
Friendly tone. Local to Kansas City Westport.
Avoid medical claims.
Start with Excerpt:
"""

    content_md = gen_with_openai_or_fallback(content_prompt, title, idea, category)

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
        "excerpt": excerpt,
        "category": category
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
            "excerpt": "",
            "category": "General"
        })

    entries.sort(key=lambda e: e["date"], reverse=True)
    INDEX_PATH.write_text(json.dumps({"posts": entries}, indent=2), encoding="utf-8")
    log("[rebuild] done")

# ====== Main ======
def main():
    log("[env] OPENAI_KEY=" + str(bool(OPENAI_API_KEY)))
    ensure_structure()
    generate_one_post()
    rebuild_index()
    log("[done] success")

if __name__ == "__main__":
    main()
