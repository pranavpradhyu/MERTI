"""Domain content: competencies, assessments, development library,
skill taxonomy (resume parsing) and AI interview templates."""

COMPETENCIES = {
    "problem_solving": {"name": "Problem Solving & Structuring",
        "blurb": "Framing ambiguous problems, hypothesis-led thinking, MECE structuring."},
    "business_acumen": {"name": "Business & Commercial Acumen",
        "blurb": "Strategy, markets, value creation and commercial judgement."},
    "data_analysis": {"name": "Quantitative & Data Analysis",
        "blurb": "Estimation, interpreting data, drawing defensible conclusions."},
    "communication": {"name": "Communication & Influence",
        "blurb": "Structured, audience-aware, concise and persuasive communication."},
    "professional_values": {"name": "Professional Values & Judgement",
        "blurb": "Integrity, client stewardship, ethics and responsible judgement."},
    "leadership": {"name": "Leadership & Teaming",
        "blurb": "Collaboration, ownership, feedback and leading through others."},
}

ASSESSMENT_TYPES = {
    "core_capability": {"name": "Core Consulting Capability",
        "description": "A broad adaptive assessment spanning all six competencies, with an AI interview.",
        "competencies": list(COMPETENCIES.keys()), "icon": "◆"},
    "problem_solving": {"name": "Problem Solving & Case Structuring",
        "description": "Case-based, hypothesis-led problem solving and structuring.",
        "competencies": ["problem_solving", "business_acumen"], "icon": "◑"},
    "data_analysis": {"name": "Quantitative & Data Reasoning",
        "description": "Estimation, data interpretation and quantitative judgement.",
        "competencies": ["data_analysis", "problem_solving"], "icon": "▲"},
    "communication": {"name": "Communication & Influence",
        "description": "Structured communication, synthesis and stakeholder influence.",
        "competencies": ["communication", "leadership"], "icon": "✦"},
    "values_judgement": {"name": "Professional Values & Judgement",
        "description": "Ethics, client stewardship and responsible professional judgement.",
        "competencies": ["professional_values", "leadership"], "icon": "●"},
    "resume_based": {"name": "Personalised (Resume-Based)",
        "description": "Adaptive questions and an AI interview tailored to your uploaded resume.",
        "competencies": list(COMPETENCIES.keys()), "icon": "❖", "resume": True},
}

DEVELOPMENT_LIBRARY = {
    "problem_solving": [
        "Practise structuring problems top-down with issue trees before diving into detail.",
        "Lead with a hypothesis, then gather only the evidence that confirms or refutes it.",
        "Review classic case frameworks (profitability, market entry) and when each applies."],
    "business_acumen": [
        "Read company teardowns to connect strategy decisions to commercial outcomes.",
        "Learn to quantify value: tie every recommendation to revenue, cost or risk impact.",
        "Study a handful of industries' economics so you can orient quickly in a new sector."],
    "data_analysis": [
        "Drill market-sizing and estimation to build speed and sound assumptions.",
        "Practise reading charts critically — ask what the data does and does not prove.",
        "Sanity-check every number against a back-of-envelope benchmark before concluding."],
    "communication": [
        "Use the pyramid principle: answer first, then supporting arguments, then detail.",
        "Tailor the message to the audience's priorities and level of detail.",
        "Practise one-sentence 'so what' summaries after any analysis."],
    "professional_values": [
        "Review professional-conduct scenarios on confidentiality and conflicts of interest.",
        "When unsure, default to transparency with the client and escalate early.",
        "Separate what the client wants to hear from what the evidence supports."],
    "leadership": [
        "Seek and act on feedback deliberately; close the loop with those who gave it.",
        "Practise delegating with clear outcomes rather than prescribing every step.",
        "Build psychological safety: invite dissent before decisions are locked."],
}

# --- Skill taxonomy for resume parsing (keyword -> canonical skill) ---
# Grouped by the competency the skill most informs.
SKILL_TAXONOMY = {
    "problem_solving": [
        "problem solving", "root cause", "hypothesis", "issue tree", "mece",
        "structuring", "case study", "frameworks", "analytical", "critical thinking"],
    "business_acumen": [
        "strategy", "business development", "market research", "go-to-market",
        "p&l", "pricing", "commercial", "product management", "operations",
        "consulting", "mergers", "m&a", "due diligence", "business analysis"],
    "data_analysis": [
        "python", "sql", "excel", "power bi", "tableau", "r ", "statistics",
        "data analysis", "data science", "machine learning", "forecasting",
        "modeling", "modelling", "analytics", "pandas", "numpy", "visualization"],
    "communication": [
        "presentation", "stakeholder", "storytelling", "writing", "public speaking",
        "negotiation", "client management", "powerpoint", "reporting", "facilitation"],
    "professional_values": [
        "compliance", "governance", "ethics", "risk management", "audit",
        "confidentiality", "quality assurance", "regulatory"],
    "leadership": [
        "leadership", "team lead", "mentoring", "project management", "agile",
        "scrum", "stakeholder management", "people management", "delegation",
        "coaching", "cross-functional"],
}

# Flatten keyword -> competency for quick lookup, and keyword -> display label.
SKILL_LOOKUP = {}
for _comp, _kw_list in SKILL_TAXONOMY.items():
    for _kw in _kw_list:
        SKILL_LOOKUP[_kw.strip()] = _comp


def _title(s):
    special = {"sql": "SQL", "p&l": "P&L", "m&a": "M&A", "mece": "MECE",
               "power bi": "Power BI", "go-to-market": "Go-to-Market",
               "numpy": "NumPy", "r ": "R"}
    key = s.strip()
    return special.get(key, key.title())


SKILL_LABELS = {kw: _title(kw) for kw in SKILL_LOOKUP}

# --- AI interview question templates ---
# {skill} filled from resume; competency behavioural prompts otherwise.
INTERVIEW_COMPETENCY_PROMPTS = {
    "problem_solving": [
        "Walk me through a complex, ambiguous problem you solved. How did you structure it?",
        "Tell me about a time your first hypothesis was wrong. What did you do next?"],
    "business_acumen": [
        "Describe a decision where you weighed commercial trade-offs. What drove your call?",
        "Tell me about a time you identified a way to create or protect business value."],
    "data_analysis": [
        "Describe an analysis where the data challenged the prevailing assumption.",
        "Walk me through how you'd estimate the size of a market you know little about."],
    "communication": [
        "Tell me about a time you had to influence a senior stakeholder who disagreed with you.",
        "Describe how you communicated a complex finding to a non-technical audience."],
    "professional_values": [
        "Tell me about a time you faced an ethical tension or conflict of interest. What did you do?",
        "Describe a situation where you had to deliver an unwelcome message to a client or leader."],
    "leadership": [
        "Tell me about a time you led a team through a difficult moment.",
        "Describe how you gave difficult feedback and what the outcome was."],
}

RESUME_INTERVIEW_TEMPLATES = [
    "Your resume highlights {skill}. Tell me about a specific project where you applied it and the impact you had.",
    "You listed {skill}. Walk me through a challenge you faced using it and how you handled it.",
    "How have you used {skill} to drive a measurable outcome? Be specific about your role.",
    "Describe a situation where your {skill} experience made the difference. What did you do?",
]


def competency_name(key):
    return COMPETENCIES.get(key, {}).get("name", key)
