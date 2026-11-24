"""MERTI — Management Consulting Assessment & Development Platform."""
import os

from flask import Flask, render_template, request

from config import Config
from models import db, Message, ROLES
from security import current_user, get_csrf_token, verify_csrf


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    for folder in ("UPLOAD_FOLDER", "RECORDING_FOLDER", "RESUME_FOLDER"):
        os.makedirs(app.config[folder], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

    db.init_app(app)

    from auth import auth_bp
    from views_main import main_bp
    from views_assessment import assess_bp
    from views_reviews import reviews_bp
    from views_messaging import mail_bp
    for bp in (auth_bp, main_bp, assess_bp, reviews_bp, mail_bp):
        app.register_blueprint(bp)

    @app.before_request
    def _csrf_guard():
        if request.endpoint == "static":
            return
        verify_csrf()

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'")
        return resp

    @app.context_processor
    def _inject():
        user = current_user()
        unread = 0
        if user:
            unread = Message.query.filter_by(recipient_id=user.id, is_read=False).count()
        return {"current_user": user, "csrf_token": get_csrf_token(),
                "unread_count": unread, "roles": ROLES,
                "support_email": app.config["SUPPORT_EMAIL"],
                "admin_email": app.config["ADMIN_EMAIL"]}

    @app.errorhandler(403)
    def _forbidden(e):
        return render_template("error.html", code=403,
                               message="You do not have access to that page."), 403

    @app.errorhandler(404)
    def _notfound(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(400)
    def _badreq(e):
        return render_template("error.html", code=400,
                               message=getattr(e, "description", "Bad request.")), 400

    with app.app_context():
        db.create_all()
        from seed import seed_all
        seed_all()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
