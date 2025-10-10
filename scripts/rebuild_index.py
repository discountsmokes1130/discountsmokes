#!/usr/bin/env python3
import os, json, re, pathlib, datetime

ROOT = pathlib.Path(".")
POSTS_DIR = ROOT / "posts"
INDEX = POSTS_DIR / "index.json"

def read_excerpt(text: str) -> str:
    m = re.search(r"Excerpt:\s*(.+)", text, re.IGNORECASE)
    if m: return m.group(1).strip()
    # fallback: first non-empty line or first 180 chars
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return (s[:180] + "…") if len(s) > 180 else s
    return "Stop by Discount Smokes in Westport for friendly help and new arrivals."

def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for p in POSTS_DIR.glob("*.md"):
        name = p.name  # e.g., 2025-03-15-title.md
        # date from filename
        try:
            yyyy, mm, dd, *_ = name.split("-", 3)
            date_iso = f"{yyyy}-{mm}-{dd}"
        except Exception:
            date_iso = datetime.date.today().isoformat()

        text = p.read_text(encoding="utf-8", errors="replace")
        # title as first H1 if present
        m = re.search(r"^#\s*(.+)$", text, flags=re.M)
        title = m.group(1).strip() if m else re.sub(r"\.md$", "", name).split("-", 3)[-1].replace("-", " ").title()
        excerpt = read_excerpt(text)
        url = f"posts/{name}"

        entries.append({
            "title": title,
            "date": date_iso,
            "url": url,
            "excerpt": excerpt,
            "category": "General"
        })

    # newest first
    entries.sort(key=lambda e: e["date"], reverse=True)
    INDEX.write_text(json.dumps({"posts": entries}, indent=2), encoding="utf-8")
    print(f"Wrote {INDEX} with {len(entries)} posts")

if __name__ == "__main__":
    main()
