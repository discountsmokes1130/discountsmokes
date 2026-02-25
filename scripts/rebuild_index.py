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
SHEETBEST_URL   = os.getenv("SHEETBEST_URL", "").strip()  # Sheet.best subscribers endpoint

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
    if not TOPICS.is_file():
        raise SystemExit("ERROR: posts/topics.json is not a file.")

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

# ====== Subscribe block (footer) ======
def subscribe_block():
    # Embed the Sheet.best URL into pages at build time
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
<script>
  const SHEETBEST_URL = {url_js};

  async function subscribeHandler(e) {{
    e.preventDefault();
    const emailEl = document.getElementById('sub-email');
    const msg = document.getElementById('sub-msg');
    const email = (emailEl.value || '').trim();

    if (!SHEETBEST_URL) {{ msg.textContent='Subscribe service not configured.'; return; }}
    if (!email || !email.includes('@')) {{ msg.textContent='Please enter a valid email.'; return; }}

    msg.textContent='Saving...';
    try {{
      const payload = {{ email, date: new Date().toISOString(), source: location.pathname }};
      const res = await fetch(SHEETBEST_URL, {{
        method: 'POST',
        mode: 'cors',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});

      if (res.status >= 200 && res.status < 300) {{
        msg.textContent = 'Thank you for subscribe.';
        emailEl.value = '';
        return;
      }}

      const txt = await res.text().catch(() => '');
      console.error('Subscribe error:', res.status, txt);
      msg.textContent = 'Could not subscribe. Please try again.';
    }} catch (err) {{
      console.error('Subscribe failed:', err);
      msg.textContent = 'Could not subscribe. Please try again.';
    }}
  }}

  const form = document.getElementById('subscribe-form');
  if (form) form.addEventListener('submit', subscribeHandler);
</script>
"""

# ====== HTML wrapper for generated posts ======
def wrap_html(title:str, excerpt:str, body_html:str)->str:
    year = datetime.date.today().year
    title_esc   = html_lib.escape(title,   quote=True)
    excerpt_esc = html_lib.escape(excerpt, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title_esc} — Discount Smokes</title>
<meta name="description" content="{excerpt_esc}"/>
<meta name="excerpt" content="{excerpt_esc}"/>
<link rel="icon" href="../../assets/favicon.svg"/>
<style>
  body{{background:#fff;color:#111;margin:0;font-family:Arial,Helvetica,sans-serif}}
  header{{background:#000;color:#fff}}
  .container{{max-width:1080px;margin:0 auto;padding:0 16px}}
  .header-inner{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;padding:10px 0}}
  .brand a{{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none}}
  .logo{{height:42px;width:auto;display:block}}
  .site-title{{margin:0;font-size:18px;line-height:1;color:#fff}}
  .top-contact{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
  .top-contact a{{color:#fff;text-decoration:none;font-size:13px;padding:6px 10px;border-radius:8px}}
  .top-contact a:hover{{color:#e63946}}
  main.container{{padding:18px 0}}
  article.post{{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:18px;box-shadow:0 8px 18px rgba(0,0,0,.04)}}
  article.post h1{{margin-top:0}}
  article.post img{{max-width:100%;height:auto;border-radius:8px}}
  footer{{background:#000;color:#fff;text-align:center;padding:10px 0;margin-top:20px;font-size:14px}}
</style>
</head><body>
<header><div class="container header-inner">
  <div class="brand">
    <a href="../../index.html" aria-label="Home">
      <svg class="logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 360" role="img" aria-label="Discount Smokes logo">
        <defs><style>.t{{font:700 90px Arial, Helvetica, sans-serif}}</style></defs>
        <rect width="1080" height="360" fill="none"/>
        <text x="40" y="160" class="t" fill="#e63946">DISCOUNT</text>
        <text x="40" y="260" class="t" fill="#ffffff" fill-opacity="0.9">SMOKES</text>
      </svg>
      <h1 class="site-title">Discount Smokes</h1>
    </a>
  </div>
  <nav class="top-contact" aria-label="Primary">
    <a href="../../index.html">🏠 Home</a>
    <a href="mailto:1130.westport@gmail.com">✉️ Contact Us</a>
    <a href="tel:+18167121130">📞 Call Now</a>
    <a href="https://www.google.com/maps?q=1130+Westport+Rd,+Kansas+City,+MO+64111" target="_blank">📍 Directions</a>
    <a href="../../blog.html">📰 Blog</a>
  </nav>
</div></header>

<main class="container">
  <article class="post">
    {body_html}
  </article>
</main>

{subscribe_block()}

<footer>© {year} Discount Smokes. All Rights Reserved.</footer>
</body></html>"""

# ====== FREE fallback post generator (NO OpenAI needed) ======
def gen_fallback_post(title: str, idea: str, category: str) -> str:
    # Creates clean markdown with Excerpt + headings, 350-500 words-ish
    # No medical claims.
    return textwrap.dedent(f"""
    Excerpt: {title} — quick, friendly info from Discount Smokes in Westport (Kansas City).

    ## What to know
    Here’s a simple, no-stress breakdown on **{idea}**. We keep things straightforward and locally relevant for Westport shoppers. Inventory can change day-to-day, so if you’re looking for something specific, the quickest move is to call us or stop in.

    ## Tips before you buy
    - **Ask what’s new today:** We get fresh items regularly, and staff can point you to current favorites.
    - **Check sizes and options:** Many items come in multiple sizes, styles, or variants.
    - **Stay within local rules:** We keep things compliant and can answer store-level questions.
    - **Don’t overthink it:** If you’re unsure, tell us what you like and we’ll recommend something that matches your style.

    ## Westport note
    If you’re already in the neighborhood, it’s easy to swing by and compare options in person. We’re located at **1130 Westport Rd, Kansas City, MO 64111**.

    **Visit Discount Smokes today.** 21+ for nicotine purchases. Call us for current stock and availability.
    """).strip()

# ====== OpenAI generation WITH automatic fallback ======
def gen_with_openai_or_fallback(prompt: str, title: str, idea: str, category: str) -> str:
    # Forced fallback
    if DRY_RUN or not OPENAI_API_KEY:
        warn("[openai] DRY_RUN enabled OR OPENAI_API_KEY missing -> FALLBACK content.")
        return gen_fallback_post(title, idea, category)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You write concise, friendly, accurate posts for Discount Smokes (Westport, KC). Avoid medical claims."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 700
    }

    log(f"[openai] Requesting model={OPENAI_MODEL} (key present={bool(OPENAI_API_KEY)})")

    try:
        r = requests.post(url, headers=headers, json=body, timeout=90)

        # If OpenAI quota/billing is the problem, fallback instead of failing
        if r.status_code == 429 and "insufficient_quota" in (r.text or ""):
            warn("[openai] insufficient_quota -> FALLBACK MODE (no OpenAI)")
            return gen_fallback_post(title, idea, category)

        if r.status_code >= 400:
            warn(f"[openai] HTTP {r.status_code}: {(r.text or '')[:500]}")
            # Fallback for any non-2xx
            warn("[openai] non-2xx -> FALLBACK MODE")
            return gen_fallback_post(title, idea, category)

        data = r.json()
        content = data["choices"][0]["message"]["content"]
        log("[openai] ✅ Generated content with OpenAI.")
        return content

    except Exception as e:
        warn(f"[openai] Exception -> FALLBACK MODE: {e}")
        return gen_fallback_post(title, idea, category)

