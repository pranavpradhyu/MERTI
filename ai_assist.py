"""AI-assisted evaluation and drafting.

A self-contained heuristic engine (no external API required) that:
 - evaluates spoken/typed interview answers against consulting criteria, and
 - drafts / polishes emails.

The scoring is transparent and explainable (PR-05): it rewards structured,
specific, outcome-oriented answers that use relevant consulting language.
If an LLM API key is configured the same interface can be swapped in.
"""
import re

STRUCTURE_WORDS = ["situation", "task", "action", "result", "because", "so that",
                   "first", "then", "finally", "approach", "led", "decided",
                   "analysed", "analyzed", "identified", "recommended"]
OUTCOME_WORDS = ["result", "impact", "increased", "reduced", "saved", "grew",
                 "improved", "delivered", "achieved", "outcome", "revenue",
                 "cost", "percent", "%"]

COMPETENCY_TERMS = {
    "problem_solving": ["structure", "hypothesis", "root cause", "framework", "mece", "break down"],
    "business_acumen": ["revenue", "cost", "margin", "market", "strategy", "value", "commercial"],
    "data_analysis": ["data", "analysis", "estimate", "metric", "number", "model", "trend"],
    "communication": ["stakeholder", "audience", "message", "explain", "influence", "clear"],
    "professional_values": ["ethic", "integrity", "transparent", "confidential", "honest", "client"],
    "leadership": ["team", "led", "delegate", "feedback", "mentor", "ownership", "collaborat"],
}


def evaluate_interview_answer(prompt, transcript, competency):
    """Return (score 0-100, feedback str). Transparent heuristic scoring."""
    text = (transcript or "").strip()
    words = re.findall(r"[a-zA-Z%]+", text.lower())
    wc = len(words)

    if wc < 8:
        return 20.0, ("The answer was very brief. Aim for a structured response "
                      "with a concrete example and the outcome you drove.")

    low = text.lower()

    # 1) Depth (word count, capped) — up to 30
    depth = min(30, (wc / 120) * 30)

    # 2) Structure markers — up to 25
    struct_hits = sum(1 for w in STRUCTURE_WORDS if w in low)
    structure = min(25, struct_hits * 6)

    # 3) Specificity / outcomes (numbers, outcome words) — up to 25
    num_hits = len(re.findall(r"\d", text))
    outcome_hits = sum(1 for w in OUTCOME_WORDS if w in low)
    specificity = min(25, outcome_hits * 5 + min(10, num_hits * 2))

    # 4) Competency relevance — up to 20
    terms = COMPETENCY_TERMS.get(competency, [])
    term_hits = sum(1 for t in terms if t in low)
    relevance = min(20, term_hits * 6)

    score = round(depth + structure + specificity + relevance)
    score = max(0, min(100, score))

    # Feedback synthesis
    notes = []
    if struct_hits >= 2:
        notes.append("good use of a structured (situation → action → result) narrative")
    else:
        notes.append("structure the answer with context, your actions, then the result")
    if outcome_hits + (num_hits > 0) >= 2:
        notes.append("strong, outcome-oriented detail")
    else:
        notes.append("quantify the impact where you can")
    if term_hits >= 1:
        notes.append("relevant consulting language")
    else:
        notes.append("tie it more explicitly to the competency being assessed")

    feedback = "Strengths and growth: " + "; ".join(notes) + "."
    return float(score), feedback


# ---------------------------------------------------------------------------
# AI email drafting / polishing
# ---------------------------------------------------------------------------
def draft_email(intent, recipient_name="", sender_name="", tone="professional"):
    """Turn a short intent into a complete, professional email body."""
    intent = (intent or "").strip()
    if not intent:
        return ""
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"
    # Expand the intent into a short structured body.
    body_core = intent[0].upper() + intent[1:]
    if not body_core.endswith((".", "!", "?")):
        body_core += "."
    lines = [
        greeting,
        "",
        f"I hope you're well. I'm writing regarding the following: {body_core}",
        "",
        "Please let me know if you'd like to discuss, or if there's anything you "
        "need from me to move this forward.",
        "",
        "Best regards,",
        sender_name or "",
    ]
    return "\n".join(l for l in lines).strip()


def polish_email(body, tone="professional"):
    """Lightly rewrite an existing draft to read more professionally."""
    body = (body or "").strip()
    if not body:
        return ""
    replacements = {
        r"\bcan't\b": "cannot", r"\bwon't\b": "will not", r"\bdon't\b": "do not",
        r"\bi'm\b": "I am", r"\bthanks\b": "thank you", r"\bhey\b": "Hello",
        r"\bwanna\b": "want to", r"\bgonna\b": "going to", r"\bASAP\b": "at your earliest convenience",
    }
    out = body
    for pat, rep in replacements.items():
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    # Ensure it opens with a greeting and closes politely.
    if not re.match(r"^(hi|hello|dear)\b", out.strip(), flags=re.IGNORECASE):
        out = "Hello,\n\n" + out
    if "regard" not in out.lower() and "best" not in out.lower():
        out = out.rstrip() + "\n\nBest regards,"
    return out
