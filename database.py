
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "alsatian.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Create the articles table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                url           TEXT UNIQUE,
                title         TEXT,
                source        TEXT,
                fetched_at    DATE,
                score         INTEGER,
                alsatian_note TEXT,
                emailed       INTEGER DEFAULT 0,
                sheeted       INTEGER DEFAULT 0
            )
        """)
        conn.commit()
    print("Database initialized")

def is_duplicate(url):
    """Return True if URL already exists in the database."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE url = ?", (url,)
        ).fetchone()
    return row is not None

def insert_article(item):
    """Insert a new article. Silently ignore if URL already exists."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO articles
                    (url, title, source, fetched_at, score, alsatian_note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item.get("url", ""),
                item.get("title", ""),
                item.get("source", ""),
                datetime.now().strftime("%Y-%m-%d"),
                item.get("score", 0),
                item.get("alsatian_note", ""),
            ))
            conn.commit()
    except Exception as e:
        print(f"Database insert error: {e}")

def filter_unsheeted(items):
    """Return only the items whose URL hasn't been written to the Google Sheet yet."""
    urls = [item.get("url", "") for item in items]
    if not urls:
        return []
    with get_connection() as conn:
        placeholders = ",".join("?" for _ in urls)
        rows = conn.execute(
            f"SELECT url FROM articles WHERE url IN ({placeholders}) AND sheeted = 1",
            urls,
        ).fetchall()
    already_sheeted = {row[0] for row in rows}
    return [item for item in items if item.get("url", "") not in already_sheeted]

def mark_sheeted(url):
    """Mark an article as written to Google Sheets."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE articles SET sheeted = 1 WHERE url = ?", (url,)
        )
        conn.commit()

if __name__ == "__main__":
    init_db()
    print(f"Database created at {DB_PATH}")
