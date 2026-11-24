"""Gmail-style private messaging with AI writing assistance."""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, jsonify)

from models import db, User, Message, ROLES
from security import login_required, current_user
from ai_assist import draft_email, polish_email

mail_bp = Blueprint("mail", __name__)


def _contacts(user):
    """All other users grouped by role, for the email sidebar."""
    users = (User.query.filter(User.id != user.id)
             .order_by(User.role, User.first_name).all())
    grouped = {k: [] for k in ROLES}
    for u in users:
        grouped.setdefault(u.role, []).append(u)
    return grouped


@mail_bp.route("/messages")
@login_required
def inbox():
    user = current_user()
    box = request.args.get("box", "inbox")
    if box == "sent":
        msgs = (Message.query.filter_by(sender_id=user.id)
                .order_by(Message.created_at.desc()).all())
    elif box == "starred":
        msgs = (Message.query.filter_by(recipient_id=user.id, starred=True)
                .order_by(Message.created_at.desc()).all())
    else:
        box = "inbox"
        msgs = (Message.query.filter_by(recipient_id=user.id)
                .order_by(Message.created_at.desc()).all())
    return render_template("messages.html", msgs=msgs, box=box,
                           contacts=_contacts(user), active=None)


@mail_bp.route("/messages/new", methods=["GET", "POST"])
@login_required
def compose():
    user = current_user()
    contacts = _contacts(user)

    if request.method == "POST":
        try:
            to_id = int(request.form["recipient_id"])
        except (KeyError, ValueError):
            flash("Choose a recipient from the contacts list.", "danger")
            return redirect(url_for("mail.inbox"))
        recipient = User.query.get(to_id)
        subject = (request.form.get("subject") or "").strip()
        body = (request.form.get("body") or "").strip()
        if recipient is None or recipient.id == user.id:
            flash("Invalid recipient.", "danger")
        elif not subject or not body:
            flash("Subject and message are both required.", "danger")
        else:
            db.session.add(Message(sender_id=user.id, recipient_id=recipient.id,
                                   subject=subject[:160], body=body))
            db.session.commit()
            flash(f"Message sent to {recipient.full_name}.", "success")
            return redirect(url_for("mail.inbox", box="sent"))

    to = request.args.get("to", type=int)
    recipient = User.query.get(to) if to else None
    if recipient and recipient.id == user.id:
        recipient = None
    return render_template("compose.html", contacts=contacts, recipient=recipient,
                           form=request.form if request.method == "POST" else {})


@mail_bp.route("/messages/<int:mid>")
@login_required
def view_message(mid):
    user = current_user()
    msg = Message.query.get_or_404(mid)
    if user.id not in (msg.sender_id, msg.recipient_id):
        abort(403)
    if msg.recipient_id == user.id and not msg.is_read:
        msg.is_read = True
        db.session.commit()
    return render_template("message.html", msg=msg, contacts=_contacts(user))


@mail_bp.route("/messages/<int:mid>/reply", methods=["POST"])
@login_required
def reply(mid):
    user = current_user()
    original = Message.query.get_or_404(mid)
    if user.id not in (original.sender_id, original.recipient_id):
        abort(403)
    other_id = (original.sender_id if original.recipient_id == user.id
                else original.recipient_id)
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Reply cannot be empty.", "danger")
        return redirect(url_for("mail.view_message", mid=mid))
    subject = original.subject if original.subject.lower().startswith("re:") \
        else "Re: " + original.subject
    db.session.add(Message(sender_id=user.id, recipient_id=other_id,
                           subject=subject[:160], body=body))
    db.session.commit()
    flash("Reply sent.", "success")
    return redirect(url_for("mail.inbox", box="sent"))


@mail_bp.route("/messages/<int:mid>/star", methods=["POST"])
@login_required
def star(mid):
    user = current_user()
    msg = Message.query.get_or_404(mid)
    if msg.recipient_id != user.id:
        abort(403)
    msg.starred = not msg.starred
    db.session.commit()
    return redirect(request.referrer or url_for("mail.inbox"))


# --- AI writing assistance (JSON) ---
@mail_bp.route("/messages/ai-draft", methods=["POST"])
@login_required
def ai_draft():
    data = request.get_json(silent=True) or {}
    body = draft_email(data.get("intent", ""), data.get("to_name", ""),
                       current_user().full_name)
    return jsonify({"body": body})


@mail_bp.route("/messages/ai-polish", methods=["POST"])
@login_required
def ai_polish():
    data = request.get_json(silent=True) or {}
    return jsonify({"body": polish_email(data.get("body", ""))})
