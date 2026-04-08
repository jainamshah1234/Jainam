# LexiFirm AI Platform (Secure Legal Intelligence)

A secure, web-based AI platform tailored for law firms. This project includes:

- Client document uploads and AI-generated reports
- Risky-clause detection and improvement suggestions
- Plain-English legal summaries
- Internal knowledge base (cases, templates, partner notes)
- Learning feedback loop (win/loss/negotiation outcomes)
- Client and internal dashboards
- RBAC, privacy controls, and encrypted-at-rest document storage
- Subscription tiers and usage-based billing tracking

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Security:** JWT auth, passlib bcrypt password hashing, role-based access control
- **Storage:** Local encrypted file storage (Fernet)
- **AI Engine:** Rule-based baseline with extension points for LLM providers
- **UI:** Premium minimal enterprise HTML/CSS/JS dashboard

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: `http://127.0.0.1:8000`

## Default Demo Users

On startup the app seeds demo users:

- `client@firm.com` / `Password123!` (role: `client`)
- `analyst@firm.com` / `Password123!` (role: `analyst`)
- `partner@firm.com` / `Password123!` (role: `partner`)
- `admin@firm.com` / `Password123!` (role: `admin`)

## API Highlights

- `POST /auth/token` → login (JWT)
- `POST /documents/upload` → upload legal docs
- `POST /documents/{id}/analyze` → AI analysis
- `GET /documents/{id}/report` → analysis report
- `POST /knowledge-base/items` → add case/template/note entry
- `POST /learning/outcomes` → tag outcome and feedback
- `GET /dashboard/client` → client metrics
- `GET /dashboard/internal` → internal analytics
- `GET /billing/usage` → usage + subscription overview

## Security Model

- **RBAC:** endpoints guarded by role checks
- **Privacy:** users can only access own docs unless analyst/partner/admin
- **Encryption:** uploaded documents encrypted at rest
- **Auditability:** analysis + outcomes linked to user and document IDs

## Production Hardening (Recommended)

- Move to PostgreSQL + row-level security
- Add object storage (S3/GCS) with KMS encryption
- Add SSO/SAML and MFA
- Integrate DLP and legal hold policies
- Use managed billing gateway (Stripe) and metered events
- Replace baseline analyzer with retrieval-augmented legal LLM pipeline
