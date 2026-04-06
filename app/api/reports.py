"""Reports router for forensic report generation and download."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.requests import GenerateReportRequest
from app.schemas.device import ReportResponse
from app.services.legal_lock_service import LegalLockService
from app.services.report_generator_service import ReportGeneratorService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("/", response_model=ReportResponse)
def generate_report(req: GenerateReportRequest, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    service = ReportGeneratorService(db, legal_lock)
    result = service.generate_report(
        case_id=req.caseId,
        investigator_id=req.investigatorId,
    )
    return ReportResponse(
        caseId=result.case_id,
        reportId=result.report_id,
        evidenceHash=result.evidence_hash,
    )


@router.get("/{case_id}/{report_id}")
def download_report(case_id: str, report_id: str, db: Session = Depends(get_db)):
    legal_lock = LegalLockService(db)
    service = ReportGeneratorService(db, legal_lock)
    pdf_bytes = service.get_report(case_id, report_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
    )
