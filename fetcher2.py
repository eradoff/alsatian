"""
fetcher.py — Pulls articles from NewsAPI and NHTSA RSS 
feeds.
Two data sources:
  1. NewsAPI — searches for crash/safety news by keyword
  2. NHTSA RSS — official recalls, investigations, safety notices
"""

import os
import requests
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import init_db
from bs4 import BeautifulSoup

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# NHTSA public RSS feeds — no API key needed
NHTSA_API_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
IIHS_FEED = "http://feeds.feedburner.com/iihs"

NTSB_RSS = "https://www.ntsb.gov/_layouts/15/feed.aspx?xsl=1&web=%2F&page=674e62a9-4f3b-4058-846b-150bc1c21aa0&wp=4d4ae30f-92c9-4e6c-9c58-6bac99822531&pageurl=%2FPages%2FRSS%2DFeed%2DPage%2Easpx"

RECALL_MAKES = [
    ("FORD", "F-150"),
    ("TOYOTA", "CAMRY"),
    ("TESLA", "MODEL 3"),
    ("CHEVROLET", "SILVERADO"),
    ("HONDA", "CIVIC"),
    ("BMW", "3 Series"),
    ("MERCEDES-BENZ", "C-CLASS"),
    ("VOLKSWAGEN", "JETTA"),
]
# Keywords relevant to Alsatian's program
# Grouped by category for relevance scoring later
SEARCH_QUERIES = [
    "car crash fatality",
    "vehicle side impact crash",
    "A-pillar intrusion crash",
    "automobile crash test",
    "vehicle occupant death injury",
    "car crash mass asymmetry SUV sedan",
    "passive safety innovation automotive",
    "crash test standard 2026",
    "vehicle structural failure crash",
    "car safety innovations",
    "automotive airbag failure",
]


def fetch_iihs_news():
    items = []
    seen = set()
    r = requests.get(IIHS_FEED, timeout=10, allow_redirects=True)
    print(f"DEBUG: IIHS_FEED={IIHS_FEED}")
    print(f"DEBUG: r.status={r.status_code} len={len(r.text)}")
    feed = feedparser.parse(r.text)
    print(f"IIHS: {len(feed.entries)} entries found")
    for entry in feed.entries:
        try:
            url = entry.link
            if url in seen:
                continue
            seen.add(url)
            title = entry.title
            desc_soup = BeautifulSoup(entry.description, "html.parser")
            span = desc_soup.find("span", class_="xhtml-content")
            description = span.get_text(strip=True) if span else ""
            pub_date = entry.get("published", "")
            items.append({
                "title": title,
                "url": url,
                "description": description,
                "published_date": pub_date,
                "source": "IIHS",
                "score" : 7,
                "alsatian_note": "IIHS safety research",
            })
        except Exception as e:
            print(f"IIHS parse error: {e}")
            continue
    print(f"IIHS: {len(items)} items fetched")
    return items


def fetch_news_articles(days_back=1):
    """
    Fetch articles from NewsAPI for all search queries.
    Returns a deduplicated list of article dicts.
    """
    if not NEWS_API_KEY:
        print("WARNING: NEWS_API_KEY not set")
        return []

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    seen_urls = set()
    articles = []

    for query in SEARCH_QUERIES:
        try:
            response = requests.get(NEWS_API_URL, params={
                "q": query,
                "from": from_date,
                "sortBy": "relevancy",
                "language": "en",
                "pageSize": 5,
                "apiKey": NEWS_API_KEY,
            }, timeout=10)

            if response.status_code != 200:
                print(f"NewsAPI error for query '{query}': {response.status_code}")
                continue

            data = response.json()

            for article in data.get("articles", []):
                url = article.get("url", "")
                if url in seen_urls or not url:
                    continue  # Skip duplicates
                seen_urls.add(url)

                articles.append({
                    "source": "NewsAPI",
                    "query": query,
                    "title": article.get("title", "No title"),
                    "description": article.get("description", ""),
                    "url": url,
                    "published_at": article.get("publishedAt", ""),
                    "source_name": article.get("source", {}).get("name", "Unknown"),
                })

        except Exception as e:
            print(f"Error fetching NewsAPI query '{query}': {e}")

    print(f"Fetched {len(articles)} unique articles from NewsAPI")
    return articles



def fetch_nhtsa_recalls():
    items = []
    seen = set()
    for make, model in RECALL_MAKES:
        try:
            response = requests.get(
                NHTSA_API_URL,
                params={"make": make, "model": model, "modelYear": "2024"},
                timeout=10
            )
            if response.status_code != 200:
                continue
            results = response.json().get("results", [])
            for r in results[:3]:
                campaign = r.get("NHTSACampaignNumber", "")
                component = r.get("Component", "")
                key = f"{make}_{model}_{campaign}_{component}"
                if not (campaign or component) or key in seen:
                    continue
                seen.add(key)
                items.append({
                    "source": "NHTSA",
                    "feed_name": "NHTSA Recalls",
                    "title": f"Recall: {make} {model} — {component}",
                    "description": r.get("Summary", "") + " " + r.get("Consequence", ""),
                  
                    "url": f"https://www.nhtsa.gov/recalls?nhtsaId={r.get('NHTSACampaignNumber','')}",
		    "published_at": r.get("ReportReceivedDate", ""),
                    "source_name": "NHTSA",
                })
        except Exception as e:
            print(f"NHTSA API error for {make}: {e}")
    print(f"Fetched {len(items)} items from NHTSA API")
    return items


def fetch_ntsb_rss():
    items = []
    try:
        feed = feedparser.parse(NTSB_RSS)
        for entry in feed.entries[:10]:
            url = entry.get("link", "")
            if not url:
                continue
            items.append({
                "source": "NTSB",
                "feed_name": "NTSB News",
                "title": entry.get("title", "No title"),
                "description": entry.get("summary", ""),
                "url": url,
                "published_at": entry.get("published", ""),
                "source_name": "NTSB",
            })
        print(f"Fetched {len(items)} items from NTSB RSS")
    except Exception as e:
        print(f"NTSB RSS error: {e}")
    return items

def fetch_all(days_back=1):
    """
    Fetch from all sources and return combined list.
    """
    articles = fetch_news_articles(days_back=days_back)
    nhtsa_items = fetch_nhtsa_recalls()
    ntsb_items = fetch_ntsb_rss()
    iihs_items = fetch_iihs_news()
    all_items = articles + nhtsa_items + ntsb_items + iihs_items
    
    init_db()
    print(f"Total items fetched: {len(all_items)}")
    return all_items


if __name__ == "__main__":
    # Test the fetcher directly
    items = fetch_all()
    for item in items[:5]:
        print(f"\n[{item['source']}] {item['title']}")
        print(f"  URL: {item['url']}")
