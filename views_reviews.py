"""Feedback / human oversight by assessor, mentor or admin (PR-09)."""
from flask import Blueprint, request, redirect, url_for, flash, abort

from models import db, User, AssessmentSession, Review
from security import roles_required, current_user

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.route("/review/<int:sid>", methods=["POST"])
@roles_required("assessor", "mentor", "admin")
def review_session(sid):
    reviewer = current_user()
    s = AssessmentSession.query.get_or_404(sid)
    if s.status != "completed" or not s.report:
        abort(404)
    comment = (request.form.get("comment") or "").strip()
    rating_raw = request.form.get("rating")
    if not comment:
        flash("Feedback comment is required.", "danger")
        return redirect(url_for("main.candidate_assessments", user_id=s.user_id))
    rating = None
    if rating_raw and rating_raw.isdigit() and int(rating_raw) in range(1, 6):
        rating = int(rating_raw)
    db.session.add(Review(session_id=s.id, candidate_id=s.user_id,
                          reviewer_id=reviewer.id, reviewer_role=reviewer.role,
                          rating=rating, comment=comment))
    db.session.commit()
    flash("Your feedback has been recorded.", "success")
    return redirect(request.referrer or
                    url_for("main.candidate_assessments", user_id=s.user_id))
