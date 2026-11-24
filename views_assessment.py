"""Assessment flow: adaptive MCQ phase + AI interview phase + report."""
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, abort)

from models import db, AssessmentSession, Report, Review
from content import ASSESSMENT_TYPES, competency_name
from engine import (start_session, current_mcq, current_interview, answer_mcq,
                    record_interview_answer, abandon_session, skip_interview, check_deadline,
                    remaining_seconds, suggest_assessments)
from security import login_required, roles_required, current_user, save_recording

assess_bp = Blueprint("assess", __name__)


def _owned_or_404(sid):
    s = AssessmentSession.query.get_or_404(sid)
    if s.user_id != current_user().id:
        abort(403)
    return s


@assess_bp.route("/assessment/start/<type_key>", methods=["POST"])
@roles_required("candidate")
def start(type_key):
    if type_key not in ASSESSMENT_TYPES:
        abort(404)
    if ASSESSMENT_TYPES[type_key].get("resume") and not current_user().resume_skills:
        flash("Upload and analyse your resume first to take the personalised assessment.",
              "warning")
        return redirect(url_for("main.resume_skills"))
    s = start_session(current_user(), type_key)
    return redirect(url_for("assess.take", sid=s.id))


@assess_bp.route("/assessment/<int:sid>")
@roles_required("candidate")
def take(sid):
    s = _owned_or_404(sid)
    if check_deadline(s):
        flash("Time is up — your assessment has been submitted and scored.", "warning")
    if s.status == "completed":
        return redirect(url_for("assess.report", sid=s.id))
    if s.status == "abandoned":
        flash("This assessment session was closed.", "warning")
        return redirect(url_for("main.dashboard"))

    if s.phase == "interview":
        return redirect(url_for("assess.interview", sid=s.id))

    item = current_mcq(s)
    if item is None:
        return redirect(url_for("assess.interview", sid=s.id))
    answered = sum(1 for it in s.mcq_items if it.answer_index is not None)
    return render_template("assessment_mcq.html", session=s, item=item,
                           question=item.question, answered=answered,
                           total=current_app.config["ASSESSMENT_LENGTH"],
                           meta=ASSESSMENT_TYPES[s.type_key],
                           competency_name=competency_name,
                           per_q=current_app.config["MCQ_TIME_LIMIT"],
                           remaining=remaining_seconds(s))


@assess_bp.route("/assessment/<int:sid>/answer", methods=["POST"])
@roles_required("candidate")
def answer(sid):
    s = _owned_or_404(sid)
    if check_deadline(s):
        return redirect(url_for("assess.report", sid=s.id))
    if s.status != "in_progress" or s.phase != "mcq":
        return redirect(url_for("assess.take", sid=s.id))
    raw = request.form.get("choice")
    # Unanswered (timed out on the question) counts as a skipped/incorrect item.
    choice = int(raw) if raw not in (None, "") and raw.isdigit() and int(raw) in range(4) else -1
    answer_mcq(s, choice)
    return redirect(url_for("assess.take", sid=s.id))


@assess_bp.route("/assessment/<int:sid>/interview")
@roles_required("candidate")
def interview(sid):
    s = _owned_or_404(sid)
    if check_deadline(s):
        return redirect(url_for("assess.report", sid=s.id))
    if s.status == "completed":
        return redirect(url_for("assess.report", sid=s.id))
    if s.phase != "interview":
        return redirect(url_for("assess.take", sid=s.id))
    item = current_interview(s)
    if item is None:
        return redirect(url_for("assess.report", sid=s.id))
    idx = sum(1 for it in s.interview_items if it.answer_text is not None)
    return render_template("assessment_interview.html", session=s, item=item,
                           index=idx + 1, total=len(s.interview_items),
                           meta=ASSESSMENT_TYPES[s.type_key],
                           per_q=current_app.config["INTERVIEW_QUESTION_TIME"],
                           remaining=remaining_seconds(s),
                           support_email=current_app.config["SUPPORT_EMAIL"],
                           admin_email=current_app.config["ADMIN_EMAIL"])


@assess_bp.route("/assessment/<int:sid>/interview/answer", methods=["POST"])
@roles_required("candidate")
def interview_answer(sid):
    s = _owned_or_404(sid)
    if check_deadline(s):
        return redirect(url_for("assess.report", sid=s.id))
    if s.status != "in_progress" or s.phase != "interview":
        return redirect(url_for("assess.take", sid=s.id))
    transcript = (request.form.get("transcript") or "").strip()
    rec = None
    try:
        rec = save_recording(request.files.get("recording"),
                             current_app.config["RECORDING_FOLDER"])
    except Exception:
        rec = None
    complete = record_interview_answer(s, transcript, rec)
    if complete:
        flash("Assessment complete — here is your analysis report.", "success")
        return redirect(url_for("assess.report", sid=s.id))
    return redirect(url_for("assess.interview", sid=s.id))


@assess_bp.route("/assessment/<int:sid>/interview/skip", methods=["POST"])
@roles_required("candidate")
def interview_skip(sid):
    s = _owned_or_404(sid)
    if s.status == "in_progress":
        skip_interview(s)
        flash("AI interview skipped — here is your analysis based on your MCQ performance.",
              "warning")
    return redirect(url_for("assess.report", sid=s.id))


@assess_bp.route("/assessment/<int:sid>/abandon", methods=["POST"])
@roles_required("candidate")
def abandon(sid):
    s = _owned_or_404(sid)
    abandon_session(s)
    flash("Your session was closed. If you hit a problem, the support team is here to help.",
          "warning")
    return redirect(url_for("main.dashboard"))


@assess_bp.route("/report/<int:sid>")
@login_required
def report(sid):
    s = AssessmentSession.query.get_or_404(sid)
    viewer = current_user()
    is_owner = (s.user_id == viewer.id)
    is_staff = viewer.role in ("assessor", "mentor", "admin")
    if not (is_owner or is_staff):
        abort(403)
    if s.status != "completed" or not s.report:
        if is_owner and s.status == "in_progress":
            return redirect(url_for("assess.take", sid=s.id))
        abort(404)

    rep = s.report
    comp_detail = []
    for key, score in rep.skill_scores.items():
        items = [it for it in s.mcq_items if it.competency == key and it.answer_index is not None]
        comp_detail.append({"key": key, "name": competency_name(key), "score": score,
                            "correct": sum(1 for it in items if it.is_correct),
                            "count": len(items)})
    comp_detail.sort(key=lambda d: -d["score"])
    reviews = (Review.query.filter_by(session_id=s.id)
               .order_by(Review.created_at.desc()).all())
    suggestions = suggest_assessments(s.user) if is_owner else []
    return render_template("report.html", session=s, report=rep,
                           meta=ASSESSMENT_TYPES[s.type_key], comp_detail=comp_detail,
                           reviews=reviews, suggestions=suggestions,
                           is_owner=is_owner, is_staff=is_staff,
                           interview_items=[i for i in s.interview_items if i.ai_score is not None])
