"""
scrapers/cnbc.py — ported from modules/scraper_core.py (CNBC variant),
adapted to the shared `run()` interface.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import time
import random
from bs4 import BeautifulSoup

from .base import new_session, safe_log, normalize

OUTLET = "CNBC"
BASE_URL = "https://www.cnbc.com"

session = new_session()


def _article_links(category_url, max_pages=1, log_callback=None):
    links = []
    for page in range(1, max_pages + 1):
        page_url = f"{category_url}?page={page}" if page > 1 else category_url
        safe_log(log_callback, f"CNBC page {page}/{max_pages}", "progress")
        try:
            time.sleep(random.uniform(0.3, 0.8))
            r = session.get(page_url, timeout=15, verify=False)
            soup = BeautifulSoup(r.text, "html.parser")
            found = 0
            for selector in ["div.Card-standardBreakerCard", "div.Card-rectangleCard",
                              "div.Card-mediaCard", "a.Card-title"]:
                for elem in soup.select(selector):
                    a = elem if selector == "a.Card-title" else (elem.select_one("a.Card-title") or elem.select_one("a"))
                    if not a or not a.get("href"):
                        continue
                    href = a["href"]
                    if not href.startswith("http"):
                        href = f"{BASE_URL}{href}"
                    if href not in links:
                        links.append(href)
                        found += 1
                if found >= 25:
                    break
            safe_log(log_callback, f"CNBC page {page}: {found} articles", "info")
            if found == 0:
                break
        except Exception as e:
            safe_log(log_callback, f"CNBC page error: {e}", "error")
            break
    return links


def _author_from_article(article_url, log_callback=None):
    try:
        r = session.get(article_url, timeout=10, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")

        a = soup.select_one("a.Author-authorName")
        if a:
            name = a.text.strip()
            href = a.get("href", "")
            url = href if href.startswith("http") else f"{BASE_URL}{href}"
            return name, url

        meta = soup.find("meta", {"name": "author"}) or soup.find("meta", {"property": "article:author"})
        if meta and meta.get("content"):
            name = meta["content"].strip()
            slug = name.lower().replace(" ", "-").replace(".", "").replace(",", "")
            return name, f"{BASE_URL}/{slug}/"
    except Exception as e:
        safe_log(log_callback, f"CNBC article error: {e}", "debug")
    return None


def _author_details(author_url, author_name, log_callback=None):
    title = bio = twitter = linkedin = ""
    try:
        r = session.get(author_url, timeout=10, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")

        role_elem = soup.select_one("span.RenderBioDetails-jobTitle") or soup.select_one("div.author-title")
        if role_elem:
            title = role_elem.text.strip()

        bio_elem = soup.select_one("div.RenderBioDetails-bioText") or soup.select_one("div.author-bio")
        if bio_elem:
            bio = bio_elem.text.strip()[:500]

        for link in soup.select("a[href*='twitter.com'], a[href*='x.com']"):
            href = link.get("href", "")
            if href and not href.rstrip("/").endswith(("twitter.com", "x.com")):
                twitter = href
                break

        li = soup.select_one("a[href*='linkedin.com']")
        if li:
            linkedin = li.get("href", "")
    except Exception as e:
        safe_log(log_callback, f"CNBC author error: {e}", "warning")

    return normalize(
        name=author_name, outlet=OUTLET, title=title, profile_url=author_url,
        twitter=twitter, linkedin=linkedin, bio=bio,
    )


def run(category_url, max_pages=1, max_threads=10, log_callback=None):
    links = _article_links(category_url, max_pages, log_callback)
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

    safe_log(log_callback, f"Found {len(author_urls)} unique CNBC authors", "success")

    results = []
    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futures = [ex.submit(_author_details, url, name, log_callback) for url, name in author_urls.items()]
        for f in as_completed(futures):
            author = f.result()
            if author:
                results.append(author)

    return results
