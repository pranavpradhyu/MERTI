"""Adaptive assessment engine: MCQ adaptive phase + AI interview phase."""
import json
import math
import random
from datetime import datetime, timedelta

from flask import current_app

from models import db, Question, AssessmentSession, SessionItem, Report
from content import (ASSESSMENT_TYPES, COMPETENCIES, DEVELOPMENT_LIBRARY,
                     competency_name, INTERVIEW_COMPETENCY_PROMPTS,
                     RESUME_INTERVIEW_TEMPLATES)
from ai_assist import evaluate_interview_answer

LEARN_RATE = 1.0
THETA_MIN, THETA_MAX = -3.0, 3.0


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _theta_to_difficulty(theta):
    return int(_clamp(round(theta + 3), 1, 5))


def _prob_correct(theta, difficulty):
    return 1.0 / (1.0 + math.exp(-(theta - (difficulty - 3))))


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------
def start_session(user, type_key):
    if type_key not in ASSESSMENT_TYPES:
        raise ValueError("Unknown assessment type.")
    attempt = (AssessmentSession.query
               .filter_by(user_id=user.id, type_key=type_key).count()) + 1
    limit = current_app.config["ASSESSMENT_TIME_LIMIT"]
    s = AssessmentSession(
        user_id=user.id, type_key=type_key, attempt=attempt, phase="mcq",
        ability=0.0, deadline=datetime.utcnow() + timedelta(seconds=limit),
    )
    db.session.add(s)
    db.session.commit()
    _attach_next_mcq(s)
    return s


def _used_question_ids(session):
    return {it.question_id for it in session.items if it.question_id}


def _pick_competency(session):
    comps = ASSESSMENT_TYPES[session.type_key]["competencies"]
    counts = {c: 0 for c in comps}
    for it in session.mcq_items:
        if it.competency in counts:
            counts[it.competency] += 1
    fewest = min(counts.values())
    return random.choice([c for c, n in counts.items() if n == fewest])


def _select_question(session):
    used = _used_question_ids(session) or {-1}
    competency = _pick_competency(session)
    target = _theta_to_difficulty(session.ability)
    pool = Question.query.filter(Question.competency == competency,
                                 ~Question.id.in_(used)).all()
    if not pool:
        pool = Question.query.filter(~Question.id.in_(used)).all()
    if not pool:
        return None
    best = min(abs(q.difficulty - target) for q in pool)
    return random.choice([q for q in pool if abs(q.difficulty - target) == best])


def _attach_next_mcq(session):
    q = _select_question(session)
    if q is None:
        return None
    item = SessionItem(session_id=session.id, kind="mcq", question_id=q.id,
                       competency=q.competency, order=len(session.items) + 1,
                       difficulty=q.difficulty, prompt=q.text,
                       asked_at=datetime.utcnow())
    db.session.add(item)
    db.session.commit()
    return item


def current_mcq(session):
    for it in session.mcq_items:
        if it.answer_index is None:
            return it
    return None


def current_interview(session):
    for it in session.interview_items:
        if it.answer_text is None:
            return it
    return None


def answer_mcq(session, answer_index):
    item = current_mcq(session)
    if item is None:
        return
    q = item.question
    correct = (answer_index == q.correct_index)
    item.answer_index = answer_index
    item.is_correct = correct
    p = _prob_correct(session.ability, q.difficulty)
    session.ability = _clamp(session.ability + LEARN_RATE * ((1 if correct else 0) - p),
                             THETA_MIN, THETA_MAX)
    item.ability_after = session.ability
    db.session.commit()

    answered = sum(1 for it in session.mcq_items if it.answer_index is not None)
    if answered >= current_app.config["ASSESSMENT_LENGTH"]:
        if current_app.config["INTERVIEW_ENABLED"]:
            _begin_interview(session)
        else:
            _finalise(session)
    else:
        _attach_next_mcq(session)


def _begin_interview(session):
    """Generate AI interview questions (resume-based where available)."""
    session.phase = "interview"
    n = current_app.config["INTERVIEW_QUESTIONS"]
    prompts = _interview_prompts(session, n)
    order = len(session.items)
    for i, (text, comp) in enumerate(prompts):
        order += 1
        db.session.add(SessionItem(
            session_id=session.id, kind="interview", competency=comp,
            order=order, prompt=text))
    db.session.commit()


