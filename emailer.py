"""
emailer.py — Sends the daily digest email via SendGrid.
Builds a clean HTML email from scored articles.
"""

import os
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "chavruta2000@gmail.com")
TO_EMAIL = os.getenv("DIGEST_TO_EMAIL", "chavruta2000@gmail.com")

# Category display names and colors
CATEGORY_META = {
    "crash_incident":    {"label": "Crash Incident",     "color": "#c0392b"},
    "safety_standard":   {"label": "Safety Standard",    "color": "#1f3a5f"},
    "technology":        {"label": "Technology",          "color": "#27ae60"},
    "regulatory":        {"label": "Regulatory",          "color": "#8e44ad"},
    "industry_behavior": {"label": "Industry Behavior",  "color": "#e67e22"},
    "biomechanics":      {"label": "Biomechanics",        "color": "#2980b9"},
    "other":             {"label": "Other",               "color": "#7f8c8d"},
}


def build_html_email(items, date_str):
    """
    Build the HTML email body from scored and sorted items.
    """
    if not items:
        body = "<p>No relevant items found today.</p>"
    else:
        cards = ""
        for item in items:
            cat = item.get("category", "other")
            meta = CATEGORY_META.get(cat, CATEGORY_META["other"])
            score = item.get("score", 0)
            alsatian_note = item.get("alsatian_note", "")

            note_html = ""
            if alsatian_note:
                note_html = f"""
                <div style="background:#fff6e5;border-left:3px solid #e0a93a;
                            padding:8px 12px;margin-top:8px;font-size:13px;color:#555;">
                    <strong>Alsatian relevance:</strong> {alsatian_note}
                </div>"""

            cards += f"""
            <div style="border:1px solid #ddd;border-radius:6px;padding:16px;
                        margin-bottom:16px;background:#fff;">
                <div style="display:flex;justify-content:space-between;
                            align-items:center;margin-bottom:8px;">
                    <span style="background:{meta['color']};color:white;
                                 padding:3px 10px;border-radius:12px;
                                 font-size:11px;font-weight:bold;">
                        {meta['label']}
                    </span>
                    <span style="color:#888;font-size:12px;">
                        Relevance: {score}/10 &nbsp;|&nbsp; {item.get('source_name','')}</span>
                </div>
                <a href="{item.get('url','#')}"
                   style="font-size:15px;font-weight:bold;color:#1f3a5f;
                          text-decoration:none;">
                    {item.get('title','')}
                </a>
                <p style="color:#444;font-size:13px;margin:8px 0 0;">
                    {item.get('summary', item.get('description','')[:200])}
                </p>
                {note_html}
            </div>"""

        body = cards

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;
             padding:20px;background:#f5f5f5;">

  <div style="background:#1f3a5f;color:white;padding:20px 24px;
              border-radius:8px 8px 0 0;">
    <h1 style="margin:0;font-size:20px;">Alsatian Safety Intelligence</h1>
    <p style="margin:4px 0 0;font-size:13px;opacity:0.8;">
        Daily digest &nbsp;&middot;&nbsp; {date_str} &nbsp;&middot;&nbsp;
        {len(items)} relevant items
    </p>
  </div>

  <div style="background:#fff;padding:20px 24px;border-radius:0 0 8px 8px;
              border:1px solid #ddd;border-top:none;">
    {body}
  </div>

  <p style="text-align:center;color:#aaa;font-size:11px;margin-top:16px;">
    Alsatian by REX Auto &middot; Safety Intelligence Agent &middot;
    <a href="http://your-domain.com" style="color:#aaa;">View online</a>
  </p>

</body>
</html>"""

    return html


def send_digest(items):
    """
    Send the daily digest email via SendGrid.
    """
    if not SENDGRID_API_KEY:
        print("WARNING: SENDGRID_API_KEY not set — skipping email")
        return False

    date_str = datetime.now().strftime("%B %d, %Y")
    subject = f"Alsatian Safety Intelligence — {date_str} ({len(items)} items)"
    html_content = build_html_email(items, date_str)

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=TO_EMAIL,
        subject=subject,
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent: status {response.status_code}")
        return True
    except Exception as e:
        print(f"SendGrid error: {e}")
        return False


if __name__ == "__main__":
    # Test with dummy data
    test_items = [{
        "title": "Tesla T-boned at 70 mph by Police Cruiser — One Dead",
        "summary": "A police cruiser struck a Tesla Model Y at 70 mph at an intersection, killing one occupant and leaving another in critical condition.",
        "alsatian_note": "A 70 mph lateral impact is exactly the severe side-impact case Alsatian's widened sill and reinforced door cross-beams (Innovations 11 and 13) are designed to address.",
        "url": "https://example.com",
        "source_name": "CNN",
        "score": 9,
        "category": "crash_incident",
    }]
    send_digest(test_items)
