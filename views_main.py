"""Dashboard, profile, resume management, attempts & analysis, admin content."""
import json
from collections import defaultdict

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, abort)

from models import (db, User, Question, AssessmentSession, Report, Review,
                    ROLES, REVIEWER_ROLES)
from content import ASSESSMENT_TYPES, COMPETENCIES, competency_name
from engine import suggest_assessments
from resume import save_resume, analyze_skills
from security import (login_required, roles_required, current_user,
                      save_profile_picture)

main_bp = Blueprint("main", __name__)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user.role == "candidate":
        reports = (Report.query.filter_by(user_id=user.id)
                   .order_by(Report.created_at.desc()).all())
        suggestions = suggest_assessments(user)
        in_progress = (AssessmentSession.query
                       .filter_by(user_id=user.id, status="in_progress")
                       .order_by(AssessmentSession.started_at.desc()).first())
        return render_template("dashboard_candidate.html",
                               assessment_types=ASSESSMENT_TYPES, reports=reports,
                               suggestions=suggestions, in_progress=in_progress,
                               latest=reports[0] if reports else None, user=user)

    candidates = User.query.filter_by(role="candidate").order_by(User.first_name).all()
    rows = []
    for c in candidates:
        latest = (Report.query.filter_by(user_id=c.id)
                  .order_by(Report.created_at.desc()).first())
        completed = AssessmentSession.query.filter_by(
            user_id=c.id, status="completed").count()
        rows.append({"candidate": c, "latest": latest, "completed": completed})
    stats = None
    if user.role == "admin":
        stats = {"users": User.query.count(), "candidates": len(candidates),
                 "questions": Question.query.count(),
                 "assessments": AssessmentSession.query.filter_by(status="completed").count()}
    return render_template("dashboard_staff.html", rows=rows, stats=stats, user=user)


# ---------------------------------------------------------------------------
# Profile (information only — history lives under Assessments & Analysis)
# ---------------------------------------------------------------------------
@main_bp.route("/profile")
@main_bp.route("/profile/<int:user_id>")
@login_required
def profile(user_id=None):
    viewer = current_user()
    target = viewer if user_id is None else User.query.get_or_404(user_id)
    if target.id != viewer.id and not (
        viewer.role in REVIEWER_ROLES and target.role == "candidate"):
        abort(403)
    return render_template("profile.html", target=target,
                           is_self=(target.id == viewer.id))


@main_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = current_user()
    if request.method == "POST":
        user.first_name = (request.form.get("first_name") or user.first_name).strip()
        user.last_name = (request.form.get("last_name") or user.last_name).strip()
        mobile = (request.form.get("mobile") or "").strip()
        if mobile and mobile != user.mobile:
            if User.query.filter(User.mobile == mobile, User.id != user.id).first():
                flash("That mobile number is already in use.", "danger")
                return render_template("edit_profile.html", user=user)
            user.mobile = mobile
        try:
            pic = save_profile_picture(request.files.get("picture"),
                                       current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
                                       current_app.config["UPLOAD_FOLDER"])
            if pic:
                user.picture = pic
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("edit_profile.html", user=user)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("main.profile"))
    return render_template("edit_profile.html", user=user)


# ---------------------------------------------------------------------------
# Resume management (candidate) — upload, analyse, review & cancel skills
# ---------------------------------------------------------------------------
@main_bp.route("/resume/skills")
@roles_required("candidate")
def resume_skills():
    user = current_user()
    return render_template("resume_skills.html", user=user,
                           suggestions=suggest_assessments(user),
                           assessment_types=ASSESSMENT_TYPES)


@main_bp.route("/resume/upload", methods=["POST"])
@roles_required("candidate")
def resume_upload():
    user = current_user()
    try:
        resume_file, text = save_resume(request.files.get("resume"),
                                        current_app.config["ALLOWED_RESUME_EXTENSIONS"],
                                        current_app.config["RESUME_FOLDER"])
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("main.resume_skills"))
    if not resume_file:
        flash("Please choose a resume file to upload.", "warning")
        return redirect(url_for("main.resume_skills"))
    user.resume_file = resume_file
    user.resume_skills = analyze_skills(text)
    db.session.commit()
    flash("Resume analysed. Review the detected skills below.", "success")
    return redirect(url_for("main.resume_skills"))


