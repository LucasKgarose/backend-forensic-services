import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from sqlalchemy.orm import Session

from app.errors import CaseNotFoundError, ReportGenerationError
from app.models.case import Case
from app.models.chain_of_custody_entry import ChainOfCustodyEntry
from app.models.evidence_hash import EvidenceHash
from app.models.forensic_report import ForensicReport
from app.models.message_record import MessageRecord
from app.models.notification_record import NotificationRecord
from app.services.legal_lock_service import LegalLockService


@dataclass
class ReportResult:
    case_id: str
    report_id: str
    evidence_hash: str


class ReportGeneratorService:
    def __init__(self, db: Session, legal_lock: LegalLockService):
        self.db = db
        self.legal_lock = legal_lock

    def generate_report(self, case_id: str, investigator_id: str) -> ReportResult:
        # Load case
        case = self.db.query(Case).filter_by(id=case_id).first()
        if case is None:
            raise CaseNotFoundError(f"Case {case_id} not found")

        # Load related data
        messages = (
            self.db.query(MessageRecord)
            .filter_by(case_id=case_id)
            .order_by(MessageRecord.timestamp)
            .all()
        )
        notifications = (
            self.db.query(NotificationRecord)
            .filter_by(case_id=case_id)
            .order_by(NotificationRecord.timestamp)
            .all()
        )
        custody_entries = (
            self.db.query(ChainOfCustodyEntry)
            .filter_by(case_id=case_id)
            .order_by(ChainOfCustodyEntry.timestamp)
            .all()
        )
        evidence_hashes = (
            self.db.query(EvidenceHash)
            .filter_by(case_id=case_id)
            .all()
        )

        report_id = str(uuid4())
        report_dir = os.path.join("reports", case_id)
        os.makedirs(report_dir, exist_ok=True)
        file_path = os.path.join(report_dir, f"{report_id}.pdf")

        try:
            self._build_pdf(
                file_path, case, investigator_id, messages,
                notifications, custody_entries, evidence_hashes,
            )
        except Exception as e:
            raise ReportGenerationError(f"PDF generation failed: {e}")

        # Read generated PDF and compute evidence hash
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

        # Apply digital signature if signing key is configured
        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.SIGNING_KEY_PATH and os.path.exists(settings.SIGNING_KEY_PATH):
                self.legal_lock.sign_report(pdf_bytes, settings.SIGNING_KEY_PATH)
        except Exception:
            pass  # Signing is optional; don't fail report generation

        # Log chain of custody entry for report generation
        self.legal_lock.log_custody_entry(
            case_id=case_id,
            investigator_id=investigator_id,
            action_type="REPORT_GENERATION",
            artifact_id=report_id,
            evidence_hash=pdf_hash,
        )

        # Persist ForensicReport record
        report = ForensicReport(
            id=report_id,
            case_id=case_id,
            file_path=file_path,
            evidence_hash=pdf_hash,
            investigator_id=investigator_id,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return ReportResult(
            case_id=case_id,
            report_id=report_id,
            evidence_hash=pdf_hash,
        )

    def get_report(self, case_id: str, report_id: str) -> bytes:
        report = (
            self.db.query(ForensicReport)
            .filter_by(case_id=case_id, id=report_id)
            .first()
        )
        if report is None:
            raise CaseNotFoundError(
                f"Report {report_id} not found for case {case_id}"
            )
        with open(report.file_path, "rb") as f:
            return f.read()

    def _build_pdf(
        self,
        file_path: str,
        case: Case,
        investigator_id: str,
        messages: list[MessageRecord],
        notifications: list[NotificationRecord],
        custody_entries: list[ChainOfCustodyEntry],
        evidence_hashes: list[EvidenceHash],
    ) -> None:
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story: list = []

        heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            spaceAfter=12,
        )

        # --- Title Page ---
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph("Forensic Investigation Report", styles["Title"]))
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(f"Case Number: {case.case_number}", styles["Heading2"]))
        story.append(Paragraph(f"Investigator: {investigator_id}", styles["Normal"]))
        story.append(
            Paragraph(
                f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                styles["Normal"],
            )
        )
        device_info = f"Device Serial: {case.device_serial or 'N/A'}, IMEI: {case.device_imei or 'N/A'}, OS: {case.os_version or 'N/A'}"
        story.append(Paragraph(device_info, styles["Normal"]))
        story.append(Spacer(1, 1 * inch))

        # --- Evidence Timeline ---
        story.append(Paragraph("Evidence Timeline", heading))
        if messages:
            table_data = [["Timestamp", "Sender", "Content", "Status"]]
            for msg in messages:
                ts = datetime.utcfromtimestamp(msg.timestamp / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                content = (msg.content[:80] + "...") if len(msg.content) > 80 else msg.content
                table_data.append([ts, msg.sender, content, msg.status])
            t = Table(table_data, repeatRows=1)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(t)
        else:
            story.append(Paragraph("No message records found.", styles["Normal"]))
        story.append(Spacer(1, 0.3 * inch))

        # --- Gap Analysis (placeholder) ---
        story.append(Paragraph("Gap Analysis", heading))
        if notifications and messages:
            notif_ts = sorted([n.timestamp for n in notifications])
            msg_ts = sorted([m.timestamp for m in messages])
            story.append(
                Paragraph(
                    f"Notification timestamps: {len(notif_ts)} entries, "
                    f"Message timestamps: {len(msg_ts)} entries.",
                    styles["Normal"],
                )
            )
            story.append(
                Paragraph(
                    "Detailed gap analysis comparing notification and message timestamps "
                    "is pending full implementation.",
                    styles["Normal"],
                )
            )
        else:
            story.append(
                Paragraph(
                    "Insufficient data for gap analysis (requires both notifications and messages).",
                    styles["Normal"],
                )
            )
        story.append(Spacer(1, 0.3 * inch))

        # --- Activity Heatmap (placeholder) ---
        story.append(Paragraph("Activity Heatmap", heading))
        if messages:
            freq: dict[str, int] = {}
            for msg in messages:
                dt = datetime.utcfromtimestamp(msg.timestamp / 1000)
                key = dt.strftime("%A")
                freq[key] = freq.get(key, 0) + 1
            summary = ", ".join(f"{day}: {count}" for day, count in freq.items())
            story.append(
                Paragraph(f"Message frequency by day: {summary}", styles["Normal"])
            )
        else:
            story.append(
                Paragraph("No messages available for heatmap.", styles["Normal"])
            )
        story.append(Spacer(1, 0.3 * inch))

        # --- Chain of Custody ---
        story.append(Paragraph("Chain of Custody", heading))
        if custody_entries:
            coc_data = [["Timestamp", "Investigator", "Action", "Artifact", "Hash"]]
            for entry in custody_entries:
                ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "N/A"
                coc_data.append([
                    ts,
                    entry.investigator_id,
                    entry.action_type,
                    entry.artifact_id[:30],
                    (entry.evidence_hash[:16] + "...") if entry.evidence_hash else "N/A",
                ])
            t = Table(coc_data, repeatRows=1)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(t)
        else:
            story.append(Paragraph("No chain of custody entries.", styles["Normal"]))
        story.append(Spacer(1, 0.3 * inch))

        # --- SHA-256 Hash Verification ---
        story.append(Paragraph("SHA-256 Hash Verification", heading))
        if evidence_hashes:
            hash_data = [["Artifact ID", "Hash Value", "Computed At"]]
            for eh in evidence_hashes:
                computed = eh.computed_at.strftime("%Y-%m-%d %H:%M:%S") if eh.computed_at else "N/A"
                hash_data.append([eh.artifact_id[:30], eh.hash_value, computed])
            t = Table(hash_data, repeatRows=1)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ]
                )
            )
            story.append(t)
        else:
            story.append(Paragraph("No evidence hashes recorded.", styles["Normal"]))

        doc.build(story)