# ====== Generate one post (title EXACTLY topics.json) ======
def generate_one_post():
    ensure_structure()
    topics = read_topics()
    today  = datetime.date.today()

    i = get_next_index(len(topics))
    topic = topics[i]

    category = (topic.get("category", "General") or "General").strip()
    title = (topic.get("title") or topic.get("idea") or "Store update").strip()
    idea  = topic.get("idea") or topic.get("title") or "Store update"

    log(f"[topic] total={len(topics)} current_index={i}")
    log(f"[topic] title(from topics.json)='{title}' category='{category}'")
    log(f"[topic] idea='{idea}'")

    content_prompt = f"""
Write a 350-500 word blog post for Discount Smokes (1130 Westport Rd, Kansas City, MO) about: {idea}.
- Avoid medical claims or health promises.
- Friendly, helpful tone. Keep it locally relevant to Westport.
- Start with a 1-2 sentence excerpt labeled 'Excerpt:'
- Include 1-2 markdown subheadings.
- End with a brief invite to visit the shop (21+ for nicotine purchases).
- Category: {category}
""".strip()

    # OpenAI or Fallback
    content_md = gen_with_openai_or_fallback(content_prompt, title=title, idea=idea, category=category)

    # Excerpt
    m = re.search(r"Excerpt:\s*(.+)", content_md, re.IGNORECASE)
    excerpt = m.group(1).strip() if m else "Stop by Discount Smokes in Westport for friendly help and new arrivals."

    # HTML page
    title_h1 = html_lib.escape(title, quote=False)
    body_html = f"<h1>{title_h1}</h1>\n" + markdown_to_html(content_md)

    slug = slugify(title)
    html_path = unique_html_path(today, slug)
    html_path.write_text(wrap_html(title, excerpt, body_html), encoding="utf-8")

    # Update index.json with EXACT title
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
    log(f"[generate] ✅ Wrote HTML post: {html_path}")
    log(f"[generate] ✅ Updated index.json with newest post title='{title}'")

