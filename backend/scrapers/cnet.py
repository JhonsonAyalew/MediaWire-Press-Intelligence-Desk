"""
scrapers/cnet.py — ported from modules/cnet_scraper_core.py, adapted to the
shared `run()` interface.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import time
import random
from bs4 import BeautifulSoup

from .base import new_session, safe_log, clean_name, normalize

OUTLET = "CNET"
BASE_URL = "https://www.cnet.com"

session = new_session()


def _article_links(max_pages=1, log_callback=None):
    links = []
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/news/" if page == 1 else f"{BASE_URL}/news/{page}/"
        safe_log(log_callback, f"CNET page {page}/{max_pages}", "progress")
        try:
            r = session.get(url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a.c-storiesNeonLatest_story"):
                href = a.get("href")
                if href:
                    full = urljoin(BASE_URL, href)
                    if full not in links:
                        links.append(full)
            time.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            safe_log(log_callback, f"CNET page error: {e}", "error")
            break
    safe_log(log_callback, f"Found {len(links)} CNET articles", "success")
    return links


def _author_from_article(article_url, log_callback=None):
    try:
        r = session.get(article_url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        name_tag = soup.select_one('[data-cy="authorName"]')
        if not name_tag:
            return None
        name = clean_name(name_tag.get_text(strip=True))

        profile_tag = soup.select_one('a[rel="author"]')
        profile_url = urljoin(BASE_URL, profile_tag["href"]) if profile_tag and profile_tag.get("href") else ""

        return name, profile_url
    except Exception as e:
        safe_log(log_callback, f"CNET article error: {e}", "debug")
        return None


def _author_details(profile_url, author_name, log_callback=None):
    twitter = email = ""
    bio = ""
    try:
        if profile_url:
            r = session.get(profile_url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for link in soup.select(".c-socialSharebar_container a"):
                href = link.get("href", "")
                if "twitter.com" in href or "x.com" in href:
                    twitter = href
                elif "mailto:" in href:
                    email = href.replace("mailto:", "")
            bio_tag = soup.select_one(".c-personCard_bio, .c-authorBio_text")
            if bio_tag:
                bio = bio_tag.get_text(" ", strip=True)[:500]
    except Exception as e:
        safe_log(log_callback, f"CNET author error: {e}", "warning")

    return normalize(
        name=author_name, outlet=OUTLET, profile_url=profile_url,
        email=email, twitter=twitter, bio=bio,
    )


def run(category_url=None, max_pages=1, max_threads=10, log_callback=None):
    links = _article_links(max_pages, log_callback)
    if not links:
        return []

    author_urls = {}
    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futures = [ex.submit(_author_from_article, link, log_callback) for link in links]
        for f in as_completed(futures):
            result = f.result()
            if result:
                name, url = result
                if name and name.lower() != "not found":
                    author_urls.setdefault(url or name, (name, url))

    safe_log(log_callback, f"Found {len(author_urls)} unique CNET authors", "success")

    results = []
    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futures = [ex.submit(_author_details, url, name, log_callback) for name, url in author_urls.values()]
        for f in as_completed(futures):
            author = f.result()
            if author:
                results.append(author)

    return results
