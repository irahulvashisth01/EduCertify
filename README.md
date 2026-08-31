# 🎓 EduCertify

An online learning and certification platform (LMS) built with Flask, SQLAlchemy, and Microsoft SQL Server. Students enroll in courses, work through modules and lessons, pass quizzes, and earn PDF certificates with QR-code verification. Instructors author courses; admins moderate the platform.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Database Setup](#database-setup)
- [Environment Setup](#environment-setup)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Demo Accounts](#demo-accounts)
- [Certificate System](#certificate-system)
- [API Endpoints](#api-endpoints)
- [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)
- [Future Improvements](#future-improvements)

---

## Overview

EduCertify lets:
- **Students** discover courses, enroll, work through modules/lessons, take quizzes, track progress, and earn verifiable certificates.
- **Instructors** create and manage courses, modules, lessons, quizzes and questions, and view student analytics.
- **Admins** manage users, approve/reject courses, manage categories, and oversee certificates and platform reports.

Every certificate has a unique Certificate ID (e.g. `EDC-2026-000125`) and a QR code linking to a public, no-login-required verification page.

---

## Features

- Session-based authentication with secure (Werkzeug) password hashing
- Role-based authorization (Student / Instructor / Admin) with ownership checks
- Course discovery: search, category/level filters, sorting, pagination
- Full LMS learning interface: module/lesson sidebar, progress bar, mark-complete, prev/next navigation
- Quiz engine: timed attempts, attempt limits, server-side scoring, answers never exposed pre-submission
- Certificate eligibility engine (lessons + module quizzes + final assessment) → PDF (ReportLab) + QR code (qrcode) generation
- Public certificate verification, no login required
- Instructor course authoring workflow with admin approve/reject + rejection feedback
- Responsive, accessible UI with Bootstrap 5, custom design system, and `prefers-reduced-motion` support
- REST-style JSON API for AJAX interactions (progress updates, quiz submission, certificate verification)

---

## Technology Stack

**Frontend:** HTML5, CSS3, vanilla JavaScript, Bootstrap 5, Google Fonts, Font Awesome
**Backend:** Python 3.13+, Flask, Flask Blueprints, Jinja2, session-based auth
**Database:** Microsoft SQL Server (via SQLAlchemy + pyodbc); SQLite supported for local development without SQL Server
**Certificates:** ReportLab (PDF) + qrcode (QR codes)

---

## Architecture

The app follows a 3-layer architecture:

```
routes/    → HTTP handling only (parses requests, calls services, renders templates)
services/  → All business logic (validation, ownership checks, calculations)
database/  → SQLAlchemy models and the shared db instance
```

`app.py` stays thin — it only creates the Flask app, registers blueprints, and wires up error handlers via an application factory (`create_app()`).

---

## Project Structure

```
EduCertify/
├── app.py                  # Application factory & entry point
├── config.py                # Environment-driven configuration
├── requirements.txt
├── .env.example              # Copy to .env and fill in real values
│
├── database/
│   ├── database.py          # Shared SQLAlchemy instance + init_db()
│   ├── models.py             # All 15 ORM models
│   └── seed.py                # Demo data seeder
│
├── routes/                   # One blueprint per concern
├── services/                  # Business logic layer
├── utils/                      # Decorators, validators, security, helpers, QR generator
├── templates/                   # Jinja2 templates (base + per-role + per-feature)
├── static/                       # CSS / JS / images
├── uploads/                       # Course/lesson/certificate file storage
└── tests/                          # pytest suite
```

---

## Database Setup

### Option A — Microsoft SQL Server (recommended for production/full dev)

1. Install SQL Server and SQL Server Management Studio (SSMS).
2. Create a database named `EduCertify`.
3. Install the [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).
4. Set `DB_ENGINE=mssql` in `.env` and fill in `SQL_SERVER`, `SQL_DATABASE`, `SQL_USERNAME`, `SQL_PASSWORD`, `SQL_DRIVER`.
5. Tables are created automatically on first run via `db.create_all()` — no manual schema scripts needed.

### Option B — SQLite (quick local demo, no SQL Server required)

Set `DB_ENGINE=sqlite` in `.env`. A file `educertify_dev.db` will be created automatically in the project root. This is intended for demos/development only — the production target is SQL Server.

---

## Environment Setup

Copy the example file and edit it:

```powershell
Copy-Item .env.example .env
```

Key variables (see `.env.example` for the full list):

```
SECRET_KEY=change-this-secret
DB_ENGINE=mssql            # or "sqlite" for local demo
SQL_SERVER=localhost
SQL_DATABASE=EduCertify
SQL_USERNAME=your_username
SQL_PASSWORD=your_password
SQL_DRIVER=ODBC Driver 18 for SQL Server
BASE_URL=http://127.0.0.1:5000   # used inside certificate QR codes
```

Never commit your real `.env` file — it's already listed in `.gitignore`.

---

## Quick Start (fastest — no SQL Server required)

If you just want to run the app locally right now, use SQLite:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and change one line:
```
DB_ENGINE=sqlite
```

Then:
```powershell
python -m database.seed
python app.py
```

Open **http://127.0.0.1:5000**. No ODBC driver, no `pyodbc`, no SQL Server needed. Switch to real SQL Server later using the [Database Setup](#database-setup) section below — the rest of the app works identically either way.

---

## Installation

From the project root, in **Windows PowerShell**:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` intentionally does **not** include `pyodbc` (SQL Server driver). It's kept in a separate file, `requirements-sqlserver.txt`, because it often needs a compiler toolchain — see [Troubleshooting](#troubleshooting) below if you need it. If you're using SQLite for local development, you can skip it entirely.

To add SQL Server support later:
```powershell
pip install -r requirements-sqlserver.txt
```

---

## Running the Application

1. **Seed demo data** (creates demo accounts, categories, and sample courses):

   ```powershell
   python -m database.seed
   ```

2. **Start the server:**

   ```powershell
   python app.py
   ```

3. Open **http://127.0.0.1:5000** in your browser.

---

## Demo Accounts

> ⚠️ Development only. Change these passwords before any real deployment.

| Role       | Email                     | Password         |
|------------|---------------------------|------------------|
| Admin      | admin@example.com         | Admin@12345      |
| Instructor | instructor@example.com    | Instructor@123   |
| Student    | student@example.com       | Student@123      |

---

## Certificate System

1. A student becomes **eligible** for a certificate once they've completed all lessons in a course, passed all module quizzes, and passed the final assessment (if one exists).
2. From **My Certificates**, the student clicks **Generate Certificate**.
3. The system generates:
   - A unique certificate number (format `EDC-YYYY-NNNNNN`)
   - A landscape PDF certificate (ReportLab) with the student's name, course title, final score, issue date, and certificate ID
   - A QR code (saved alongside the PDF) that links to `/certificates/verify/<certificate_number>`
4. Anyone — no login required — can verify a certificate at `/certificates/verify` by entering the ID, or by scanning the QR code.
5. Admins can **revoke** a certificate from the Admin → Certificates page; revoked certificates show as invalid/revoked on the public verification page.

Generated files are stored in `uploads/certificates/`.

---

## API Endpoints

All JSON responses follow the shape `{"success": bool, "message": str, ...}`.

| Method | Endpoint                                   | Description                                  | Auth          |
|--------|---------------------------------------------|-----------------------------------------------|---------------|
| GET    | `/api/courses`                              | List published courses                        | Public        |
| GET    | `/api/courses/<id>`                         | Course detail                                  | Public        |
| POST   | `/api/progress/<lesson_id>`                 | Mark a lesson complete, returns new progress % | Student       |
| POST   | `/api/quizzes/<quiz_id>/start`              | Start a quiz attempt (returns questions, no answers) | Student |
| POST   | `/api/quizzes/<quiz_id>/submit`             | Submit answers, returns score/percentage/passed | Student      |
| GET    | `/api/certificates/verify/<certificate_id>` | Verify a certificate by ID                     | Public        |

---

## Running Tests

```powershell
pip install -r requirements.txt
python -m pytest tests/ -v
```

The test suite uses an in-memory SQLite database (via `TestingConfig`) and covers:
- Registration, login, logout, invalid login
- Role-based authorization (student/instructor blocked from admin; instructor blocked from admin)
- Course creation/update, ownership enforcement, duplicate-enrollment prevention
- Quiz scoring, pass/fail thresholds, attempt limits, answer confidentiality
- Certificate eligibility, generation, uniqueness, and public verification (valid + invalid IDs)

---

## Troubleshooting

| Problem | Likely Cause / Fix |
|---|---|
| `error: Microsoft Visual C++ 14.0 or greater is required` while installing `pyodbc` | This happens when pip tries to **compile** `pyodbc` from source because no prebuilt wheel matches your Python version. **Fix (recommended):** you likely don't need `pyodbc` yet — it's no longer in `requirements.txt`. Just run `pip install -r requirements.txt` (without SQL Server support) and use `DB_ENGINE=sqlite` in `.env` to get running immediately. **If you do need SQL Server:** run `pip install -r requirements-sqlserver.txt` (uses `pyodbc==5.2.0`, which ships prebuilt wheels for Python 3.13 on Windows — no compiler needed). Only if that specific version also fails to find a wheel for your exact Python build should you install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and retry. |
| `ModuleNotFoundError: No module named 'flask'` right after `pip install -r requirements.txt` | This means the `pip install` step **failed partway through** (commonly because the `pyodbc` build error above aborted the whole install, so Flask itself never got installed). Scroll up in your terminal output to find the actual error, fix that first, then re-run `pip install -r requirements.txt` and confirm it finishes with no errors before moving on. |
| `ModuleNotFoundError: pyodbc` when starting the app | Confirm `DB_ENGINE=sqlite` in `.env` if you don't have SQL Server set up — `pyodbc` is only required when `DB_ENGINE=mssql`. |
| Can't connect to SQL Server | Confirm the ODBC Driver 18 is installed and `SQL_DRIVER` in `.env` matches exactly. Try `DB_ENGINE=sqlite` to confirm the app itself works before debugging SQL Server connectivity. |
| `TemplateNotFound` error | Confirm you're running `python app.py` from the project root, not from inside a subfolder. |
| Certificate PDF/QR not generating | Ensure the `uploads/certificates/` folder is writable; it's created automatically on app startup. |
| Login redirects in a loop | Clear cookies for `127.0.0.1:5000` — a stale session cookie from a previous run can conflict with a fresh database. |
| Port 5000 already in use | Change the port in `app.py`'s `app.run(...)` call, or stop the other process using it. |

---

## Future Improvements

- Wire up real email delivery for password reset (currently a functional stub)
- Firebase-backed file storage for course thumbnails/lesson videos as an alternative to local `uploads/`
- Richer instructor analytics (charts via Chart.js)
- Course reviews/ratings submission UI (data model already supports it)
- Notification generation on key events (enrollment, quiz pass, certificate issued)
- Multi-step course creation wizard UI (currently a single form + management hub)
