"""
scrapers/base.py — shared HTTP session, logging, and normalization helpers
used by every site-specific scraper module.
"""
import re
import requests
import urllib3

urllib3.disable_warnings()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def new_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return s


def safe_log(log_callback, msg, level="info"):
    """Never let a logging hiccup crash a scrape job."""
    if not log_callback:
        return
    try:
        log_callback(msg, level)
    except Exception:
        pass


def clean_name(name):
    if not name:
        return ""
    name = name.strip()
    name = re.sub(r"^by\s+", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}")


def extract_email(text):
    if not text:
        return ""
    match = EMAIL_RE.search(text)
    return match.group(0) if match else ""


def decode_cf_email(encoded_string):
    """Decode a Cloudflare email-protection obfuscated string."""
    try:
        if "#39;" in encoded_string:
            encoded_string = encoded_string.split("#39;")[-1].split("'")[0]
        elif "#" in encoded_string:
            encoded_string = encoded_string.split("#")[-1]
        r = int(encoded_string[:2], 16)
        return "".join(
            chr(int(encoded_string[i:i + 2], 16) ^ r)
            for i in range(2, len(encoded_string), 2)
        )
    except Exception:
        return ""


def normalize(name="", outlet="", title="", profile_url="", email="", twitter="",
              linkedin="", bio="", profile_image="", total_articles=1):
    """Common author record shape every scraper module returns."""
    return {
        "name": clean_name(name) or "Unknown",
        "outlet": outlet,
        "title": title or "",
        "profile_url": profile_url or "",
        "email": (email or "").strip().lower() if email and "@" in email else "",
        "twitter": twitter or "",
        "linkedin": linkedin or "",
        "bio": (bio or "").strip()[:600],
        "profile_image": profile_image or "",
        "total_articles": total_articles or 1,
    }
