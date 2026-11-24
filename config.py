"""Application configuration."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Security ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me-in-production")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "merti.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Uploads ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    RECORDING_FOLDER = os.path.join(BASE_DIR, "static", "recordings")
    RESUME_FOLDER = os.path.join(BASE_DIR, "static", "resumes")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB (interview recordings)
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_RESUME_EXTENSIONS = {"pdf", "docx", "txt"}

    # --- Assessment engine ---
    ASSESSMENT_LENGTH = 10            # MCQ items per adaptive session
    START_DIFFICULTY = 3
    INTERVIEW_QUESTIONS = 4          # AI interview questions per session
    INTERVIEW_ENABLED = os.environ.get("INTERVIEW_ENABLED", "1") == "1"  # 0 = MCQ-only

    # Timing (seconds) — PR: 1hr main, 1min/MCQ, 2min/interview question
    ASSESSMENT_TIME_LIMIT = 60 * 60
    MCQ_TIME_LIMIT = 60
    INTERVIEW_TIME_LIMIT = 60 * 60
    INTERVIEW_QUESTION_TIME = 120

    # --- OTP ---
    OTP_TTL = 300                    # 5 minutes
    OTP_DEMO_MODE = os.environ.get("OTP_DEMO_MODE", "1") == "1"  # show OTP on screen

    # --- Support / escalation contacts ---
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@merti.io")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@merti.io")
    EMAIL_DOMAIN = "merti.io"
