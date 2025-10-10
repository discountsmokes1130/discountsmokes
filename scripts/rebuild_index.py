#!/usr/bin/env python3
import os
import json
import datetime
import re
import pathlib
import textwrap
import sys

try:
    import requests
except Exception:
    print("ERROR: 'requests' not installed. Did pip install run?", file=sys.stderr)
    sys.exit(1)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DRY_RUN = os.getenv("DRY_RUN", "")

REPO_ROOT  = pathlib.Path(".")
POSTS_DIR  = REPO_ROOT / "posts"
INDEX_FILE = POSTS_DIR / "index.json"
TOPICS_FILE = POSTS_DIR / "topics.json"
STATE_FILE  = POSTS_DIR / ".topic_state.json"


def ensure_structure():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text(json.dumps({"posts": []}, indent=2), encoding="utf-8")
    if not TOPICS_FILE.exists():
        # If you’re not using topics.json, you can relax this.
        raise SystemExit("ERROR: posts/topics.json not found. Add the 1000-topic file to posts/.")


def read_topics():
    data = json.loads(TOPICS_FILE.read_text(encoding="utf-8"))
    topics = data.get("topics", [])
    if not topics:
        raise SystemExit("ERROR: posts/topics.json has no 'topics' array.")
    return topics


def get_next_index(total: int) -> int:
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            idx = int(st.get("next_index", 0))
        except Exception:
            idx = 0
    else:
        idx = 0
    if idx < 0 or idx >= total:
        idx = 0
    return idx


def bump_index(idx: int, total: int):
    next_idx = (idx + 1) % total
    STATE_FILE.write_text(json.dumps({"next_index": next_idx}, indent=2), encoding="utf-8")


def gen_with_openai(prompt: str) -> str:
    if DRY_RUN or not OPENAI_API_KEY:
        return textwrap.dedent("""
        Excerpt: Visit Discount Smokes in Westport for helpful service and new arrivals.

        ## Placeholder Post
        This is a placeholder blog post created by the automation. Once you add
        the OPENAI_API_KEY secret, the system will publish fully written posts automatically.

        ### Stop By
        1130 Westport Rd, Kansas City, MO 64111
        """).strip()

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write concise, friendly, accurate posts for a smoke shop in "
                    "Kansas City Westport (Discount Smokes). Avoid medical claims."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 700,
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    try:
        r.raise_for_status()
    except Exception:
        print("ERROR: OpenAI API error:", r.text, file=sys.stderr)
        raise
    data = r.json()
    return data["choices"][0]["message"]["content"]


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "post"


def unique_post_path(date: datetime.date, slug: str) -> pathlib.Path:
    """
    Ensure we never overwrite today’s post if the script runs multiple times.
    Creates YYYY-MM-DD-slug.md, or appends -1, -2, ... until unique.
    """
    base = f"{date:%Y-%m-%d}-{slug}.md"
    path = POSTS_DIR / base
    if not path.exists():
        return path
    # find next available suffix
    i = 1
    while True:
        candidate = POSTS_DIR / f"{date:%Y-%m-%d}-{slug}-{i}.md"
        if not candidate.exists():
            return candidate
        i += 1


def main():
    print("== Auto Blog (unique filenames) : start ==")
    ensure_structure()
    topics = read_topics()

    today = datetime.date.today()

    # Pick next topic by persistent index
    idx = get_next_index(len(topics))
    topic = topics[idx]
    category = topic.get("category", "General")
    idea = topic.get("idea") or topic.get("title") or "Store update"

    # Title + content prompts
    title_prompt = f"Create a catchy 6-10 word blog title about: {topic.get('title', idea)}"
    content_prompt = f"""
Write a 350-500 word blog post for Discount Smokes (1130 Westport Rd, Kansas City, MO) about: {idea}.
- Avoid medical claims or health promises.
- Friendly, helpful tone. Keep it locally relevant to Westport.
- Start with a 1-2 sentence excerpt labeled 'Excerpt:'
- Include 1-2 markdown subheadings.
- End with a brief invite to visit the shop (21+ for nicotine purchases).
- Category: {category}
"""

    try:
        title = gen_with_openai(title_prompt).strip().splitlines()[0].replace('"', "")
        if not title:
            title = f"{category} Update"
        content = gen_with_openai(content_prompt)
    except Exception as e:
        print("FATAL: Could not generate content:", e, file=sys.stderr)
        sys.exit(1)

    # Excerpt extraction
    m = re.search(r"Excerpt:\s*(.+)", content, re.IGNORECASE)
    excerpt = m.group(1).strip() if m else "Stop by Discount Smokes in Westport for friendly help and new arrivals."

    slug = slugify(title)
    post_path = unique_post_path(today, slug)  # ← ensure unique filename
    post_url = f"posts/{post_path.name}"

    # Write post file
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    post_path.write_text(content, encoding="utf-8")

    # Update index.json
    idx_json = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    idx_json.setdefault("posts", [])
    idx_json["posts"].insert(0, {
        "title": title,
        "date": f"{today:%Y-%m-%d}",
        "url": post_url,
        "excerpt": excerpt,
        "category": category
    })
    INDEX_FILE.write_text(json.dumps(idx_json, indent=2), encoding="utf-8")

    # Bump rotation index
    bump_index(idx, len(topics))

    print(f"== Auto Blog: wrote {post_path} (category: {category}) ==")
    print("== Auto Blog: success ==")


if __name__ == "__main__":
    main()
