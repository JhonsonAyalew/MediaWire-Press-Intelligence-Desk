"""
scrapers/apnews.py — ported from modules/ap_scraper_core.py, adapted to the
shared `run()` interface. Includes the Cloudflare email-protection decoder
used by AP's author pages.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re

from .base import new_session, safe_log, clean_name, decode_cf_email, normalize

OUTLET = "AP News"
BASE_URL = "https://apnews.com"

session = new_session()


def _fetch(url, log_callback=None):
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        safe_log(log_callback, f"Fetch error {url}: {e}", "error")
        return None


def _extract_email_from_page(soup):
    for link in soup.find_all("a", href=re.compile(r"^mailto:")):
        email = link["href"].replace("mailto:", "").strip()
        if email:
            return email

    for link in soup.find_all("a", href=re.compile(r"/cdn-cgi/l/email-protection")):
        href = link.get("href", "")
        if "#" in href:
            decoded = decode_cf_email(href.split("#")[-1])
            if decoded and "@" in decoded:
                return decoded

    for script in soup.find_all("script"):
        text = str(script.string or "")
        if "email-protection" in text:
            for match in re.findall(r"#([a-f0-9]{20,})", text):
                decoded = decode_cf_email(match)
                if decoded and "@" in decoded and "." in decoded:
                    return decoded
    return ""


def _article_links(category_url, log_callback=None):
    safe_log(log_callback, "Fetching AP News category page", "progress")
    html = _fetch(category_url, log_callback)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for article in soup.find_all("div", class_="PagePromo"):
        a = article.find("a", href=True)
        if a and "/article/" in a["href"]:
            links.add(urljoin(BASE_URL, a["href"]))
    safe_log(log_callback, f"Found {len(links)} AP articles", "success")
    return list(links)


def _author_from_article(article_url, log_callback=None):
    html = _fetch(article_url, log_callback)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    byline = soup.find("div", class_="Page-authors")
    if not byline:
        return None
    a = byline.find("a", href=True)
    if not a:
        return None
    return clean_name(a.get_text(strip=True)), urljoin(BASE_URL, a["href"])


def _author_details(author_url, author_name, log_callback=None):
    html = _fetch(author_url, log_callback)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("div", class_="AuthorLead-jobTitle")
    title = title_tag.text.strip() if title_tag else ""

    bio_tag = soup.find("div", class_="AuthorLead-biography")
    bio = bio_tag.text.strip() if bio_tag else ""

    twitter = ""
    for link in soup.find_all("a", class_="SocialLink"):
        href = link.get("href", "").strip()
        if "twitter.com" in href or "x.com" in href:
            twitter = href
            break

    email = _extract_email_from_page(soup)

    return normalize(
        name=author_name, outlet=OUTLET, title=title, profile_url=author_url,
        email=email, twitter=twitter, bio=bio,
    )


def run(category_url, max_pages=1, max_threads=8, log_callback=None):
    links = _article_links(category_url, log_callback)
    if not links:
        return []

    author_urls = {}
    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futures = [ex.submit(_author_from_article, link, log_callback) for link in links]
        for f in as_completed(futures):
            result = f.result()
            if result:
                name, url = result
                author_urls.setdefault(url, name)

    safe_log(log_callback, f"Found {len(author_urls)} unique AP News authors", "success")

    results = []
    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futures = [ex.submit(_author_details, url, name, log_callback) for url, name in author_urls.items()]
        for f in as_completed(futures):
            author = f.result()
            if author:
                results.append(author)

    return results
