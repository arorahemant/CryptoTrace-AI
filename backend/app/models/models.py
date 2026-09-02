"""
CryptoTrace AI - SQLAlchemy Domain Models
Complete database schema for the investigation platform.
13 domain entities with proper relationships, indexes, and constraints.
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime,
    ForeignKey, Enum, Index, JSON, UniqueConstraint, BigInteger,
    Uuid,
)
from sqlalchemy.orm import relationship
from app.core.database import Base

# Use SQLAlchemy's built-in Uuid type for cross-database compatibility
UUID = Uuid


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return uuid.uuid4()


# ─── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    INVESTIGATOR = "investigator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class CaseStatus(str, enum.Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    REVIEW = "review"
    COMPLETED = "completed"


class RiskCategory(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatternType(str, enum.Enum):
    RAPID_MOVEMENT = "rapid_movement"
    FUND_SPLITTING = "fund_splitting"
    FUND_CONSOLIDATION = "fund_consolidation"
    LAYERING = "layering"
    REPEATED_CONNECTIONS = "repeated_connections"


class AttributionConfidence(str, enum.Enum):
    KNOWN = "known"
    LIKELY = "likely"
    UNKNOWN = "unknown"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Blockchain(str, enum.Enum):
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    POLYGON = "polygon"
    BSC = "bsc"
    DEMO = "demo"


# ─── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.INVESTIGATOR)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    cases = relationship("Case", back_populates="investigator")
    audit_logs = relationship("AuditLog", back_populates="user")


# ─── Case ──────────────────────────────────────────────────────────────────────

class Case(Base):
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    reported_wallet = Column(String(255), nullable=False)
    blockchain = Column(Enum(Blockchain), nullable=False, default=Blockchain.ETHEREUM)
    status = Column(Enum(CaseStatus), nullable=False, default=CaseStatus.NEW)
    incident_date = Column(DateTime(timezone=True), nullable=True)
    reported_amount = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    investigator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_demo = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    investigator = relationship("User", back_populates="cases")
    wallets = relationship("Wallet", back_populates="case", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="case", cascade="all, delete-orphan")
    fund_flows = relationship("FundFlow", back_populates="case", cascade="all, delete-orphan")
    findings = relationship("PatternFinding", back_populates="case", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessment", back_populates="case", cascade="all, delete-orphan")
    vasp_attributions = relationship("VASPAttribution", back_populates="case", cascade="all, delete-orphan")
    investigation_events = relationship("InvestigationEvent", back_populates="case", cascade="all, delete-orphan")
    ai_conversations = relationship("AIConversation", back_populates="case", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_cases_status", "status"),
        Index("ix_cases_investigator", "investigator_id"),
    )


# ─── Wallet ────────────────────────────────────────────────────────────────────

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    address = Column(String(255), nullable=False)
    blockchain = Column(Enum(Blockchain), nullable=False)
    label = Column(String(255), nullable=True)
    is_reported = Column(Boolean, default=False)
    is_intermediary = Column(Boolean, default=False)
    is_destination = Column(Boolean, default=False)
    is_suspicious = Column(Boolean, default=False)
    hop_distance = Column(Integer, nullable=True)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    total_received = Column(Float, default=0.0)
    total_sent = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    case = relationship("Case", back_populates="wallets")
    risk_assessments = relationship("RiskAssessment", back_populates="wallet")

    __table_args__ = (
        Index("ix_wallets_case_address", "case_id", "address"),
        UniqueConstraint("case_id", "address", name="uq_wallet_case_address"),
    )


# ─── Transaction (Canonical Model) ────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    hash = Column(String(255), nullable=False)
    blockchain = Column(Enum(Blockchain), nullable=False)
    block_number = Column(BigInteger, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    from_address = Column(String(255), nullable=False)
    to_address = Column(String(255), nullable=False)
    asset = Column(String(50), nullable=False, default="ETH")
    amount = Column(Float, nullable=False)
    amount_usd = Column(Float, nullable=True)
    fee = Column(Float, nullable=True)
    status = Column(String(50), default="confirmed")
    source = Column(String(100), nullable=False, default="demo")
    is_suspicious = Column(Boolean, default=False)
    hop_number = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    case = relationship("Case", back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_case", "case_id"),
        Index("ix_transactions_from", "from_address"),
        Index("ix_transactions_to", "to_address"),
        Index("ix_transactions_timestamp", "timestamp"),
        Index("ix_transactions_hash", "hash"),
    )


# ─── Fund Flow ────────────────────────────────────────────────────────────────

class FundFlow(Base):
    __tablename__ = "fund_flows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    path_index = Column(Integer, nullable=False)
    from_address = Column(String(255), nullable=False)
    to_address = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    asset = Column(String(50), default="ETH")
    hop_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    transaction_hash = Column(String(255), nullable=False)
    is_primary_path = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    case = relationship("Case", back_populates="fund_flows")

    __table_args__ = (
        Index("ix_fund_flows_case", "case_id"),
    )


# ─── Pattern Finding ──────────────────────────────────────────────────────────

class PatternFinding(Base):
    __tablename__ = "pattern_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    pattern_type = Column(Enum(PatternType), nullable=False)
    pattern_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Enum(Severity), nullable=False, default=Severity.MEDIUM)
    confidence = Column(Float, nullable=False, default=0.5)
    trigger = Column(Text, nullable=True)
    affected_wallets = Column(JSON, nullable=True)  # list of wallet addresses
    supporting_transaction_ids = Column(JSON, nullable=True)  # list of tx hashes
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    case = relationship("Case", back_populates="findings")

    __table_args__ = (
        Index("ix_findings_case", "case_id"),
        Index("ix_findings_type", "pattern_type"),
    )


# ─── VASP Attribution ─────────────────────────────────────────────────────────

class VASPAttribution(Base):
    __tablename__ = "vasp_attributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    wallet_address = Column(String(255), nullable=False)
    entity_name = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=True)  # exchange, mixer, etc.
    attribution_type = Column(String(100), nullable=False)  # public, inferred, intelligence
    confidence = Column(Enum(AttributionConfidence), nullable=False, default=AttributionConfidence.UNKNOWN)
    source = Column(String(255), nullable=False)
    supporting_evidence = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    case = relationship("Case", back_populates="vasp_attributions")

    __table_args__ = (
        Index("ix_vasp_case", "case_id"),
        Index("ix_vasp_address", "wallet_address"),
    )


# ─── Risk Assessment ──────────────────────────────────────────────────────────

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True)
    wallet_address = Column(String(255), nullable=False)
    risk_score = Column(Float, nullable=False, default=0.0)
    risk_category = Column(Enum(RiskCategory), nullable=False, default=RiskCategory.LOW)
    contributing_signals = Column(JSON, nullable=True)  # list of signal objects
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    case = relationship("Case", back_populates="risk_assessments")
    wallet = relationship("Wallet", back_populates="risk_assessments")

    __table_args__ = (
        Index("ix_risk_case", "case_id"),
    )


# ─── Evidence ─────────────────────────────────────────────────────────────────

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("pattern_findings.id"), nullable=True)
    transaction_hash = Column(String(255), nullable=True)
    wallet_address = Column(String(255), nullable=True)
    evidence_type = Column(String(100), nullable=False)  # transaction, pattern, attribution, risk
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    source = Column(String(100), nullable=False, default="analysis")
    is_bookmarked = Column(Boolean, default=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    case = relationship("Case", back_populates="evidence")

    __table_args__ = (
        Index("ix_evidence_case", "case_id"),
        Index("ix_evidence_finding", "finding_id"),
    )


# ─── Investigation Event (Timeline) ───────────────────────────────────────────

class InvestigationEvent(Base):
    __tablename__ = "investigation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    transaction_hash = Column(String(255), nullable=True)
    from_address = Column(String(255), nullable=True)
    to_address = Column(String(255), nullable=True)
    amount = Column(Float, nullable=True)
    asset = Column(String(50), nullable=True)
    sequence_order = Column(Integer, nullable=False, default=0)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    case = relationship("Case", back_populates="investigation_events")

    __table_args__ = (
        Index("ix_events_case", "case_id"),
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_order", "case_id", "sequence_order"),
    )


# ─── AI Conversation ──────────────────────────────────────────────────────────

class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    grounding_context = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    case = relationship("Case", back_populates="ai_conversations")

    __table_args__ = (
        Index("ix_ai_conv_case", "case_id"),
    )


# ─── Report ───────────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    report_type = Column(String(50), default="investigation")
    content = Column(JSON, nullable=False)  # structured report sections
    summary = Column(Text, nullable=True)
    generated_by = Column(String(100), default="system")
    status = Column(String(50), default="draft")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    case = relationship("Case", back_populates="reports")

    __table_args__ = (
        Index("ix_reports_case", "case_id"),
    )


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_user", "user_id"),
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_action", "action"),
    )