# ====== Index rebuild (title = <h1> inside <article>) ======
TITLE_IN_ARTICLE_RE = re.compile(r"<article[^>]*class=['\"]post['\"][^>]*>.*?<h1[^>]*>(.*?)</h1>", re.I | re.S)
EXCERPT_META_RE     = re.compile(r'<meta\s+name=["\']excerpt["\']\s+content=["\'](.*?)["\']', re.I)

def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()

def extract_title_from_article(html: str, fallback: str) -> str:
    m = TITLE_IN_ARTICLE_RE.search(html)
    raw = strip_tags(m.group(1)) if m else fallback
    return html_lib.unescape(raw)

def extract_excerpt(html: str, fallback: str) -> str:
    m = EXCERPT_META_RE.search(html)
    if m:
        return html_lib.unescape(m.group(1).strip())
    pm = re.search(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)
    if pm:
        t = strip_tags(pm.group(1))
        t = html_lib.unescape(t)
        return (t[:180] + "…") if len(t) > 180 else t
    return fallback

def date_from_filename(name: str) -> str:
    try:
        yyyy, mm, dd, _ = name.split("-", 3)
        return f"{yyyy}-{mm}-{dd}"
    except Exception:
        return datetime.date.today().isoformat()

def rebuild_index():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(list(HTML_DIR.glob("*.html")))
    log(f"[rebuild] Found {len(files)} HTML files in {HTML_DIR}")

    entries = []
    for file in files:
        name = file.name
        date_iso = date_from_filename(name)
        try:
            html = file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            warn(f"[rebuild] Skipping {name}: {e}")
            continue

        fallback_title = re.sub(r"\.html$", "", name).split("-", 3)[-1].replace("-", " ").title()
        title   = extract_title_from_article(html, fallback_title)
        excerpt = extract_excerpt(html, "Stop by Discount Smokes in Westport for friendly help and new arrivals.")

        entries.append({
            "title": title,
            "date": date_iso,
            "url": f"posts/html/{name}",
            "excerpt": excerpt,
            "category": "General"
        })

    entries.sort(key=lambda e: e["date"], reverse=True)
    INDEX_PATH.write_text(json.dumps({"posts": entries}, indent=2), encoding="utf-8")
    log(f"[rebuild] ✅ Wrote {INDEX_PATH} with {len(entries)} HTML posts")

# ====== Main ======
def main():
    # Print environment summary (no secrets)
    log("[env] OPENAI_API_KEY present=" + str(bool(OPENAI_API_KEY)))
    log("[env] OPENAI_MODEL=" + str(OPENAI_MODEL))
    log("[env] DRY_RUN=" + ("1" if DRY_RUN else "0"))
    log("[env] SHEETBEST_URL configured=" + str(bool(SHEETBEST_URL)))

    ensure_structure()

    # Generation SHOULD NOT fail for insufficient_quota anymore (fallback handles it)
    try:
        generate_one_post()
    except SystemExit:
        raise
    except Exception as e:
        warn("[generate] ❌ FAILED to generate new post.")
        warn(f"[generate] Error: {e}")
        warn("[generate] Traceback:\n" + traceback.format_exc())
        raise SystemExit(1)

    # Rebuild index (fail only if rebuild itself fails)
    try:
        rebuild_index()
    except Exception as e:
        warn("[rebuild] ❌ FAILED to rebuild index.json.")
        warn(f"[rebuild] Error: {e}")
        warn("[rebuild] Traceback:\n" + traceback.format_exc())
        raise SystemExit(1)

    log("[done] ✅ Generation + rebuild completed successfully.")

if __name__ == "__main__":
    main()
