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
    nxt = (i + 1) % total
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

# ====== HTML wrapper for generated posts (MATCHES YOUR SITE LINKS + CSS) ======
def wrap_html(title:str, excerpt:str, body_html:str)->str:
    year = datetime.date.today().year
    title_esc   = html_lib.escape(title,   quote=True)
    excerpt_esc = html_lib.escape(excerpt, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title_esc} — Discount Smokes</title>
  <meta name="description" content="{excerpt_esc}"/>
  <meta name="excerpt" content="{excerpt_esc}"/>
  <link rel="stylesheet" href="../../styles.css"/>
  <link rel="icon" href="../../assets/favicon.svg"/>
  <style>
    /* Small safe overrides so generated posts look clean */
    main.container {{ padding: 18px 0; }}
    article.post {{ background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:18px; box-shadow:0 8px 18px rgba(0,0,0,.04); }}
    article.post h1 {{ margin-top: 0; }}
    article.post img {{ max-width:100%; height:auto; border-radius:10px; }}
  </style>
</head>
<body>
  <header>
    <div class="container header-inner">
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

      <div class="top-contact">
        <a href="https://www.google.com/maps?q=1130+Westport+Rd,+Kansas+City,+MO+64111" target="_blank" class="action small">📍 Directions</a>
        <a href="mailto:1130.westport@gmail.com" class="action small">✉️ Contact Us</a>
        <a href="tel:+18167121130" class="action small">📞 Call Now</a>
        <a href="../../blog.html" class="action small">📰 Blog</a>
      </div>
    </div>
  </header>

  <main class="container">
    <article class="post">
      {body_html}
    </article>
  </main>

  {subscribe_block()}

  <footer>© {year} Discount Smokes. All Rights Reserved.</footer>
</body>
</html>"""

# ====== FREE fallback post generator (NO OpenAI needed) ======
def gen_fallback_post(title: str, idea: str, category: str) -> str:
    # 600–800 words-ish, sales-oriented, no medical claims.
    # Build a structured, richer post that reads like a real blog.
    location = "1130 Westport Rd, Kansas City, MO 64111"
    return textwrap.dedent(f"""
    Excerpt: {title} — helpful tips and in-store guidance from Discount Smokes in Westport (Kansas City).

    ## Why this matters (Westport-friendly)
    If you’ve ever walked into a smoke shop and felt overwhelmed by options, you’re not alone. The goal of this guide is to make **{idea}** simple and practical—without hype and without complicated talk. In Westport, people are usually looking for one of two things: something reliable they already like, or something new that fits their vibe. Either way, the fastest way to make a good pick is to focus on **what you want the experience to feel like** and then match that with the right product type.

    At **Discount Smokes**, we keep it straightforward: we’ll tell you what’s popular today, what’s new, and what’s best for your preferences. Inventory changes often, so think of this as a “how to choose” guide that stays useful even when brands rotate.

    ## What to look for (quick checklist)
    Here are the smart things to check before buying—especially if you want something you’ll actually enjoy:
    - **Freshness & packaging:** Look for sealed packaging and clean labeling.
    - **Options that match your style:** Size, strength, flavor, and form factor matter more than the “most popular” item.
    - **Consistency:** If you’re buying something you liked before, ask what’s closest to it now.
    - **Local compliance:** We keep products aligned with applicable rules; if you’re unsure, ask us in-store.

    ## Tips that save you money (and time)
    Want to avoid regret purchases? These are the simplest habits that help:
    1. **Tell us your “must-haves.”** Example: “smooth, not harsh” or “simple and easy to use.”
    2. **Ask what’s best at your price point.** There’s usually a solid option that fits your budget without feeling cheap.
    3. **Don’t guess—ask.** If you’re deciding between two things, staff can help you compare quickly.
    4. **Plan for accessories.** If you need papers, cones, grinders, chargers, or other add-ons, bundle it in one visit.

    ## What people in Westport usually ask us
    We hear these questions constantly, so here are quick answers:
    - **“What’s new this week?”** We get fresh items regularly—ask what just arrived.
    - **“What’s easiest for beginners?”** Simple setups with clear usage are the move; we’ll point you to low-fuss options.
    - **“What’s the best value?”** Value usually means: reliable + consistent + priced fairly. We’ll show you current picks.

    ## A simple “choose your lane” guide
    Use this to narrow down quickly:
    - If you want **easy + quick** → ask for “low-maintenance, popular picks.”
    - If you want **variety** → ask what flavors or options are trending right now.
    - If you want **accessories** → ask what matches your setup so you don’t buy the wrong add-on.
    - If you want **something giftable** → ask what looks clean, packaged well, and is widely liked.

    ## Visit us (and get real help)
    The best part of shopping in person is that you can ask questions and compare options quickly. We’re right here in Westport at **{location}**. If you want to confirm availability before coming in, just call us—we’ll tell you what’s in stock today.

    **Stop by Discount Smokes.** 21+ for nicotine purchases. Call us for current stock and friendly help.
    """).strip()

# ====== OpenAI generation WITH automatic fallback ======
def gen_with_openai_or_fallback(prompt: str, title: str, idea: str, category: str) -> str:
    if DRY_RUN or not OPENAI_API_KEY:
        warn("[openai] DRY_RUN enabled OR OPENAI_API_KEY missing -> FALLBACK content.")
        return gen_fallback_post(title, idea, category)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You write helpful, friendly, sales-supporting posts for Discount Smokes (Westport, KC). Avoid medical claims. No health promises. Keep it practical and locally relevant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1100
    }

    log(f"[openai] Requesting model={OPENAI_MODEL} (key present={bool(OPENAI_API_KEY)})")

    try:
        r = requests.post(url, headers=headers, json=body, timeout=90)

        # Fallback if quota/billing or any non-2xx
        if r.status_code == 429:
            warn(f"[openai] HTTP 429 -> FALLBACK MODE")
            return gen_fallback_post(title, idea, category)

        if r.status_code >= 400:
            warn(f"[openai] HTTP {r.status_code}: {(r.text or '')[:400]}")
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

    content_prompt = f"""
Write a 600-800 word blog post for Discount Smokes (1130 Westport Rd, Kansas City, MO) about: {idea}.
Rules:
- Avoid medical claims, health promises, or anything that sounds like medical advice.
- Friendly, helpful, sales-supporting tone. Keep it locally relevant to Westport.
- Start with a 1-2 sentence excerpt labeled 'Excerpt:'.
- Use 3-5 markdown subheadings (##).
- Include practical tips/checklists that help shoppers decide what to buy.
- End with a short invite to visit the shop (21+ for nicotine purchases) + mention calling for stock.
- Category: {category}
""".strip()

    content_md = gen_with_openai_or_fallback(
        content_prompt,
        title=title,
        idea=idea,
        category=category
    )

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

    try:
        generate_one_post()
    except SystemExit:
        raise
    except Exception as e:
        warn("[generate] ❌ FAILED to generate new post.")
        warn(f"[generate] Error: {e}")
        warn("[generate] Traceback:\n" + traceback.format_exc())
        raise SystemExit(1)

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
