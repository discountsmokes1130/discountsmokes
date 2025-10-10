#!/usr/bin/env python3
import os, json, re, pathlib, datetime, sys

ROOT = pathlib.Path(".")
POSTS_DIR = ROOT / "posts"
HTML_DIR  = POSTS_DIR / "html"
INDEX     = POSTS_DIR / "index.json"

CUTOFF_DAYS = int(os.getenv("CUTOFF_DAYS", "60"))
KEEP_MIN    = int(os.getenv("KEEP_MIN", "20"))
DRY_RUN     = os.getenv("DRY_RUN", "")

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")

def parse_date_from_name(name: str):
    m = DATE_RE.match(name)
    if not m:
        return None
    y, mth, d = map(int, m.groups())
    try:
        return datetime.date(y, mth, d)
    except ValueError:
        return None

def main():
    today = datetime.date.today()
    cutoff_date = today - datetime.timedelta(days=CUTOFF_DAYS)

    if INDEX.exists():
        try:
            idx = json.loads(INDEX.read_text(encoding="utf-8"))
            posts = idx.get("posts", [])
        except Exception:
            posts = []
    else:
        posts = []

    HTML_DIR.mkdir(parents=True, exist_ok=True)

    # Collect HTML posts
    entries = []
    for p in HTML_DIR.glob("*.html"):
        dt = parse_date_from_name(p.name)
        entries.append((p, dt))

    # Sort newest -> oldest
    entries.sort(key=lambda x: (x[1] is not None, x[1]), reverse=True)
    keep_set = set(e[0].name for e in entries[:KEEP_MIN])

    to_delete = []
    for p, dt in entries[KEEP_MIN:]:
        if dt and dt < cutoff_date:
            to_delete.append(p)

    deleted_names = set()
    for p in to_delete:
        if p.name in keep_set:
            continue
        if DRY_RUN:
            print(f"[DRY_RUN] Would delete: {p}")
        else:
            try:
                p.unlink()
                deleted_names.add(p.name)
                print(f"Deleted: {p}")
            except Exception as e:
                print(f"ERROR deleting {p}: {e}", file=sys.stderr)

    # Remove any leftover .md files (legacy)
    for md_file in POSTS_DIR.glob("*.md"):
        try:
            if DRY_RUN:
                print(f"[DRY_RUN] Would remove legacy file: {md_file}")
            else:
                md_file.unlink()
                print(f"Removed legacy file: {md_file}")
        except Exception as e:
            print(f"ERROR removing {md_file}: {e}", file=sys.stderr)

    # Update index.json to drop deleted HTML posts
    if deleted_names:
        new_posts = []
        for post in posts:
            url = post.get("url", "")
            fname = url.split("/")[-1] if "/" in url else url
            if fname in deleted_names:
                continue
            new_posts.append(post)
        if DRY_RUN:
            print(f"[DRY_RUN] Would write index.json with {len(new_posts)} posts")
        else:
            INDEX.write_text(json.dumps({"posts": new_posts}, indent=2), encoding="utf-8")
            print(f"Updated index.json — {len(new_posts)} posts remain")
    else:
        print("No deletions needed.")

if __name__ == "__main__":
    main()
