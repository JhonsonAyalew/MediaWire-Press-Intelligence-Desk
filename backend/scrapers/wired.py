"""
scrapers/wired.py — ported from the desktop tool's modules/wired_scraper_core.py,
adapted to the shared `run()` interface used by the Flask job runner.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time
import random

from .base import new_session, safe_log, clean_name, extract_email, normalize

OUTLET = "WIRED"
BASE_URL = "https://www.wired.com"

session = new_session()


def _scrape_article_links(category_url, log_callback=None):
    safe_log(log_callback, f"Fetching WIRED category page", "progress")
    try:
        r = session.get(category_url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for card in soup.find_all("div", class_="summary-item"):
            a = card.find("a", class_="summary-item__hed-link")
            if a and a.get("href"):
                links.append(urljoin(BASE_URL, a["href"]))
        safe_log(log_callback, f"Found {len(links)} articles", "success")
        return links
    except Exception as e:
        safe_log(log_callback, f"Category page error: {e}", "error")
        return []


def _author_url_from_article(article_url, log_callback=None):
    try:
        r = session.get(article_url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        a = soup.select_one("a.byline__name-link")
        if a and a.get("href"):
            return clean_name(a.get_text(strip=True)), urljoin(BASE_URL, a["href"])
    except Exception as e:
        safe_log(log_callback, f"Article error: {e}", "debug")
    return None


def _author_details(author_url, author_name, log_callback=None):
    try:
        r = session.get(author_url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        title = ""
        title_tag = soup.select_one('[data-testid="ContributorHeaderTitle"]')
        if title_tag:
            title = title_tag.get_text(strip=True)

        bio = ""
        email = ""
        bio_tag = soup.select_one('[data-testid="ContributorHeaderBio"]')
        if bio_tag:
            bio = bio_tag.get_text(" ", strip=True)
            email = extract_email(bio)

        profile_image = ""
        img = soup.find("img", class_="contributor__image")
        if img and img.get("src"):
            profile_image = img["src"]

        twitter = linkedin = ""
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if ("twitter.com" in href or "x.com" in href) and not twitter:
                twitter = href
            elif "linkedin.com" in href and not linkedin:
                linkedin = href
            elif "mailto:" in href and not email:
                email = href.replace("mailto:", "")

        return normalize(
            name=author_name, outlet=OUTLET, title=title, profile_url=author_url,
            email=email, twitter=twitter, linkedin=linkedin, bio=bio,
            profile_image=profile_image,
        )
    except Exception as e:
        safe_log(log_callback, f"Author scrape error: {e}", "error")
        return None


def run(category_url, max_pages=1, max_threads=8, log_callback=None):
    links = _scrape_article_links(category_url, log_callback)
    if not links:
        return []

    author_urls = {}
    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futures = [ex.submit(_author_url_from_article, link, log_callback) for link in set(links)]
        for f in as_completed(futures):
            result = f.result()
            if result:
                name, url = result
                author_urls.setdefault(url, name)

    safe_log(log_callback, f"Found {len(author_urls)} unique WIRED authors", "success")

    results = []
    items = list(author_urls.items())
    for i in range(0, len(items), 10):
        batch = items[i:i + 10]
        with ThreadPoolExecutor(max_workers=min(max_threads, len(batch))) as ex:
            futures = [ex.submit(_author_details, url, name, log_callback) for url, name in batch]
            for f in as_completed(futures):
                author = f.result()
                if author:
                    results.append(author)
        if i + 10 < len(items):
            time.sleep(random.uniform(0.4, 0.9))

    return results
