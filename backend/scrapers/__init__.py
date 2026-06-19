from . import wired, cnbc, apnews, cnet

SITES = {
    "wired": {"label": "WIRED", "module": wired, "default_url": "https://www.wired.com/category/business/"},
    "cnbc": {"label": "CNBC", "module": cnbc, "default_url": "https://www.cnbc.com/technology/"},
    "apnews": {"label": "AP News", "module": apnews, "default_url": "https://apnews.com/politics"},
    "cnet": {"label": "CNET", "module": cnet, "default_url": "https://www.cnet.com/news/"},
}
