"""
scorer.py — Uses Claude API to score relevance to Alsatian
and generate plain-language summaries with "relevance to Alsatian" notes.

This is the AI brain of the agent.
Refactored (Month 1, Day 2): RelevanceScorer class replaces module-level client.
"""

import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

# Alsatian's core concerns — used to brief Claude on what matters.
# Deliberately left as a module-level constant: static text, no secrets,
# no per-instance variation needed (yet). SCREAMING_SNAKE_CASE = constant.
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
   low-volume manufacturer exemptions, NSF SBIR grant process.  NOTE: Articles published by IIHS or HLDI are directly relevant to Alsatian — score 
   minimum 5. The alsatian_note must be specific to THIS article's actual findings, not 
   a generic label. Explain precisely why this specific research matters for Alsatian.

7. COMPETITOR/INDUSTRY BEHAVIOR — How OEMs respond to (or fail) safety tests,
   new safety technologies, patent filings in safety space.

8. REAL-WORLD CRASH DATA — Specific crash incidents that illustrate Alsatian's
   design rationale, especially high-speed, mass-asymmetry, or side-impact cases.
"""


class RelevanceScorer:
    """Scores news articles for relevance to Alsatian using the Claude API."""

    def __init__(self, api_key=None, model="claude-sonnet-4-6"):
        # Note the quotes: "ANTHROPIC_API_KEY" is the NAME of the env var,
        # passed as a string. Without quotes it's a NameError.
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("No Anthropic API key provided")  # fail fast
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model

    def score_and_summarize(self, item):
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
            item["category"] = "other"
            return item

        prompt = f"""You are analyzing news articles for relevance to the Alsatian vehicle safety program.

ALSATIAN CONTEXT:
{ALSATIAN_CONTEXT}

ARTICLE TO ANALYZE:
Title: {title}
Source: {source}
Description: {description}

IMPORTANT: The alsatian_note must reference specific details from THIS article — statistics, vehicle names, death rates, findings. Generic phrases like "IIHS safety research" or "directly relevant" alone are not acceptable. Name the specific finding and explain precisely how it connects to Alsatian's design goals.


Please respond with a JSON object containing exactly these fields:
{{
  "score": <integer 0-10, where 0=not relevant, 10=directly relevant to Alsatian>,
  "summary": "<one sentence plain-language summary of what happened>",
  "alsatian_note": "<one sentence explaining specifically why this matters for Alsatian, or empty string if score < 4>",
  "category": "<one of: crash_incident, safety_standard, technology, regulatory, industry_behavior, biomechanics, other>"
}}

Respond with only the JSON object. No preamble, no explanation, no markdown."""

        try:
            response = self.client.messages.create(
                model=self.model,          # reads the instance's configured model
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
            # NOTE (Day 5 autopsy pending): this catches EVERYTHING, including
            # our own bugs (NameError, typos), and converts them into fake 0/10
            # scores. It kept the pipeline alive today, but it lied to us three
            # times. We will narrow this and add real logging on Day 5.
            print(f"Claude API error for '{title}': {e}")
            item["score"] = 0
            item["summary"] = description[:200] if description else ""
            item["alsatian_note"] = ""
            item["category"] = "other"

        return item

    def score_all(self, items, min_score=4):
        """
        Score all items and return only those above min_score,
        sorted by score descending.
        """
        print(f"Scoring {len(items)} items with Claude...")
        scored = []

        for i, item in enumerate(items):
            if item.get("score") is not None:
                print(f"  Pre-scored: {item.get('title', '')[:60]}... score={item['score']}")
                if item["score"] >= min_score:
                    scored.append(item)
                continue
            print(f"  Scoring {i+1}/{len(items)}: {item.get('title', '')[:60]}...")
            scored_item = self.score_and_summarize(item)
            if scored_item["score"] >= min_score:
                scored.append(scored_item)
        # Sort by score, highest first
        scored.sort(key=lambda x: x["score"], reverse=True)
        print(f"  {len(scored)} items scored {min_score}+ out of {len(items)} total")
        return scored


if __name__ == "__main__":
    # Construct the scorer — this is where __init__ finally runs,
    # the client is created, and a missing key fails fast and loud.
    scorer = RelevanceScorer()
    print(f"Scorer ready. Model: {scorer.model}")

    # Optional live test — costs one real API call. Uncomment to run.
    # test_item = {
    #     "title": "Tesla Model Y T-boned by Police Cruiser at 70 mph, One Dead",
    #     "description": "A police cruiser running a red light struck a Tesla Model Y at approximately 70 mph in an intersection. One occupant died, the second remains in critical condition. The Tesla's B-pillar showed significant intrusion.",
    #     "source_name": "CNN",
    #     "url": "https://example.com/test",
    # }
    # result = scorer.score_and_summarize(test_item)
    # print(f"\nScore: {result['score']}/10")
    # print(f"Summary: {result['summary']}")
    # print(f"Alsatian note: {result['alsatian_note']}")
    # print(f"Category: {result['category']}")
