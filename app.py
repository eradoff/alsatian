"""
app.py — Flask web application for the Alsatian Safety Intelligence Agent.

Routes:
  GET /           — Today's digest webpage
  GET /run        — Manually trigger a fetch+score+email cycle
  GET /health     — Health check for AWS monitoring

Scheduler:
  Runs the full pipeline daily at 7:00 AM UTC (adjust to your timezone)
"""

#python library
import os
import json
from datetime import datetime
from functools import wraps


#third party
from flask import Flask, render_template_string, jsonify, redirect, request, Response  
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

#modules
from sheets_writer import append_items
from database import insert_article, filter_unsheeted, mark_sheeted
from fetcher2 import fetch_all
from scorer import RelevanceScorer
from emailer import send_digest, build_html_email

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# In-memory store for latest digest results
# On AWS we'd use a database, but this works for v1
latest_results = {
    "items": [],
    "last_run": None,
    "status": "No run yet"
}

def require_auth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != os.getenv("SITE_USER") \
           or auth.password != os.getenv("SITE_PASS"):
            return Response("Auth required", 401,
                            {"WWW-Authenticate": 'Basic realm="Alsatian"'})
        return f(*args, **kwargs)
    return wrapped

def run_pipeline(trigger="scheduled"):
    """
    Full pipeline: fetch → score → email → store results.
    Called by scheduler and manual trigger.
    """
    global latest_results
    print(f"\n{'='*50}")
    print(f"Pipeline started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
  

    try:
        # Step 1: Fetch from all sources
        print("\nStep 1: Fetching articles...")
        raw_items = fetch_all(days_back=1)

        # Step 2: Score and filter with Claude
        print("\nStep 2: Scoring with Claude...")
        scorer = RelevanceScorer()
        scored_items = scorer.score_all(raw_items, min_score=4)

        # Step 3: Store articles in database (dedupes by URL on insert)
        print("\nStep 3: Storing articles in database...")
        for item in scored_items:
            insert_article(item)

        # Step 4: Send email digest
        print("\nStep 4: Sending email digest...")
        email_sent = send_digest(scored_items)

        # Step 5: Append new-to-sheet items to Google Sheet
        print("\nStep 5: Appending to Google Sheet...")
        new_to_sheet = filter_unsheeted(scored_items)
        if append_items(new_to_sheet):
            for item in new_to_sheet:
                mark_sheeted(item.get("url", ""))

        # Step 6: Store results for web display
        latest_results = {
            "items": scored_items,
            "last_run": datetime.now().strftime("%B %d, %Y at %H:%M UTC"),
            "status": f"OK — {len(scored_items)} relevant items found, email {'sent' if email_sent else 'failed'}",
            "trigger": ("manual" if trigger == "manual" else "scheduled")
        }

        print(f"\nPipeline complete: {len(scored_items)} items, email {'sent' if email_sent else 'failed'}")

    except Exception as e:
        print(f"Pipeline error: {e}")
        latest_results["status"] = f"Error: {str(e)}"


# ---- Web routes ----

DIGEST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Alsatian Safety Intelligence</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 780px; margin: 0 auto;
               padding: 20px; background: #f5f5f5; }
        .header { background: #1f3a5f; color: white; padding: 20px 24px;
                  border-radius: 8px 8px 0 0; }
        .header h1 { margin: 0; font-size: 22px; }
        .header p { margin: 4px 0 0; font-size: 13px; opacity: 0.8; }
        .content { background: white; padding: 20px 24px;
                   border-radius: 0 0 8px 8px; border: 1px solid #ddd;
                   border-top: none; }
        .card { border: 1px solid #ddd; border-radius: 6px; padding: 16px;
                margin-bottom: 16px; background: white; }
        .badge { display: inline-block; color: white; padding: 3px 10px;
                 border-radius: 12px; font-size: 11px; font-weight: bold; }
        .score { color: #888; font-size: 12px; }
        .card-title { font-size: 15px; font-weight: bold; color: #1f3a5f;
                      text-decoration: none; display: block; margin: 8px 0 4px; }
        .card-title:hover { text-decoration: underline; }
        .card-summary { color: #444; font-size: 13px; margin: 4px 0; }
        .alsatian-note { background: #fff6e5; border-left: 3px solid #e0a93a;
                         padding: 8px 12px; margin-top: 8px; font-size: 13px;
                         color: #555; }
        .status-bar { background: #eaf1f8; border: 1px solid #ccc; padding: 10px 16px;
                      border-radius: 6px; margin-bottom: 20px; font-size: 13px; color: #555; }
        .run-btn { background: #1f3a5f; color: white; padding: 8px 18px;
                   border: none; border-radius: 4px; cursor: pointer;
                   font-size: 13px; text-decoration: none; display: inline-block; }
        .run-btn:hover { background: #2c5282; }
        .empty { text-align: center; color: #888; padding: 40px; }
        .cat-crash    { background: #c0392b; }
        .cat-standard { background: #1f3a5f; }
        .cat-tech     { background: #27ae60; }
        .cat-reg      { background: #8e44ad; }
        .cat-industry { background: #e67e22; }
        .cat-bio      { background: #2980b9; }
        .cat-other    { background: #7f8c8d; }
    </style>
</head>
<body>

<div class="header">
    <h1>Alsatian Safety Intelligence</h1>
    <p>Daily digest &nbsp;&middot;&nbsp; {{ last_run or 'Not yet run' }}
       &nbsp;&middot;&nbsp; {{ items|length }} relevant items</p>
</div>

<div class="content">

    <div class="status-bar">
        <strong>Status:</strong> {{ status }}
        &nbsp;&nbsp;
        &middot; {{ trigger }}
        <a href="/run" class="run-btn">Run Now</a>
    </div>

    {% if items %}
        {% for item in items %}
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="badge cat-{{ item.category|replace('_','') if item.category else 'other' }}"
                      style="background:{{ cat_colors.get(item.category, '#7f8c8d') }}">
                    {{ cat_labels.get(item.category, 'Other') }}
                </span>
                <span class="score">
                    Relevance: {{ item.score }}/10 &nbsp;|&nbsp; {{ item.source_name }}
                </span>
            </div>
            <a class="card-title" href="{{ item.url }}" target="_blank">
                {{ item.title }}
            </a>
            <p class="card-summary">{{ item.summary or item.description[:200] }}</p>
            {% if item.alsatian_note %}
            <div class="alsatian-note">
                <strong>Alsatian relevance:</strong> {{ item.alsatian_note }}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    {% else %}
        <div class="empty">
            <p>No digest yet. Click <strong>Run Now</strong> to fetch today's articles.</p>
        </div>
    {% endif %}

</div>

<p style="text-align:center;color:#aaa;font-size:11px;margin-top:16px;">
    Alsatian by REX Auto &middot; Safety Intelligence Agent
</p>

</body>
</html>
"""

CAT_COLORS = {
    "crash_incident":    "#c0392b",
    "safety_standard":   "#1f3a5f",
    "technology":        "#27ae60",
    "regulatory":        "#8e44ad",
    "industry_behavior": "#e67e22",
    "biomechanics":      "#2980b9",
    "other":             "#7f8c8d",
}

CAT_LABELS = {
    "crash_incident":    "Crash Incident",
    "safety_standard":   "Safety Standard",
    "technology":        "Technology",
    "regulatory":        "Regulatory",
    "industry_behavior": "Industry Behavior",
    "biomechanics":      "Biomechanics",
    "other":             "Other",
}


@app.route("/")
@require_auth
def index():
   
    return render_template_string(
        DIGEST_TEMPLATE,
        **latest_results,
        cat_colors=CAT_COLORS,
        cat_labels=CAT_LABELS,
    )


@app.route("/run")
@require_auth
def manual_run():
    
    """Manually trigger the pipeline."""
      
    run_pipeline(trigger="manual")
    
    return redirect("/")


@app.route("/health")
@require_auth
def health():
    
    """Health check for AWS load balancer / monitoring."""
    return jsonify({
        "status": "healthy",
        "last_run": latest_results["last_run"],
        "items": len(latest_results["items"])
    })


# ---- Scheduler ----

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=run_pipeline,
    trigger="cron",
    hour=7,       # 7:00 AM UTC = adjust for your timezone
    minute=0,
    id="daily_digest"
)
scheduler.start()


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    print(f"Starting Alsatian News Agent on port {port}")
    print(f"Daily digest scheduled for 07:00 UTC")
    print(f"Visit http://localhost:{port} to view digest")
    print(f"Visit http://localhost:{port}/run to trigger manually")
    app.run(host="0.0.0.0", port=port, debug=False)