def _interview_prompts(session, n):
    meta = ASSESSMENT_TYPES[session.type_key]
    user = session.user
    prompts = []

    # Resume-based prompts first, if the candidate has analysed skills.
    if meta.get("resume") and user.resume_skills:
        from resume import skills_to_competencies
        label_to_comp = {}
        from content import SKILL_LOOKUP, SKILL_LABELS
        for kw, comp in SKILL_LOOKUP.items():
            label_to_comp[SKILL_LABELS[kw]] = comp
        skills = user.resume_skills[:]
        random.shuffle(skills)
        for skill in skills:
            if len(prompts) >= n:
                break
            tmpl = random.choice(RESUME_INTERVIEW_TEMPLATES)
            comp = label_to_comp.get(skill, "communication")
            prompts.append((tmpl.format(skill=skill), comp))

    # Fill the rest with competency behavioural prompts.
    comps = meta["competencies"][:]
    random.shuffle(comps)
    ci = 0
    while len(prompts) < n and comps:
        comp = comps[ci % len(comps)]
        pool = INTERVIEW_COMPETENCY_PROMPTS.get(comp, [])
        if pool:
            prompts.append((random.choice(pool), comp))
        ci += 1
        if ci > 50:
            break
    return prompts[:n]


def record_interview_answer(session, transcript, recording_filename):
    item = current_interview(session)
    if item is None:
        return False
    score, feedback = evaluate_interview_answer(item.prompt, transcript, item.competency)
    item.answer_text = transcript or "(no answer captured)"
    item.recording = recording_filename
    item.ai_score = score
    item.ai_feedback = feedback
    db.session.commit()

    if current_interview(session) is None:
        _finalise(session)
        return True
    return False


def skip_interview(session):
    """Bypass the AI interview: score from what has been answered and report."""
    if session.status != "in_progress":
        return
    for it in list(session.interview_items):
        if it.answer_text is None:
            db.session.delete(it)
    db.session.commit()
    _finalise(session)


def abandon_session(session):
    if session.status == "in_progress":
        session.status = "abandoned"
        session.finished_at = datetime.utcnow()
        db.session.commit()


def check_deadline(session):
    """Finalise automatically if the overall time limit has elapsed."""
    if (session.status == "in_progress" and session.deadline
            and datetime.utcnow() > session.deadline):
        # Score whatever has been answered so far.
        if sum(1 for it in session.items if it.answered) > 0:
            _finalise(session)
        else:
            session.status = "abandoned"
            session.finished_at = datetime.utcnow()
            db.session.commit()
        return True
    return False


def remaining_seconds(session):
    if not session.deadline:
        return None
    delta = (session.deadline - datetime.utcnow()).total_seconds()
    return max(0, int(delta))


# ---------------------------------------------------------------------------
# Scoring & report synthesis
# ---------------------------------------------------------------------------
def _mcq_competency_scores(session):
    buckets = {}
    for it in session.mcq_items:
        if it.answer_index is None:
            continue
        got, total = buckets.get(it.competency, (0.0, 0.0))
        total += it.difficulty
        if it.is_correct:
            got += it.difficulty
        buckets[it.competency] = (got, total)
    return {c: round(g / t * 100) for c, (g, t) in buckets.items() if t}


def _interview_competency_scores(session):
    buckets = {}
    for it in session.interview_items:
        if it.ai_score is None:
            continue
        vals = buckets.setdefault(it.competency, [])
        vals.append(it.ai_score)
    return {c: round(sum(v) / len(v)) for c, v in buckets.items() if v}


def _level(score):
    if score >= 80: return "Advanced"
    if score >= 65: return "Proficient"
    if score >= 45: return "Developing"
    return "Foundational"


