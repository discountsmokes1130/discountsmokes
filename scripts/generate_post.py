#!/usr/bin/env python3
import os, json, datetime, re, pathlib, textwrap, sys

try:
    import requests
except Exception as e:
    print("ERROR: 'requests' not available. Did pip install run?", file=sys.stderr)
    sys.exit(1)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DRY_RUN = os.getenv("DRY_RUN", "")

REPO_ROOT = pathlib.Path(".")
POSTS_DIR = REPO_ROOT / "posts"
INDEX_FILE = POSTS_DIR / "index.json"

def ensure_structure():
    if not POSTS_DIR.exists():
        print("Creating posts/ ...")
        POSTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        print("Seed posts/index.json ...")
        INDEX_FILE.write_text(json.dumps({"posts": []}, indent=2), encoding="utf-8")

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "post"

def gen_with_openai(prompt: str) -> str:
    """Generate text using OpenAI API or fallback content if API key missing."""
    if DRY_RUN or not OPENAI_API_KEY:
        print("DRY_RUN active or OPENAI_API_KEY missing — generating placeholder content.")
        return textwrap.dedent(f"""
        Excerpt: Visit Discount Smokes in Westport for helpful service and new arrivals.

        ## Placeholder Post
        This is a placeholder blog post created by the automation. Once you add
        the OPENAI_API_KEY secret in your GitHub repo, the system will publish
        fully written posts automatically.

        ### Stop By
        1130 Westport Rd, Kansas City, MO 64111
        """).strip()

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You write concise, friendly blog posts for a Kansas City smoke shop. Avoid medical claims."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 700
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    try:
        r.raise_for_status()
    except Exception as e:
        print("ERROR: OpenAI API error:", r.text, file=sys.stderr)
        raise
    data = r.json()
    return data["choices"][0]["message"]["content"]

def main():
    print("== Auto Blog: start ==")
    ensure_structure()

    topics = [
        "New vape arrivals and flavors this week",
        "Tips for choosing between disposables and refillables",
        "Cigar wraps, sizes, and pairing ideas",
        "Hookah charcoal and shisha care essentials",
        "What to know about kratom products (no medical claims)",
        "Gummies: types and what to look for (no medical claims)",
        "Smoking accessories: grinders, papers, and trays spotlight",
    ]
    today = datetime.date.today()
    topic = topics[today.toordinal() % len(topics)]

    # Title prompt
    title_prompt = f"Write a catchy title (max 10 words) for a blog post about: {topic}."

    # ✅ Fixed triple quotes here
    content_prompt = f"""Write a 300-450 word blog post for Discount Smokes (1130 Westport Rd, Kansas City, MO) about: {topic}.
- Avoid medical claims or health promises.
- Friendly, helpful tone. End with a short call to visit the shop.
- Add a 1-2 sentence excerpt at the start, clearly marked as 'Excerpt:'
- Include a simple markdown subheading or two.
"""

    try:
        title = gen_with_openai(title_prompt).strip().splitlines()[0].replace('"','')
        if not title:
            title = "Store Update"
        content = gen_with_openai(content_prompt)
    except Exception as e:
        print("FATAL: Could not generate content:", e, file=sys.stderr)
        sys.exit(1)

    # Extract excerpt
    m = re.search(r"Excerpt:\s*(.+)", content, re.IGNORECASE)
    excerpt = m.group(1).strip() if m else "Stop by Discount Smokes in Westport for friendly help and new arrivals."

    slug = slugify(title)
    filename = f"{today:%Y-%m-%d}-{slug}.md"
    post_path = POSTS_DIR / filename
    post_url = f"posts/{filename}"

    print(f"Writing post: {post_path}")
    post_path.write_text(content, encoding="utf-8")

    # Update index
    idx = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    idx.setdefault("posts", [])
    idx["posts"].insert(0, {
        "title": title,
        "date": f"{today:%Y-%m-%d}",
        "url": post_url,
        "excerpt": excerpt,
        "category": "General"
    })
    INDEX_FILE.write_text(json.dumps(idx, indent=2), encoding="utf-8")

    print("== Auto Blog: success ==")

if __name__ == "__main__":
    main()
