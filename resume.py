"""Resume ingestion and AI-assisted skill analysis.

Extracts text from an uploaded resume (PDF / DOCX / TXT) and detects the
candidate's skills against a consulting-relevant taxonomy. The detected
skills drive personalised assessments and resume-based interview questions.
"""
import os

from content import SKILL_LOOKUP, SKILL_LABELS, competency_name


def extract_text(path):
    ext = path.rsplit(".", 1)[-1].lower()
    try:
        if ext == "pdf":
            import pdfplumber
            parts = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            return "\n".join(parts)
        if ext == "docx":
            import docx
            d = docx.Document(path)
            return "\n".join(p.text for p in d.paragraphs)
        # txt / fallback
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def analyze_skills(text):
    """Return a de-duplicated, ordered list of detected skill labels."""
    if not text:
        return []
    low = " " + text.lower() + " "
    found = []
    seen = set()
    for keyword, comp in SKILL_LOOKUP.items():
        kw = keyword.strip()
        # word-ish boundary match to avoid false hits
        needle = kw if kw.endswith(" ") else kw
        if _contains(low, needle):
            label = SKILL_LABELS[keyword]
            if label not in seen:
                seen.add(label)
                found.append(label)
    return found


def _contains(haystack, needle):
    if not needle:
        return False
    # pad short tokens with boundaries
    if len(needle) <= 3:
        return f" {needle} " in haystack or f" {needle}," in haystack or f" {needle}." in haystack
    return needle in haystack


def skills_to_competencies(skill_labels):
    """Map detected display labels back to competency buckets with counts."""
    # reverse label -> keyword -> competency
    label_to_comp = {}
    for keyword, comp in SKILL_LOOKUP.items():
        label_to_comp[SKILL_LABELS[keyword]] = comp
    counts = {}
    for label in skill_labels:
        comp = label_to_comp.get(label)
        if comp:
            counts[comp] = counts.get(comp, 0) + 1
    return counts


def weakest_covered_competencies(skill_labels):
    """Competencies least represented on the resume — useful to assess."""
    counts = skills_to_competencies(skill_labels)
    all_comps = list(__import__("content").COMPETENCIES.keys())
    ordered = sorted(all_comps, key=lambda c: counts.get(c, 0))
    return [(c, competency_name(c), counts.get(c, 0)) for c in ordered]


def save_resume(file_storage, allowed_ext, folder):
    """Validate and store an uploaded resume. Returns (filename, text)."""
    from werkzeug.utils import secure_filename
    import secrets
    if not file_storage or file_storage.filename == "":
        return None, ""
    name = secure_filename(file_storage.filename)
    if "." not in name:
        raise ValueError("Resume must be a PDF, DOCX or TXT file.")
    ext = name.rsplit(".", 1)[1].lower()
    if ext not in allowed_ext:
        raise ValueError("Unsupported resume type. Use PDF, DOCX or TXT.")
    os.makedirs(folder, exist_ok=True)
    unique = f"{secrets.token_hex(8)}.{ext}"
    dest = os.path.join(folder, unique)
    file_storage.save(dest)
    text = extract_text(dest)
    return unique, text
