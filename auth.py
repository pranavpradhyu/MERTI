"""Authentication: full-page login, OTP reset, registration with resume."""
import re

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, session as flask_session)

from models import db, User, Otp, ROLES
from security import (login_user, logout_user, current_user, save_profile_picture,
                      rate_limited, record_attempt, clear_attempts, generate_otp)
from resume import save_resume, analyze_skills

auth_bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.]{3,32}$")
MOBILE_RE = re.compile(r"^[0-9+\-\s]{7,20}$")


def _password_issues(pw):
    issues = []
    if len(pw) < 8:
        issues.append("at least 8 characters")
    if not re.search(r"[A-Za-z]", pw):
        issues.append("a letter")
    if not re.search(r"[0-9]", pw):
        issues.append("a number")
    return issues


def _unique_email(username):
    base = f"{username}@{current_app.config['EMAIL_DOMAIN']}"
    if not User.query.filter_by(email=base).first():
        return base
    i = 2
    while True:
        cand = f"{username}{i}@{current_app.config['EMAIL_DOMAIN']}"
        if not User.query.filter_by(email=cand).first():
            return cand
        i += 1


@auth_bp.route("/")
def index():
    if current_user():
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        key = f"{username}|{request.remote_addr}"
        if rate_limited(key):
            flash("Too many attempts. Please wait a few minutes and try again.", "danger")
            return render_template("login.html", form={"username": username})

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            record_attempt(key)
            flash("Invalid username or password.", "danger")
            return render_template("login.html", form={"username": username})

        clear_attempts(key)
        login_user(user)
        flash(f"Welcome back, {user.first_name}.", "success")
        nxt = request.args.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        return redirect(url_for("main.dashboard"))

    return render_template("login.html", form={})


# ---------------------------------------------------------------------------
# Forgot password -> mobile + 4-digit OTP login
# ---------------------------------------------------------------------------
@auth_bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        mobile = (request.form.get("mobile") or "").strip()
        user = User.query.filter_by(mobile=mobile).first()
        # Always behave the same to avoid leaking which numbers exist.
        demo_code = None
        if user:
            code = generate_otp()
            otp = Otp.new(mobile, code, current_app.config["OTP_TTL"])
            db.session.add(otp)
            db.session.commit()
            demo_code = code  # In production this is sent by SMS, not shown.
        flask_session["otp_mobile"] = mobile
        if current_app.config["OTP_DEMO_MODE"] and demo_code:
            flash(f"Demo mode — your OTP is {demo_code} (normally sent by SMS).", "warning")
        else:
            flash("If that mobile is registered, an OTP has been sent.", "success")
        return redirect(url_for("auth.verify_otp"))
    return render_template("forgot.html")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    mobile = flask_session.get("otp_mobile")
    if not mobile:
        return redirect(url_for("auth.forgot"))

    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        new_pw = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""

        otp = (Otp.query.filter_by(mobile=mobile, code=code, used=False)
               .order_by(Otp.created_at.desc()).first())
        if not otp or not otp.is_valid:
            flash("Invalid or expired OTP. Please try again.", "danger")
            return render_template("verify_otp.html", mobile=mobile)

        user = User.query.filter_by(mobile=mobile).first()
        if not user:
            flash("Account not found.", "danger")
            return redirect(url_for("auth.forgot"))

        # Optional password reset
        if new_pw or confirm:
            issues = _password_issues(new_pw)
            if issues:
                flash("New password needs " + ", ".join(issues) + ".", "danger")
                return render_template("verify_otp.html", mobile=mobile)
            if new_pw != confirm:
                flash("Passwords do not match.", "danger")
                return render_template("verify_otp.html", mobile=mobile)
            user.set_password(new_pw)

        otp.used = True
        db.session.commit()
        flask_session.pop("otp_mobile", None)
        login_user(user)
        flash("Signed in via OTP.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("verify_otp.html", mobile=mobile)


# ---------------------------------------------------------------------------
# Registration (with optional resume upload for candidates)
# ---------------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("main.dashboard"))

    form = {}
    if request.method == "POST":
        form = {
            "first_name": (request.form.get("first_name") or "").strip(),
            "last_name": (request.form.get("last_name") or "").strip(),
            "username": (request.form.get("username") or "").strip(),
            "mobile": (request.form.get("mobile") or "").strip(),
            "role": request.form.get("role") or "",
        }
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        consent = request.form.get("consent") == "on"

        errors = []
        if not form["first_name"] or not form["last_name"]:
            errors.append("First and last name are required.")
        if not USERNAME_RE.match(form["username"]):
            errors.append("Username must be 3–32 characters (letters, numbers, _ or .).")
        if not MOBILE_RE.match(form["mobile"]):
            errors.append("Enter a valid mobile number.")
        if form["role"] not in ROLES:
            errors.append("Please choose a valid role.")
        if _password_issues(password):
            errors.append("Password needs " + ", ".join(_password_issues(password)) + ".")
        if password != confirm:
            errors.append("Passwords do not match.")
        if form["role"] == "candidate" and not consent:
            errors.append("Candidates must provide consent to be assessed.")
        if User.query.filter_by(username=form["username"]).first():
            errors.append("That username is already taken.")
        if User.query.filter_by(mobile=form["mobile"]).first():
            errors.append("That mobile number is already registered.")

        picture = None
        resume_file, resume_text = None, ""
        if not errors:
            try:
                picture = save_profile_picture(
                    request.files.get("picture"),
                    current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
                    current_app.config["UPLOAD_FOLDER"])
            except ValueError as e:
                errors.append(str(e))
        if not errors and form["role"] == "candidate":
            try:
                resume_file, resume_text = save_resume(
                    request.files.get("resume"),
                    current_app.config["ALLOWED_RESUME_EXTENSIONS"],
                    current_app.config["RESUME_FOLDER"])
            except ValueError as e:
                errors.append(str(e))

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", roles=ROLES, form=form)

        user = User(
            first_name=form["first_name"], last_name=form["last_name"],
            username=form["username"], email=_unique_email(form["username"]),
            mobile=form["mobile"], role=form["role"], picture=picture,
            consent=consent, resume_file=resume_file)
        if resume_file:
            user.resume_skills = analyze_skills(resume_text)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        if resume_file:
            flash("Account created. We analysed your resume — review the detected skills below.",
                  "success")
            return redirect(url_for("main.resume_skills"))
        flash("Your account has been created.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html", roles=ROLES, form=form)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
