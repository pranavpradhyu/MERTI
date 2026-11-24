"""Database models for MERTI."""
import json
from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

ROLES = {
    "candidate": "Candidate",
    "assessor": "Assessor / Consultant",
    "mentor": "Mentor",
    "admin": "Platform Administrator",
}
REVIEWER_ROLES = {"assessor", "mentor", "admin"}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    mobile = db.Column(db.String(20), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    picture = db.Column(db.String(255))
    consent = db.Column(db.Boolean, default=False)
    # Candidate resume + AI-extracted skills
    resume_file = db.Column(db.String(255))
    resume_skills_json = db.Column(db.Text)      # list[str]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship("AssessmentSession", backref="user", lazy=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def role_label(self):
        return ROLES.get(self.role, self.role)

    @property
    def resume_skills(self):
        return json.loads(self.resume_skills_json) if self.resume_skills_json else []

    @resume_skills.setter
    def resume_skills(self, value):
        self.resume_skills_json = json.dumps(value)

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper()


class Otp(db.Model):
    """One-time passcode for mobile login / password reset."""
    __tablename__ = "otps"
    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(20), nullable=False, index=True)
    code = db.Column(db.String(4), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def new(mobile, code, ttl_seconds):
        return Otp(mobile=mobile, code=code,
                   expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds))

    @property
    def is_valid(self):
        return (not self.used) and datetime.utcnow() < self.expires_at


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    competency = db.Column(db.String(64), nullable=False, index=True)
    skill = db.Column(db.String(96), nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=False)
    correct_index = db.Column(db.Integer, nullable=False)
    explanation = db.Column(db.Text)

    @property
    def options(self):
        return json.loads(self.options_json)


class AssessmentSession(db.Model):
    __tablename__ = "assessment_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type_key = db.Column(db.String(48), nullable=False)
    attempt = db.Column(db.Integer, default=1)
    phase = db.Column(db.String(16), default="mcq")       # mcq | interview
    status = db.Column(db.String(16), default="in_progress")  # in_progress | completed | abandoned
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime)                     # overall 1hr limit
    finished_at = db.Column(db.DateTime)
    ability = db.Column(db.Float, default=0.0)
    score = db.Column(db.Float)

    items = db.relationship(
        "SessionItem", backref="session", lazy=True,
        order_by="SessionItem.order", cascade="all, delete-orphan")
    report = db.relationship("Report", backref="session", uselist=False,
                             cascade="all, delete-orphan")

    @property
    def mcq_items(self):
        return [i for i in self.items if i.kind == "mcq"]

    @property
    def interview_items(self):
        return [i for i in self.items if i.kind == "interview"]


class SessionItem(db.Model):
    __tablename__ = "session_items"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False)
    kind = db.Column(db.String(12), default="mcq")        # mcq | interview
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"))  # null for interview
    competency = db.Column(db.String(64))
    order = db.Column(db.Integer, nullable=False)
    difficulty = db.Column(db.Integer, default=3)
    prompt = db.Column(db.Text)                            # interview question text
    # MCQ answer
    answer_index = db.Column(db.Integer)
    is_correct = db.Column(db.Boolean)
    ability_after = db.Column(db.Float)
    # Interview answer
    answer_text = db.Column(db.Text)
    recording = db.Column(db.String(255))
    ai_score = db.Column(db.Float)
    ai_feedback = db.Column(db.Text)
    asked_at = db.Column(db.DateTime)

    question = db.relationship("Question")

    @property
    def answered(self):
        if self.kind == "mcq":
            return self.answer_index is not None
        return self.answer_text is not None


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    overall_score = db.Column(db.Float, nullable=False)
    mcq_score = db.Column(db.Float)
    interview_score = db.Column(db.Float)
    level = db.Column(db.String(32))
    skill_scores_json = db.Column(db.Text)
    strengths_json = db.Column(db.Text)
    weaknesses_json = db.Column(db.Text)
    recommendations_json = db.Column(db.Text)
    summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def _load(self, field):
        raw = getattr(self, field)
        return json.loads(raw) if raw else []

    @property
    def skill_scores(self):
        return self._load("skill_scores_json") or {}

    @property
    def strengths(self):
        return self._load("strengths_json")

    @property
    def weaknesses(self):
        return self._load("weaknesses_json")

    @property
    def recommendations(self):
        return self._load("recommendations_json")


class Review(db.Model):
    """Feedback / human oversight from assessor, mentor or admin (PR-09)."""
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewer_role = db.Column(db.String(20), nullable=False)
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    candidate = db.relationship("User", foreign_keys=[candidate_id])


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    starred = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])