@main_bp.route("/resume/skill/remove", methods=["POST"])
@roles_required("candidate")
def resume_skill_remove():
    user = current_user()
    skill = (request.form.get("skill") or "").strip()
    skills = [s for s in user.resume_skills if s != skill]
    user.resume_skills = skills
    db.session.commit()
    flash(f"Removed “{skill}”.", "success")
    return redirect(url_for("main.resume_skills"))


@main_bp.route("/resume/skill/add", methods=["POST"])
@roles_required("candidate")
def resume_skill_add():
    user = current_user()
    skill = (request.form.get("skill") or "").strip()
    if skill:
        skills = user.resume_skills
        if skill not in skills:
            skills.append(skill)
            user.resume_skills = skills
            db.session.commit()
            flash(f"Added “{skill}”.", "success")
    return redirect(url_for("main.resume_skills"))


# ---------------------------------------------------------------------------
# Assessments & Analysis (attempts grouped by type, per-attempt reports + feedback)
# ---------------------------------------------------------------------------
def _attempts_view(candidate, viewer):
    sessions = (AssessmentSession.query.filter_by(user_id=candidate.id)
                .order_by(AssessmentSession.attempt.desc(),
                          AssessmentSession.started_at.desc()).all())
    grouped = defaultdict(list)
    for s in sessions:
        feedback = (Review.query.filter_by(session_id=s.id)
                    .order_by(Review.created_at.desc()).all())
        grouped[s.type_key].append({"session": s, "feedback": feedback})
    # order groups by assessment catalogue
    ordered = [(k, ASSESSMENT_TYPES.get(k, {"name": k}), grouped[k])
               for k in ASSESSMENT_TYPES if k in grouped]
    return render_template("assessments_analysis.html", candidate=candidate,
                           groups=ordered, viewer=viewer,
                           assessment_types=ASSESSMENT_TYPES)


@main_bp.route("/me/assessments")
@roles_required("candidate")
def my_assessments():
    user = current_user()
    return _attempts_view(user, user)


@main_bp.route("/candidate/<int:user_id>/assessments")
@roles_required("assessor", "mentor", "admin")
def candidate_assessments(user_id):
    candidate = User.query.get_or_404(user_id)
    if candidate.role != "candidate":
        abort(404)
    return _attempts_view(candidate, current_user())


# ---------------------------------------------------------------------------
# Admin content management
# ---------------------------------------------------------------------------
@main_bp.route("/admin/content")
@roles_required("admin")
def admin_content():
    questions = Question.query.order_by(Question.competency, Question.difficulty).all()
    by_comp = defaultdict(list)
    for q in questions:
        by_comp[q.competency].append(q)
    return render_template("admin_content.html", by_comp=by_comp,
                           competencies=COMPETENCIES, total=len(questions))


@main_bp.route("/admin/content/new", methods=["GET", "POST"])
@roles_required("admin")
def admin_new_question():
    if request.method == "POST":
        try:
            competency = request.form["competency"]
            skill = (request.form.get("skill") or "").strip() or "General"
            difficulty = int(request.form["difficulty"])
            text = (request.form.get("text") or "").strip()
            options = [(request.form.get(f"opt{i}") or "").strip() for i in range(4)]
            correct = int(request.form["correct"])
            explanation = (request.form.get("explanation") or "").strip()
        except (KeyError, ValueError):
            flash("Please complete all required fields correctly.", "danger")
            return redirect(url_for("main.admin_new_question"))
        if competency not in COMPETENCIES or not text or any(not o for o in options) \
                or difficulty not in range(1, 6) or correct not in range(4):
            flash("All fields, four options and a valid difficulty are required.", "danger")
            return redirect(url_for("main.admin_new_question"))
        db.session.add(Question(competency=competency, skill=skill, difficulty=difficulty,
                                text=text, options_json=json.dumps(options),
                                correct_index=correct, explanation=explanation))
        db.session.commit()
        flash("Question added to the bank.", "success")
        return redirect(url_for("main.admin_content"))
    return render_template("admin_new_question.html", competencies=COMPETENCIES)


@main_bp.route("/admin/content/<int:qid>/delete", methods=["POST"])
@roles_required("admin")
def admin_delete_question(qid):
    q = Question.query.get_or_404(qid)
    db.session.delete(q)
    db.session.commit()
    flash("Question removed.", "success")
    return redirect(url_for("main.admin_content"))
