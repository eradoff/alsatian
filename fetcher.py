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

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# NHTSA public RSS feeds — no API key needed
NHTSA_API_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"

NTSB_RSS = "https://www.ntsb.gov/Pages/RSS.aspx"

RECALL_MAKES = [
    ("Ford", "F-150"),
    ("Toyota", "Camry"),
    ("Tesla", "Model 3"),
    ("Chevrolet", "Silverado"),
    ("Honda", "Civic"),
    ("BMW", "3 Series"),
    ("Mercedes-Benz", "C-Class"),
    ("Volkswagen", "Jetta"),
]
# Keywords relevant to Alsatian's program
# Grouped by category for relevance scoring later
SEARCH_QUERIES = [
    "car crash fatality highway",
    "vehicle side impact crash",
    "A-pillar intrusion crash",
    "automotive crash test IIHS NHTSA",
    "vehicle occupant death injury",
    "car crash mass asymmetry SUV sedan",
    "passive safety innovation automotive",
    "crash test standard 2026",
    "vehicle structural failure crash",
    "automotive airbag failure",
]


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
                title = r.get("Subject", "")
                if not title or title in seen:
                    continue
                seen.add(title)
                items.append({
                    "source": "NHTSA",
                    "feed_name": "NHTSA Recalls",
                    "title": f"Recall: {make} {model} — {title}",
                    "description": r.get("Consequence", ""),
                    "url": f"https://www.nhtsa.gov/vehicle/{make}",
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
    all_items = articles + nhtsa_items + ntsb_items
    print(f"Total items fetched: {len(all_items)}")
    return all_items


if __name__ == "__main__":
    # Test the fetcher directly
    items = fetch_all()
    for item in items[:5]:
        print(f"\n[{item['source']}] {item['title']}")
        print(f"  URL: {item['url']}")
