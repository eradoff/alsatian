import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

HEADERS = [
    "Date", "Source", "Title", "URL", "Relevance Score", "Alsatian Note"
]

def get_sheet():
    creds = Credentials.from_service_account_file(
        os.getenv("GOOGLE_CREDENTIALS_PATH"),
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID"))
    return sheet.sheet1

def ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if first_row != HEADERS:
        sheet.insert_row(HEADERS, 1)

def append_items(items):
    """
    Append scored items to the Google Sheet.
    Each item should have: source, title, url, score, alsatian_note
    Never overwrites — always appends.
    Returns True if the write succeeded (or there was nothing to write), False on error.
    """
    try:
        sheet = get_sheet()
        ensure_headers(sheet)
        today = datetime.now().strftime("%Y-%m-%d")
        rows = []
        for item in items:
            rows.append([
                today,
                item.get("source", ""),
                item.get("title", ""),
                item.get("url", ""),
                item.get("score", ""),
                item.get("alsatian_note", ""),
            ])
        if rows:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"Appended {len(rows)} rows to Google Sheet")
        else:
            print("No rows to append")
        return True
    except Exception as e:
        print(f"Google Sheets error: {e}")
        return False

if __name__ == "__main__":
    # Quick test
    test_items = [{
        "source": "Test",
        "title": "Test article",
        "url": "https://example.com",
        "score": 7,
        "alsatian_note": "Test note"
    }]
    append_items(test_items)
