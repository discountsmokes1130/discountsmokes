#!/usr/bin/env python3
import os, json, smtplib, ssl, urllib.request, urllib.parse, hashlib, re, time

SHEETBEST_URL      = os.getenv("SHEETBEST_URL")                 # subscribers sheet
SHEETBEST_UNSUB_URL= os.getenv("SHEETBEST_UNSUB_URL") or (
    (SHEETBEST_URL.rstrip("/") + "/tabs/unsubscribes") if SHEETBEST_URL else None
)
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "change-me")
FROM_EMAIL         = os.getenv("GMAIL_USER")                    # 1130.westport@gmail.com
APP_PASSWORD       = os.getenv("GMAIL_APP_PASSWORD")
SITE_BASE          = os.getenv("SITE_BASE", "https://discountsmokeskc.com/")

CALL_TEL = "tel:+18167121130"
DIR_LINK = "https://www.google.com/maps?q=1130+Westport+Rd,+Kansas+City,+MO+64111"
FB_LINK  = "https://www.facebook.com/TrippinSmokeandVape/"
IG_LINK  = "https://www.instagram.com/trippin_smokes/"
SC_LINK  = "https://www.snapchat.com/add/discountkc"

ARTICLE_RE = re.compile(r"<article[^>]*class=['\"]post['\"][^>]*>(.*?)</article>", re.I | re.S)

def http_get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_emails():
    rows = http_get_json(SHEETBEST_URL)
    return sorted({ str(row.get("email","")).strip().lower()
                    for row in rows if "@" in str(row.get("email","")) })

def fetch_unsubscribed():
    if not SHEETBEST_UNSUB_URL:
        return set()
    try:
        rows = http_get_json(SHEETBEST_UNSUB_URL)
    except Exception:
        return set()
    return { str(row.get("email","")).strip().lower() for row in rows if "@" in str(row.get("email","")) }

def latest_post():
    with open("posts/index.json","r",encoding="utf-8") as f:
        idx = json.load(f)
    if not idx.get("posts"): raise RuntimeError("No posts in index.json")
    p = idx["posts"][0]
    return p["title"], p["url"]  # local relative URL to HTML

def read_article_body(rel_url: str) -> str:
    local_path = rel_url.replace("/", os.sep)
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return "<p>Blog content could not be loaded.</p>"
    m = ARTICLE_RE.search(html)
    return (m.group(1).strip() if m else html)

def make_token(email: str) -> str:
    h = hashlib.sha256()
    h.update((email + "|" + UNSUBSCRIBE_SECRET).encode("utf-8"))
    return h.hexdigest()

def unsubscribe_link(email: str) -> str:
    token = make_token(email)
    # the public unsubscribe page in your repo
    base = SITE_BASE.rstrip("/") + "/unsubscribe.html"
    params = urllib.parse.urlencode({"e": email, "t": token})
    return f"{base}?{params}"

def send_one_email(to_addr: str, subject: str, html_body: str):
    # Compose headers WITHOUT exposing other recipients
    headers = [
        f"From: Discount Smokes <{FROM_EMAIL}>",
        f"To: {to_addr}",                           # individual send
        f"Subject: {subject}",
        "MIME-Version: 1.0",
        "Content-Type: text/html; charset=utf-8",
    ]
    msg = "\r\n".join(headers) + "\r\n\r\n" + html_body
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ctx)
        s.login(FROM_EMAIL, APP_PASSWORD)
        s.sendmail(FROM_EMAIL, [to_addr], msg.encode("utf-8"))

def main():
    subs = fetch_emails()
    unsub = fetch_unsubscribed()
    # Skip unsubscribed
    send_list = [e for e in subs if e not in unsub]
    if not send_list:
        print("No subscribers to email (or all unsubscribed).")
        return

    title, rel_url = latest_post()   # title already equals topics.json (from generator)
    body_inner_html = read_article_body(rel_url)

    for idx, email in enumerate(send_list, start=1):
        unsub_url = unsubscribe_link(email)
        html = f"""
          <div style="font-family:Arial,Helvetica,sans-serif;line-height:1.55;">
            <h2 style="margin:0 0 10px;color:#e63946;">{title}</h2>
            <div style="background:#ffffff;border:1px solid #eee;border-radius:12px;padding:16px;">
              {body_inner_html}
            </div>
            <div style="margin-top:14px;padding-top:12px;border-top:1px solid #e5e7eb;">
              <p style="margin:6px 0;">
                <a href="{CALL_TEL}" style="color:#e63946;text-decoration:none;">📞 Call Us</a> &nbsp;•&nbsp;
                <a href="{DIR_LINK}" style="color:#e63946;text-decoration:none;" target="_blank">📍 Directions</a>
              </p>
              <p style="margin:6px 0;">
                <a href="{FB_LINK}" style="text-decoration:none;color:#1877F2;" target="_blank">Facebook</a> &nbsp;|&nbsp;
                <a href="{IG_LINK}" style="text-decoration:none;color:#d6249f;" target="_blank">Instagram</a> &nbsp;|&nbsp;
                <a href="{SC_LINK}" style="text-decoration:none;color:#fffc00;background:#000;padding:2px 6px;border-radius:6px;" target="_blank">Snapchat</a>
              </p>
              <p style="font-size:12px;color:#6b7280;margin-top:10px;">
                1130 Westport Rd, Kansas City, MO 64111 — 21+ for nicotine purchases.
              </p>
              <p style="font-size:12px;color:#6b7280;margin-top:6px;">
                <a href="{unsub_url}" style="color:#6b7280;text-decoration:underline;" target="_blank">Unsubscribe</a>
              </p>
            </div>
          </div>
        """
        subject = f"Discount Smokes - {title}"
        try:
            send_one_email(email, subject, html)
            print(f"Sent {idx}/{len(send_list)} → {email}")
        except Exception as e:
            print(f"ERROR sending to {email}: {e}", file=sys.stderr)
        # be a good citizen to SMTP — small pause
        time.sleep(0.5)

if __name__ == "__main__":
    main()
