#!/usr/bin/env python3
import os, json, smtplib, ssl, urllib.request, re

SHEETBEST_URL = os.getenv("SHEETBEST_URL")          # Sheet.best endpoint
FROM_EMAIL    = os.getenv("GMAIL_USER")             # 1130.westport@gmail.com
APP_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD")     # Gmail App Password
SITE_BASE     = os.getenv("SITE_BASE", "")          # Optional: public base URL if you need absolute links

# Contact / social links
CALL_TEL = "tel:+18167121130"
DIR_LINK = "https://www.google.com/maps?q=1130+Westport+Rd,+Kansas+City,+MO+64111"
FB_LINK  = "https://www.facebook.com/TrippinSmokeandVape/"
IG_LINK  = "https://www.instagram.com/trippin_smokes/"
SC_LINK  = "https://www.snapchat.com/add/discountkc"

ARTICLE_RE = re.compile(r"<article[^>]*class=['\"]post['\"][^>]*>(.*?)</article>", re.I | re.S)

def fetch_emails():
    with urllib.request.urlopen(SHEETBEST_URL, timeout=30) as r:
        rows = json.loads(r.read().decode("utf-8"))
    return sorted({ str(row.get("email","")).strip().lower()
                    for row in rows if "@" in str(row.get("email","")) })

def latest_post():
    with open("posts/index.json","r",encoding="utf-8") as f:
        idx = json.load(f)
    if not idx.get("posts"):
        raise RuntimeError("No posts in index.json")
    p = idx["posts"][0]
    rel_url = p["url"]  # e.g., posts/html/2025-01-15-slug.html
    local_path = rel_url.replace("/", os.sep)
    # Title already equals topics.json title (set by generator)
    return p["title"], local_path

def read_article_html(local_path: str) -> str:
    """Return inner HTML of <article class='post'>...</article> or a fallback."""
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return "<p>Blog content could not be loaded.</p>"
    m = ARTICLE_RE.search(html)
    if m:
        return m.group(1).strip()
    return html  # fallback: whole file

def send_email(to_list, subject, html):
    msg = (
        f"From: Discount Smokes <{FROM_EMAIL}>\r\n"
        f"To: {', '.join(to_list)}\r\n"
        f"Subject: {subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n\r\n" + html
    )
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ctx)
        s.login(FROM_EMAIL, APP_PASSWORD)
        for i in range(0, len(to_list), 40):
            s.sendmail(FROM_EMAIL, to_list[i:i+40], msg.encode("utf-8"))

def main():
    subs = fetch_emails()
    if not subs:
        print("No subscribers; skipping email.")
        return

    title, local_path = latest_post()
    body_inner_html = read_article_html(local_path)

    # Full email (no "Read the post" button; include contact links + socials)
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
        </div>
      </div>
    """

    subject = f"Discount Smokes - {title}"
    send_email(subs, subject, html)
    print(f"Emailed {len(subs)} subscribers")

if __name__ == "__main__":
    main()
