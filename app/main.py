from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import AnalysisReport, Document, KnowledgeBaseItem, LearningOutcome, UsageRecord, User
from .schemas import (
    AnalysisResponse,
    BillingSummary,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    LearningOutcomeCreate,
    Token,
)
from .security import create_access_token, decode_access_token, get_password_hash, verify_password
from .services.ai_engine import analyze_legal_text

app = FastAPI(title="LexiFirm AI Platform", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

STORAGE_DIR = Path("app/storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
ENCRYPTION_KEY_PATH = STORAGE_DIR / "fernet.key"

if ENCRYPTION_KEY_PATH.exists():
    key = ENCRYPTION_KEY_PATH.read_bytes()
else:
    key = Fernet.generate_key()
    ENCRYPTION_KEY_PATH.write_bytes(key)

cipher = Fernet(key)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_demo_users()


def seed_demo_users() -> None:
    db = next(get_db())
    try:
        seed_data = [
            ("client@firm.com", "Client User", "client", "starter"),
            ("analyst@firm.com", "Analyst User", "analyst", "pro"),
            ("partner@firm.com", "Partner User", "partner", "enterprise"),
            ("admin@firm.com", "Admin User", "admin", "enterprise"),
        ]
        for email, name, role, tier in seed_data:
            exists = db.query(User).filter(User.email == email).first()
            if not exists:
                db.add(
                    User(
                        email=email,
                        full_name=name,
                        role=role,
                        subscription_tier=tier,
                        hashed_password=get_password_hash("Password123!"),
                    )
                )
        db.commit()
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/auth/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = create_access_token(subject=user.email, role=user.role)
    return Token(access_token=access_token)


@app.post("/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(require_role("client", "analyst", "partner", "admin")),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    encrypted = cipher.encrypt(content)

    storage_path = STORAGE_DIR / f"{user.id}_{file.filename}.enc"
    storage_path.write_bytes(encrypted)

    doc = Document(
        owner_id=user.id,
        filename=file.filename,
        file_path=str(storage_path),
        content_type=file.content_type or "application/octet-stream",
    )
    db.add(doc)
    db.flush()

    db.add(UsageRecord(user_id=user.id, metric="uploads", quantity=1, cost_usd=0.02))
    db.commit()

    return {"document_id": doc.id, "status": "uploaded"}


@app.post("/documents/{document_id}/analyze", response_model=AnalysisResponse)
def analyze_document(
    document_id: int,
    user: User = Depends(require_role("client", "analyst", "partner", "admin")),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if user.role == "client" and doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    decrypted = cipher.decrypt(Path(doc.file_path).read_bytes())
    text = decrypted.decode(errors="ignore")
    result = analyze_legal_text(text)

    report = db.query(AnalysisReport).filter(AnalysisReport.document_id == doc.id).first()
    if report:
        report.risky_clauses = "\n".join(result.risky_clauses)
        report.suggestions = "\n".join(result.suggestions)
        report.summary = result.summary
        report.confidence_score = result.confidence_score
    else:
        db.add(
            AnalysisReport(
                document_id=doc.id,
                risky_clauses="\n".join(result.risky_clauses),
                suggestions="\n".join(result.suggestions),
                summary=result.summary,
                confidence_score=result.confidence_score,
            )
        )

    db.add(UsageRecord(user_id=user.id, metric="analyses", quantity=1, cost_usd=0.15))
    db.commit()

    return AnalysisResponse(
        risky_clauses=result.risky_clauses,
        suggestions=result.suggestions,
        summary=result.summary,
        confidence_score=result.confidence_score,
    )


@app.get("/documents/{document_id}/report", response_model=AnalysisResponse)
def get_report(
    document_id: int,
    user: User = Depends(require_role("client", "analyst", "partner", "admin")),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if user.role == "client" and doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    report = db.query(AnalysisReport).filter(AnalysisReport.document_id == doc.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="No analysis report available")

    return AnalysisResponse(
        risky_clauses=report.risky_clauses.split("\n"),
        suggestions=report.suggestions.split("\n"),
        summary=report.summary,
        confidence_score=report.confidence_score,
    )


@app.post("/knowledge-base/items", response_model=KnowledgeBaseOut)
def create_knowledge_item(
    payload: KnowledgeBaseCreate,
    user: User = Depends(require_role("analyst", "partner", "admin")),
    db: Session = Depends(get_db),
):
    item = KnowledgeBaseItem(
        category=payload.category,
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/knowledge-base/items", response_model=list[KnowledgeBaseOut])
def list_knowledge_items(
    user: User = Depends(require_role("analyst", "partner", "admin")),
    db: Session = Depends(get_db),
):
    _ = user
    return db.query(KnowledgeBaseItem).order_by(KnowledgeBaseItem.created_at.desc()).all()


@app.post("/learning/outcomes")
def add_learning_outcome(
    payload: LearningOutcomeCreate,
    user: User = Depends(require_role("analyst", "partner", "admin")),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    outcome = LearningOutcome(
        document_id=payload.document_id,
        outcome=payload.outcome,
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(outcome)
    db.commit()

    return {"status": "recorded", "outcome": payload.outcome}


@app.get("/dashboard/client")
def client_dashboard(user: User = Depends(require_role("client", "analyst", "partner", "admin")), db: Session = Depends(get_db)):
    doc_count = db.query(func.count(Document.id)).filter(Document.owner_id == user.id).scalar() or 0
    report_count = (
        db.query(func.count(AnalysisReport.id))
        .join(Document, Document.id == AnalysisReport.document_id)
        .filter(Document.owner_id == user.id)
        .scalar()
        or 0
    )

    return {
        "client": user.email,
        "documents_uploaded": doc_count,
        "reports_generated": report_count,
        "subscription_tier": user.subscription_tier,
    }


@app.get("/dashboard/internal")
def internal_dashboard(
    user: User = Depends(require_role("analyst", "partner", "admin")),
    db: Session = Depends(get_db),
):
    total_documents = db.query(func.count(Document.id)).scalar() or 0
    total_reports = db.query(func.count(AnalysisReport.id)).scalar() or 0
    total_kb_items = db.query(func.count(KnowledgeBaseItem.id)).scalar() or 0
    outcomes = db.query(LearningOutcome.outcome, func.count(LearningOutcome.id)).group_by(LearningOutcome.outcome).all()

    return {
        "total_documents": total_documents,
        "total_reports": total_reports,
        "knowledge_base_items": total_kb_items,
        "outcomes": [{"outcome": k, "count": v} for k, v in outcomes],
        "viewer_role": user.role,
    }


@app.get("/billing/usage", response_model=BillingSummary)
def billing_usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    usage = db.query(UsageRecord).filter(UsageRecord.user_id == user.id).all()
    total_cost = round(sum(item.cost_usd for item in usage), 2)
    total_uploads = sum(item.quantity for item in usage if item.metric == "uploads")
    total_analyses = sum(item.quantity for item in usage if item.metric == "analyses")

    return BillingSummary(
        subscription_tier=user.subscription_tier,
        total_cost_usd=total_cost,
        total_uploads=total_uploads,
        total_analyses=total_analyses,
    )


@app.post("/demo/analyze-inline", response_model=AnalysisResponse)
def demo_inline_analyze(content: str = Form(...)):
    result = analyze_legal_text(content)
    return AnalysisResponse(
        risky_clauses=result.risky_clauses,
        suggestions=result.suggestions,
        summary=result.summary,
        confidence_score=result.confidence_score,
    )
