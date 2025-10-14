#!/usr/bin/env python3
import os, json, smtplib, ssl, urllib.request

SHEETBEST_URL = os.getenv("SHEETBEST_URL")         # same endpoint
FROM_EMAIL    = os.getenv("GMAIL_USER")             # 1130.westport@gmail.com
APP_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD")     # Gmail App Password
SITE_BASE     = os.getenv("SITE_BASE", "")          # https://<user>.github.io/<repo>/ or your custom domain

def fetch_emails():
    with urllib.request.urlopen(SHEETBEST_URL, timeout=30) as r:
        rows = json.loads(r.read().decode("utf-8"))
    emails = { str(row.get("email","")).strip().lower()
               for row in rows if "@" in str(row.get("email","")) }
    return sorted(emails)

def latest_post():
    with open("posts/index.json","r",encoding="utf-8") as f:
        idx = json.load(f)
    if not idx.get("posts"): raise RuntimeError("No posts in index.json")
    p = idx["posts"][0]
    link = p["url"]
    if SITE_BASE:
        if not SITE_BASE.endswith("/"): SITE_BASE += "/"
        link = SITE_BASE + link
    return p["title"], p.get("excerpt",""), link

def send_email(to_list, subject, html):
    msg = f"From: Discount Smokes <{FROM_EMAIL}>\r\n" \
          f"To: {', '.join(to_list)}\r\n" \
          f"Subject: {subject}\r\n" \
          f"MIME-Version: 1.0\r\n" \
          f"Content-Type: text/html; charset=utf-8\r\n\r\n" + html
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ctx)
        s.login(FROM_EMAIL, APP_PASSWORD)
        BATCH = 40
        for i in range(0, len(to_list), BATCH):
            s.sendmail(FROM_EMAIL, to_list[i:i+BATCH], msg.encode("utf-8"))

def main():
    subs = fetch_emails()
    if not subs:
        print("No subscribers; skipping email.")
        return
    title, excerpt, link = latest_post()
    subject = f"Discount Smokes - {title}"
    html = f"""
      <div style="font-family:Arial,Helvetica,sans-serif;">
        <h2 style="margin:0 0 8px;color:#e63946;">{title}</h2>
        <p style="color:#374151;">{excerpt}</p>
        <p><a href="{link}" style="background:#e63946;color:#fff;padding:10px 14px;border-radius:10px;text-decoration:none;">Read the post</a></p>
        <p style="font-size:12px;color:#6b7280;">1130 Westport Rd, Kansas City, MO 64111</p>
      </div>
    """
    send_email(subs, subject, html)
    print(f"Emailed {len(subs)} subscribers")

if __name__ == "__main__":
    main()
