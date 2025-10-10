#!/usr/bin/env python3
import os, json, datetime, re, pathlib, textwrap, sys
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
    sys.exit(1)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "post"

def gen_with_openai(prompt: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You write concise, helpful, and accurate blog posts for a smoke shop. Avoid medical claims. Keep it friendly and local to Kansas City Westport."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 700
    }
    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return content

def main():
    repo_root = pathlib.Path(".")
    posts_dir = repo_root / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    idx_file = posts_dir / "index.json"
    if idx_file.exists():
        idx = json.loads(idx_file.read_text(encoding="utf-8"))
    else:
        idx = {"posts": []}

    today = datetime.date.today().strftime("%Y-%m-%d")

    # Simple topic rotation
    topics = [
        "New vape arrivals and flavors this week",
        "Tips for choosing between disposables and refillables",
        "Cigar wraps, sizes, and pairing ideas",
        "Hookah charcoal and shisha care essentials",
        "What to know about kratom products (no medical claims)",
        "Gummies: types and what to look for (no medical claims)",
        "Smoking accessories: grinders, papers, and trays spotlight",
    ]
    topic = topics[datetime.date.today().toordinal() % len(topics)]

    title_prompt = f"Write a catchy title (max 10 words) for a blog post about: {topic}."
    title = gen_with_openai(title_prompt).strip().replace('"','')
    title = title.splitlines()[0]

    post_prompt = f\"\"\"Write a 300-450 word blog post for Discount Smokes (1130 Westport Rd, Kansas City, MO) about: {topic}.
- Avoid medical claims or health promises.
- Friendly, helpful tone. End with a short call to visit the shop.
- Add a 1-2 sentence excerpt at the start, clearly marked as 'Excerpt:'
- Include a simple markdown subheading or two.
\"\"\"
    content = gen_with_openai(post_prompt)

    # Extract excerpt
    excerpt_match = re.search(r"Excerpt:\s*(.+)", content, re.IGNORECASE)
    excerpt = excerpt_match.group(1).strip() if excerpt_match else "Stop by Discount Smokes in Westport for friendly help and new arrivals."

    slug = slugify(title)
    filename = f"{today}-{slug}.md"
    post_path = posts_dir / filename
    post_url = f"posts/{filename}"

    post_path.write_text(content, encoding="utf-8")

    # Update index.json
    idx["posts"].insert(0, {
        "title": title,
        "date": today,
        "url": post_url,
        "excerpt": excerpt,
        "category": "General"
    })
    idx_file.write_text(json.dumps(idx, indent=2), encoding="utf-8")
    print(f"Created {post_path}")

if __name__ == "__main__":
    main()
