# MERTI — Management Consulting Assessment & Development Platform

**Live demo: https://merti.onrender.com**

MERTI is an AI-assisted platform for assessing and developing management-consulting
capability. A candidate uploads a resume, takes
an adaptive MCQ assessment and a timed AI video interview, and receives an evidence-based
analysis report with strengths, gaps and development advice. Assessors, mentors and
administrators review results and give feedback, and all four roles can message each
other privately.

---

## Try it

Open **https://merti.onrender.com** and sign in with a demo account
(the role comes from the account — there is no role picker on the login page):

| Role | Username | Password | Mobile (for OTP) |
|------|----------|----------|------------------|
| Candidate | `candidate` | `candidate123` | 9000000001 |
| Assessor / Consultant | `assessor` | `assessor123` | 9000000002 |
| Mentor | `mentor` | `mentor123` | 9000000003 |
| Platform Administrator | `admin` | `admin123` | 9000000004 |

You can also register a new account from the login page.

**For the AI interview, use Google Chrome** and click **Allow** when asked for camera and
microphone access. Live speech-to-text uses the browser's Web Speech API, which works best
in Chrome (a typed-answer fallback is always available).

### Suggested walkthrough
1. Sign in as `candidate` → **Begin assessment** on *Core Consulting Capability*.
2. Answer the adaptive MCQs, then the AI interview (or choose **Skip interview** to be
   scored on the MCQs alone) → your **analysis report** opens automatically.
3. Open the profile-picture menu → **Assessments & Analysis** to see every attempt, its
   report, evaluator feedback, and the **Re-attempt** button.
4. Sign out, sign in as `assessor`, open the candidate's assessment and leave feedback.
5. Use **Messages** (Gmail-style) to write to any other role, with AI drafting help.
6. Sign in as `admin` → **Content** to add or remove questions.

---

## Features

**Login & access**
- Full-screen login with an animated intro: a figure climbs the letters **M-E-R-T-I** and
  the **I** lifts him into a rising sun, then the sign-in card appears (*Skip intro*
  available).
- **Forgot password → mobile number + 4-digit OTP** sign-in, with an optional password reset.
  No SMS gateway is connected, so in demo mode the OTP is shown on screen
  (`OTP_DEMO_MODE=0` hides it; connect an SMS provider for production).
- Registration: first and last name, username, mobile, password + re-type with a live match
  check, role, optional picture, and — for candidates — **resume upload**.

**Resume AI analysis**
- Uploaded resumes (PDF / DOCX / TXT) are parsed and a **skill profile** is extracted.
  Skills appear as chips the candidate can **remove** (✕) or add to.
- Re-uploading a resume re-analyses it. The skills feed a **personalised, resume-based
  assessment** whose AI interview asks about the candidate's own skills.

**Adaptive assessments**
- Each assessment is an **adaptive MCQ phase** (difficulty adjusts after every answer) plus
  an **AI interview phase**.
- **AI interview:** camera and microphone on, the question is read aloud, the spoken answer
  is recorded and transcribed live, and every answer is AI-evaluated with feedback.
- **Timers:** 1-hour overall limit, 1 minute per MCQ, 2 minutes per interview question.
  Per-question timers start when the question appears and auto-submit on timeout.
- The interview can be bypassed per attempt (**Skip interview & view my report**) or switched
  off for everyone with `INTERVIEW_ENABLED=0`.

**Analysis report**
- Overall score and level, MCQ and interview scores, per-competency skill breakdown, strong
  and weak areas, development recommendations, interview evidence with AI evaluation, and
  evaluator feedback.
- Visible to the candidate and to the assessor, mentor and administrator roles.
- Candidates get AI suggestions for the next assessments, targeting their weakest areas.

**Support**
- The interview screen always shows the Support team and Platform Administrator emails and
  an **End interview** control, for difficulties or an abrupt ending.

**Messaging (Gmail-style)**
- Inbox, sent and starred, with a contacts sidebar listing every role's email — click a
  contact to write to them. **AI assistance** can draft an email from a one-line intent or
  polish an existing draft.

**Profile & history**
- Profile-picture menu → Profile, Assessments & Analysis, Resume & Skills, Sign out.
- **Profile** shows account information. **Assessments & Analysis** lists every attempt as an
  expandable dropdown with its report and feedback from the other three roles.

