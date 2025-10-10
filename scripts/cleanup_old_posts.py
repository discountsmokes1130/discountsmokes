#!/usr/bin/env python3
"""
Deletes posts older than a cutoff (default 60 days) from posts/*.md
and removes them from posts/index.json.

Safety:
- Skips files without a parseable YYYY-MM-DD prefix.
- Keeps at least KEEP_MIN most recent posts (default 20), even if older.
- DRY_RUN=1 will log actions without deleting.
"""

import os, json, re, pathlib, datetime, sys

ROOT = pathlib.Path(".")
POSTS_DIR = ROOT / "posts"
INDEX = POSTS_DIR / "index.json"

CUTOFF_DAYS = int(os.getenv("CUTOFF_DAYS", "60"))  # delete if older than this
KEEP_MIN    = int(os.getenv("KEEP_MIN", "20"))     # always keep this many newest
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

    # Load index safely
    if INDEX.exists():
        try:
            idx = json.loads(INDEX.read_text(encoding="utf-8"))
            posts = idx.get("posts", [])
        except Exception:
            posts = []
    else:
        posts = []

    # Gather files on disk with parsed dates
    entries = []
    for p in POSTS_DIR.glob("*.md"):
        dt = parse_date_from_name(p.name)
        entries.append((p, dt))

    # Sort newest -> oldest (None dates go last)
    entries.sort(key=lambda x: (x[1] is not None, x[1]), reverse=True)

    # Always keep at least KEEP_MIN newest files
    keep_set = set(e[0].name for e in entries[:KEEP_MIN])

    to_delete = []
    for p, dt in entries[KEEP_MIN:]:  # only consider beyond KEEP_MIN newest
        if dt is None:
            continue
        if dt < cutoff_date:
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

    # Update index.json if we removed anything
    if deleted_names:
        new_posts = []
        for post in posts:
            url = post.get("url", "")
            fname = url.split("/")[-1] if "/" in url else url
            if fname and fname in deleted_names:
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
