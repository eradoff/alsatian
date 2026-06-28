"""
scorer.py — Uses Claude API to score relevance to Alsatian
and generate plain-language summaries with "relevance to Alsatian" notes.

This is the AI brain of the agent.
"""

import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Alsatian's core concerns — used to brief Claude on what matters
ALSATIAN_CONTEXT = """
Alsatian is a consumer vehicle safety program with the following specific concerns:

1. HIGH-SPEED CRASH SURVIVABILITY — Alsatian is designed to a 70 mph frontal, 50 mph side,
   and 60 mph rear rigid barrier standard. Far above the regulatory 35-40 mph tests.

2. MASS ASYMMETRY — 75% of US vehicles are trucks/SUVs. When a lighter car hits a heavier
   vehicle, the lighter car absorbs nearly all crash energy alone. This is the core market problem.

3. PASSIVE SAFETY INNOVATIONS — Endoskeleton roll cage, occupant geometry constant (adjustable
   pedals), five-point harness with force limiters, A-pillar corner airbag, widened door sill,
   reinforced structural bulkhead, rear trunk cage.

4. ACTIVE SAFETY — Full ADAS suite including radar, LiDAR, AEB, driver monitoring, AI
   coordination layer. Integrated with passive systems.

5. CRASH BIOMECHANICS — The "third crash" (organs hitting inside of body), aortic rupture,
   deceleration trauma, force-deflection curves, plateau-shaped crush profiles.

6. REGULATORY LANDSCAPE — FMVSS standards, IIHS test protocols, NHTSA investigations,
   low-volume manufacturer exemptions, NSF SBIR grant process.

7. COMPETITOR/INDUSTRY BEHAVIOR — How OEMs respond to (or fail) safety tests,
   new safety technologies, patent filings in safety space.

8. REAL-WORLD CRASH DATA — Specific crash incidents that illustrate Alsatian's
   design rationale, especially high-speed, mass-asymmetry, or side-impact cases.
"""


def score_and_summarize(item):
    """
    Send an article to Claude for relevance scoring and summarization.
    Returns the item with added 'score', 'summary', and 'alsatian_note' fields.
    """
    title = item.get("title", "")
    description = item.get("description", "")
    source = item.get("source_name", "")

    # Skip if no useful content
    if not title or title == "No title":
        item["score"] = 0
        item["summary"] = ""
        item["alsatian_note"] = ""
        return item

    prompt = f"""You are analyzing news articles for relevance to the Alsatian vehicle safety program.

ALSATIAN CONTEXT:
{ALSATIAN_CONTEXT}

ARTICLE TO ANALYZE:
Title: {title}
Source: {source}
Description: {description}

Please respond with a JSON object containing exactly these fields:
{{
  "score": <integer 0-10, where 0=not relevant, 10=directly relevant to Alsatian>,
  "summary": "<one sentence plain-language summary of what happened>",
  "alsatian_note": "<one sentence explaining specifically why this matters for Alsatian, or empty string if score < 4>",
  "category": "<one of: crash_incident, safety_standard, technology, regulatory, industry_behavior, biomechanics, other>"
}}

Respond with only the JSON object. No preamble, no explanation, no markdown."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()

        # Parse JSON response
        result = json.loads(text)
        item["score"] = result.get("score", 0)
        item["summary"] = result.get("summary", "")
        item["alsatian_note"] = result.get("alsatian_note", "")
        item["category"] = result.get("category", "other")

    except json.JSONDecodeError as e:
        print(f"JSON parse error for '{title}': {e}")
        item["score"] = 0
        item["summary"] = description[:200] if description else ""
        item["alsatian_note"] = ""
        item["category"] = "other"

    except Exception as e:
        print(f"Claude API error for '{title}': {e}")
        item["score"] = 0
        item["summary"] = description[:200] if description else ""
        item["alsatian_note"] = ""
        item["category"] = "other"

    return item


def score_all(items, min_score=4):
    """
    Score all items and return only those above min_score,
    sorted by score descending.
    """
    print(f"Scoring {len(items)} items with Claude...")
    scored = []

    for i, item in enumerate(items):
        print(f"  Scoring {i+1}/{len(items)}: {item.get('title', '')[:60]}...")
        scored_item = score_and_summarize(item)
        if scored_item["score"] >= min_score:
            scored.append(scored_item)

    # Sort by score, highest first
    scored.sort(key=lambda x: x["score"], reverse=True)
    print(f"  {len(scored)} items scored {min_score}+ out of {len(items)} total")
    return scored


if __name__ == "__main__":
    # Test with a dummy article
    test_item = {
        "title": "Tesla Model Y T-boned by Police Cruiser at 70 mph, One Dead",
        "description": "A police cruiser running a red light struck a Tesla Model Y at approximately 70 mph in an intersection. One occupant died, the second remains in critical condition. The Tesla's B-pillar showed significant intrusion.",
        "source_name": "CNN",
        "url": "https://example.com/test",
    }
    result = score_and_summarize(test_item)
    print(f"\nScore: {result['score']}/10")
    print(f"Summary: {result['summary']}")
    print(f"Alsatian note: {result['alsatian_note']}")
    print(f"Category: {result['category']}")