**Administration**
- Administrators manage the question bank (add / remove) and see platform statistics.

---

## Tech stack

Flask 3 · Flask-SQLAlchemy · SQLite · Jinja2 · vanilla JavaScript · gunicorn ·
pdfplumber · python-docx

## Security

- Werkzeug password hashing (scrypt); session-bound **CSRF** protection on all writes,
  including the JSON AI endpoints (`X-CSRF-Token`).
- **Role-based access control** on every route, with ownership checks (candidates see only
  their own data).
- HttpOnly, SameSite cookies (Secure in production); security headers; validated uploads
  (images, resumes, recordings) with random filenames and size limits; login rate limiting.

## The "AI" engine

Resume skill extraction, adaptive item selection, interview-answer evaluation and email
drafting run as a self-contained, transparent heuristic engine, so the app needs no external
API key. The adaptive engine uses a Rasch-style ability estimate to pick each next question.
Interview evaluation scores the transcript only (structure, specificity, outcomes,
relevance); recordings are stored but never analysed. Each function is a drop-in point for a
hosted LLM.

## Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | dev value | Session signing key — set a long random value in production |
| `COOKIE_SECURE` | `0` | Set `1` behind HTTPS |
| `DATABASE_URL` | local SQLite file | Database connection string |
| `OTP_DEMO_MODE` | `1` | Show the OTP on screen instead of sending SMS |
| `INTERVIEW_ENABLED` | `1` | Set `0` for MCQ-only assessments |
| `SUPPORT_EMAIL` / `ADMIN_EMAIL` | `support@merti.io` / `admin@merti.io` | Contacts shown on the interview screen |

## Run it yourself

```bash
pip install -r requirements.txt
python app.py
```

The app starts on port 5000 (the address is printed in the terminal; set `PORT` to change
it). The database is created and seeded on first run with a 60-question bank and the four
demo accounts. Browsers only allow camera and microphone over HTTPS or on the local machine.

## Deployment (Render)

`render.yaml` and a `Procfile` are included.

1. Push the repo to GitHub.
2. On Render choose **New → Blueprint**, select the repo and click **Apply**. It installs
   `requirements.txt`, starts `gunicorn app:app`, generates `SECRET_KEY` and sets
   `COOKIE_SECURE=1`.
3. Every `git push` to `main` redeploys automatically.

Render's free plan has an ephemeral filesystem, so the SQLite database and uploaded files
reset on restart. For persistence, attach a disk or point `DATABASE_URL` at Postgres.

## Project structure

```
merti/
├── app.py                 # App factory, CSRF guard, headers, error handlers
├── config.py              # Configuration (env-driven)
├── models.py              # SQLAlchemy models and roles
├── security.py            # Auth state, RBAC, CSRF, uploads, rate limiting, OTP
├── content.py             # Competencies, assessment catalogue, skill taxonomy, prompts
├── engine.py              # Adaptive engine, scoring, reports, suggestions
├── ai_assist.py           # Interview-answer evaluation, email drafting/polish
├── resume.py              # Resume text extraction and skill detection
├── seed.py                # Question bank (60 items) and demo users
├── auth.py                # Login, OTP, registration
├── views_main.py          # Dashboard, profile, resume, assessments & analysis, admin
├── views_assessment.py    # MCQ phase, AI interview, report
├── views_reviews.py       # Evaluator feedback
├── views_messaging.py     # Gmail-style messaging and AI assist
├── templates/             # Jinja2 templates
├── static/css/style.css   # Stylesheet
└── requirements.txt · Procfile · render.yaml
```

## Maps to the PRD

PR-01 journey · PR-02 profile and consent · PR-03 configurable competency assessments ·
PR-04 response and evidence formats (MCQ, video interview) · PR-05 transparent AI evaluation ·
PR-06 strengths, gaps and evidence summaries · PR-08 communication via the interview ·
PR-09 assessor review and feedback · PR-10 development recommendations · PR-11 admin content
management · PR-12 access control and data protection. PR-07 (case-style work samples) is
covered only through scenario-style MCQs and the behavioural interview.