def _finalise(session):
    session.status = "completed"
    session.finished_at = datetime.utcnow()

    mcq = _mcq_competency_scores(session)
    interview = _interview_competency_scores(session)

    # Blend per competency: 60% MCQ, 40% interview when both present.
    comps = set(mcq) | set(interview)
    skill_scores = {}
    for c in comps:
        if c in mcq and c in interview:
            skill_scores[c] = round(mcq[c] * 0.6 + interview[c] * 0.4)
        elif c in mcq:
            skill_scores[c] = mcq[c]
        else:
            skill_scores[c] = interview[c]

    overall = round(sum(skill_scores.values()) / len(skill_scores)) if skill_scores else 0
    mcq_overall = round(sum(mcq.values()) / len(mcq)) if mcq else 0
    iv_overall = round(sum(interview.values()) / len(interview)) if interview else None
    session.score = overall

    strengths = sorted([c for c, v in skill_scores.items() if v >= 70],
                       key=lambda c: -skill_scores[c])
    weaknesses = sorted([c for c, v in skill_scores.items() if v < 50],
                        key=lambda c: skill_scores[c])

    recommendations = []
    targets = weaknesses or [c for c, _ in sorted(skill_scores.items(),
                                                  key=lambda kv: kv[1])[:2]]
    for c in targets:
        recommendations.append({"area": competency_name(c), "key": c,
                                "score": skill_scores.get(c, 0),
                                "advice": DEVELOPMENT_LIBRARY.get(c, [])})

    summary = _narrative(session, overall, mcq_overall, iv_overall, strengths, weaknesses)

    db.session.add(Report(
        session_id=session.id, user_id=session.user_id, overall_score=overall,
        mcq_score=mcq_overall, interview_score=iv_overall, level=_level(overall),
        skill_scores_json=json.dumps(skill_scores),
        strengths_json=json.dumps([competency_name(c) for c in strengths]),
        weaknesses_json=json.dumps([competency_name(c) for c in weaknesses]),
        recommendations_json=json.dumps(recommendations), summary=summary))
    db.session.commit()


def _narrative(session, overall, mcq_overall, iv_overall, strengths, weaknesses):
    type_name = ASSESSMENT_TYPES[session.type_key]["name"]
    mc = sum(1 for it in session.mcq_items if it.answer_index is not None)
    cc = sum(1 for it in session.mcq_items if it.is_correct)
    iv = sum(1 for it in session.interview_items if it.ai_score is not None)
    parts = [
        f"On the {type_name} assessment (attempt {session.attempt}), "
        f"{session.user.first_name} answered {cc} of {mc} adaptive MCQs correctly "
        f"and " + (f"completed {iv} AI-interview question(s)" if iv else "skipped the AI interview")
        + f", for an overall capability score of {overall}/100 ({_level(overall)}). "
        + f"MCQ score {mcq_overall}/100"
        + (f"; AI-interview score {iv_overall}/100." if iv else " (interview not included).")]
    if strengths:
        parts.append("Strengths: " + ", ".join(competency_name(c) for c in strengths) + ".")
    if weaknesses:
        parts.append("Priority development areas: "
                     + ", ".join(competency_name(c) for c in weaknesses) + ".")
    parts.append("The MCQ phase adapted difficulty to each answer; the interview "
                 "answers were evaluated for structure, specificity and relevance.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# AI next-assessment suggestions
# ---------------------------------------------------------------------------
def suggest_assessments(user):
    latest = (Report.query.filter_by(user_id=user.id)
              .order_by(Report.created_at.desc()).first())
    suggestions = []

    if latest:
        weak = {c: s for c, s in latest.skill_scores.items() if s < 65}
        for key, meta in ASSESSMENT_TYPES.items():
            hit = [c for c in meta["competencies"] if c in weak]
            if hit:
                suggestions.append({
                    "key": key, "name": meta["name"],
                    "reason": "Targets your lower-scoring areas: "
                              + ", ".join(competency_name(c) for c in hit),
                    "priority": min(weak[c] for c in hit)})
        suggestions.sort(key=lambda s: s["priority"])

    # Always surface the resume-based assessment if a resume is present.
    if user.resume_skills and not any(s["key"] == "resume_based" for s in suggestions):
        suggestions.insert(0, {
            "key": "resume_based", "name": ASSESSMENT_TYPES["resume_based"]["name"],
            "reason": "Personalised to the skills detected on your resume.",
            "priority": -1})
    return suggestions[:3]
