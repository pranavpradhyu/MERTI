# MERTI — Management Consulting Assessment & Development Platform

An AI-assisted platform for assessing and developing enterprise management
consulting capability, built to the MODUS / MERTI Hackathon PRD (v1.0).

Complete candidate journey: resume analysis → adaptive MCQ + AI video interview
→ evidence-led analysis report → development guidance — with human oversight
(feedback) from assessors, mentors and administrators, a Gmail-style private
messaging channel with AI writing assistance, and administrator content
management.

---

## Quick start (local)

```bash
pip install -r requirements.txt
python app.py
# open http://localhost:5000
```

SQLite is created and seeded on first run (60-question bank + 4 demo accounts).

> **Use Google Chrome on `localhost`.** The AI interview needs camera + mic,
> and live speech-to-text uses the Web Speech API (best in Chrome). Browsers
> only allow camera/mic on `localhost` or over HTTPS.

### Demo accounts

| Role | Username | Password | Mobile (for OTP) |
|------|----------|----------|------------------|
| Candidate | `candidate` | `candidate123` | 9000000001 |
| Assessor / Consultant | `assessor` | `assessor123` | 9000000002 |
| Mentor | `mentor` | `mentor123` | 9000000003 |
| Platform Administrator | `admin` | `admin123` | 9000000004 |

---

## Features (this version)

**Login & access**
- Full-screen login with an animated intro (a figure walks up the **MERTI**
  letters; at the **I** the sun rises, then the sign-in card appears — *Skip
  intro* is available). No role selection on login — the role comes from the account.
- **Forgot password → mobile + 4-digit OTP** login (and optional password reset).
  *No SMS gateway is wired, so in demo mode the OTP is shown on screen; set
  `OTP_DEMO_MODE=0` and integrate an SMS provider for production.*
- Registration: first/last name, username, mobile, password + **re-type with
  live match check**, role, optional picture, and — for candidates — **resume upload**.

**Resume AI analysis**
- On upload, the AI parses the resume (PDF / DOCX / TXT), extracts a **skill
  profile**, and shows it as chips you can **remove** (or add to) — the ✕ cancel option.
- Re-upload anytime from **Resume & Skills**; the profile re-analyses.
- Skills drive a **personalised (resume-based) assessment** whose AI interview
  asks questions about *your* skills.

**Assessments (AI-assisted & adaptive)**
- Every assessment = an **adaptive MCQ phase** (difficulty adapts to each
  answer) **+ an AI interview phase**.
- **AI interview**: camera + mic on, the AI asks a question (read aloud), your
  spoken answer is **recorded** and **transcribed** live, and each answer is
  **AI-evaluated** (structure, specificity, relevance) with feedback.
- **Timers**: 1-hour overall limit; **1 min per MCQ**; **2 min per interview
  question** — the per-question timer starts when the question is presented, and
  auto-submits on timeout.
- The **analysis report** (MCQ score, interview score, per-skill breakdown,
  strengths, weaknesses, development recommendations, interview evidence +
  AI evaluation) is viewable by all four roles (candidate owner + staff).

**Support / escalation**
- The interview screen always shows **Support team** and **Platform
  Administrator** email contacts, plus an **End interview** control, in case the
  interview is difficult or ends abruptly.

**Messaging (Gmail-style)**
- Gmail-like inbox / sent / starred with a contacts sidebar listing **every
  role's email** — pick a recipient by clicking a contact (no dropdown).
- **AI writing assistance**: *Draft with AI* (turns a one-line intent into a
  full email) and *Polish my draft*.

**Profile & history**
- Top-right **profile-picture menu** → Profile, Assessments & Analysis, Resume
  & Skills, Sign out (the separate Profile/Sign-out links are gone).
- **Profile** shows account information only.
- **Assessments & Analysis** lists every assessment, each attempt as an
  expandable dropdown with its analysis report and **feedback from the other
  three roles**; candidates can **re-attempt** any assessment.

**Administration**
- Administrators manage the **question bank** (add / remove) and see platform stats.

---

## Security
- Werkzeug password hashing; session-bound **CSRF** on all writes (incl. JSON
  AI endpoints via `X-CSRF-Token`); **role-based access control**; hardened
  cookies; security headers; validated uploads (images, resumes, recordings);
  login rate limiting; candidates see only their own data.

> The CSP allows inline scripts to keep the interactive pages (timers, camera,
> animation) self-contained. For a stricter CSP, move inline `<script>` blocks
> to external files under `static/js/` and drop `'unsafe-inline'`.

## The "AI" engine
Resume skill extraction, adaptive item selection, interview answer evaluation
and email drafting run as a **self-contained, transparent heuristic engine** —
no external API key required, so it runs anywhere. Each interface
(`evaluate_interview_answer`, `draft_email`, …) is a drop-in point if you later
want to call a hosted LLM.

---

## Deploy to Render
`render.yaml` + `Procfile` are included — **New → Blueprint** on Render builds
and starts `gunicorn app:app`, generates `SECRET_KEY`, and sets `COOKIE_SECURE=1`.
Render serves HTTPS, so camera/mic/OTP work there. SQLite on the free tier is
ephemeral — attach a disk or point `DATABASE_URL` at Postgres for persistence,
and configure an SMS provider + `OTP_DEMO_MODE=0` for real OTP delivery.

## Maps to the PRD
PR-01 journey · PR-02 profile/consent · PR-03 configurable competency
assessments · PR-04 response & evidence formats (MCQ, written, video) · PR-05
transparent AI evaluation · PR-06 strengths/gaps/evidence summaries · PR-07
case-style items · PR-08 communication via written + video interview · PR-09
assessor review & feedback · PR-10 development recommendations · PR-11 admin
content management · PR-12 access control & data protection.
