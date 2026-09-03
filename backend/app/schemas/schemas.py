"""
CryptoTrace AI - Pydantic Schemas
Request/response validation for all API endpoints.
"""
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ─── Enums ─────────────────────────────────────────────────────────────────────

class UserRoleSchema(str, Enum):
    INVESTIGATOR = "investigator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    REPORTER = "reporter"


class CaseStatusSchema(str, Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    REVIEW = "review"
    COMPLETED = "completed"


class BlockchainSchema(str, Enum):
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    POLYGON = "polygon"
    BSC = "bsc"
    DEMO = "demo"


class RiskCategorySchema(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SeveritySchema(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRoleSchema = UserRoleSchema.INVESTIGATOR


class ReporterRegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)


# ─── User ──────────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    full_name: str
    role: UserRoleSchema
    is_active: bool
    created_at: datetime

    # ORM compatibility is configured on the model via ConfigDict.


# ─── Case ──────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    reported_wallet: str = Field(..., min_length=10, max_length=255)
    blockchain: BlockchainSchema = BlockchainSchema.ETHEREUM
    incident_date: Optional[datetime] = None
    reported_amount: Optional[float] = None
    notes: Optional[str] = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    title: str
    description: Optional[str]
    reported_wallet: str
    blockchain: BlockchainSchema
    status: CaseStatusSchema
    incident_date: Optional[datetime]
    reported_amount: Optional[float]
    notes: Optional[str]
    investigator_id: UUID
    is_demo: bool
    created_at: datetime
    updated_at: datetime



class CaseListResponse(BaseModel):
    cases: List[CaseResponse]
    total: int


class ReporterSubmissionCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    reported_wallet: str = Field(..., min_length=10, max_length=255)
    blockchain: BlockchainSchema = BlockchainSchema.ETHEREUM
    description: Optional[str] = Field(default=None, max_length=2000)


class ReporterVisibleInvestigator(BaseModel):
    display_name: str
    role_title: str


class ReporterSubmissionResponse(BaseModel):
    id: UUID
    reference_number: str
    title: str
    reported_wallet: str
    blockchain: BlockchainSchema
    status: str
    status_label: str
    submitted_at: datetime
    last_status_update: datetime
    next_step: str
    assigned_investigator: Optional[ReporterVisibleInvestigator] = None


class InvestigatorPublicProfileUpdate(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=255)
    role_title: str = Field(..., min_length=2, max_length=255)
    is_reporter_visible: bool = False


class InvestigatorPublicProfileResponse(BaseModel):
    display_name: str
    role_title: str
    is_reporter_visible: bool
    updated_at: datetime


# ─── Wallet ────────────────────────────────────────────────────────────────────

class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    address: str
    blockchain: BlockchainSchema
    label: Optional[str]
    is_reported: bool
    is_intermediary: bool
    is_destination: bool
    is_suspicious: bool
    hop_distance: Optional[int]
    total_received: float
    total_sent: float
    transaction_count: int
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]



# ─── Transaction (Canonical) ──────────────────────────────────────────────────

class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hash: str
    blockchain: BlockchainSchema
    block_number: Optional[int]
    timestamp: datetime
    from_address: str
    to_address: str
    asset: str
    amount: float
    amount_usd: Optional[float]
    status: str
    source: str
    is_suspicious: bool
    hop_number: Optional[int]



class EvidenceCreate(BaseModel):
    """Evidence captured by an investigator from an observed case artifact."""
    evidence_type: str = Field(default="transaction", min_length=3, max_length=100)
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=3)
    reason: Optional[str] = None
    transaction_hash: Optional[str] = Field(default=None, max_length=255)
    wallet_address: Optional[str] = Field(default=None, max_length=255)
    finding_id: Optional[UUID] = None
    source: str = Field(default="investigator", min_length=2, max_length=100)
    metadata: Optional[dict[str, Any]] = None


# ─── Investigation ────────────────────────────────────────────────────────────

class InvestigateRequest(BaseModel):
    max_hops: int = Field(default=5, ge=1, le=10)
    min_amount: float = Field(default=0.001, ge=0)
    time_window_hours: int = Field(default=720, ge=1, le=8760)
    direction: str = Field(default="outgoing", pattern="^(outgoing|incoming|both)$")


class InvestigationSummary(BaseModel):
    case_id: UUID
    status: str
    total_wallets: int
    total_transactions: int
    total_findings: int
    risk_level: RiskCategorySchema
    max_hops_traced: int
    total_amount_traced: float
    is_demo: bool


# ─── Graph ─────────────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    address: str
    label: Optional[str] = None
    is_reported: bool = False
    is_intermediary: bool = False
    is_destination: bool = False
    is_suspicious: bool = False
    hop_distance: int = 0
    total_received: float = 0
    total_sent: float = 0
    risk_category: Optional[RiskCategorySchema] = None
    risk_score: Optional[float] = None
    risk_signals: List[dict[str, Any]] = Field(default_factory=list)
    vasp_name: Optional[str] = None
    vasp_attribution_type: Optional[str] = None
    vasp_confidence: Optional[str] = None
    vasp_source: Optional[str] = None
    vasp_supporting_evidence: Optional[str] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    hash: str
    amount: float
    asset: str = "ETH"
    timestamp: datetime
    is_suspicious: bool = False
    hop_number: int = 0


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    primary_path: List[str] = Field(default_factory=list)  # ordered list of addresses in main trail


# ─── Fund Flow ─────────────────────────────────────────────────────────────────

class FundFlowStep(BaseModel):
    hop: int
    from_address: str
    to_address: str
    amount: float
    asset: str
    timestamp: datetime
    transaction_hash: str
    is_primary: bool = False


class FundFlowResponse(BaseModel):
    case_id: UUID
    paths: List[List[FundFlowStep]]
    total_amount_origin: float
    total_amount_destination: float
    max_hops: int


# ─── Pattern Finding ──────────────────────────────────────────────────────────

class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pattern_type: str
    pattern_name: str
    description: str
    severity: SeveritySchema
    confidence: float
    trigger: Optional[str]
    affected_wallets: Optional[List[str]]
    supporting_transaction_ids: Optional[List[str]]
    created_at: datetime



# ─── Evidence ─────────────────────────────────────────────────────────────────

class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_type: str
    title: str
    description: str
    reason: Optional[str]
    transaction_hash: Optional[str]
    wallet_address: Optional[str]
    source: str
    is_bookmarked: bool
    created_at: datetime



class BookmarkEvidenceRequest(BaseModel):
    evidence_id: UUID
    bookmarked: bool = True


# ─── Risk ──────────────────────────────────────────────────────────────────────

class RiskSignal(BaseModel):
    signal_name: str
    description: str
    weight: float
    score_contribution: float


class RiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wallet_address: str
    risk_score: float
    risk_category: RiskCategorySchema
    contributing_signals: List[RiskSignal]
    explanation: str



# ─── WHY? ─────────────────────────────────────────────────────────────────────

class WhyExplanation(BaseModel):
    wallet_address: str
    reasons: List[str]
    findings: List[FindingResponse]
    evidence: List[EvidenceResponse]
    risk: Optional[RiskResponse]


# ─── VASP Attribution ─────────────────────────────────────────────────────────

class VASPResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wallet_address: str
    entity_name: str
    entity_type: Optional[str]
    attribution_type: str
    confidence: str
    source: str
    supporting_evidence: Optional[str]



# ─── Timeline ─────────────────────────────────────────────────────────────────

class TimelineEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    title: str
    description: Optional[str]
    timestamp: datetime
    transaction_hash: Optional[str]
    from_address: Optional[str]
    to_address: Optional[str]
    amount: Optional[float]
    asset: Optional[str]
    sequence_order: int



class TimelineResponse(BaseModel):
    events: List[TimelineEvent]
    total_events: int


# ─── Replay ───────────────────────────────────────────────────────────────────

class ReplayEvent(BaseModel):
    event_id: UUID
    step: int
    event_type: str
    title: str
    description: str
    timestamp: datetime
    from_address: Optional[str]
    to_address: Optional[str]
    amount: Optional[float]
    asset: Optional[str]
    transaction_hash: Optional[str]
    highlight_nodes: List[str] = Field(default_factory=list)
    highlight_edges: List[str] = Field(default_factory=list)
    cumulative_amount: float = 0


class ReplayResponse(BaseModel):
    case_id: UUID
    total_steps: int
    events: List[ReplayEvent]


# ─── AI Copilot ───────────────────────────────────────────────────────────────

class AIQueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)


class AIQueryResponse(BaseModel):
    answer: str
    grounded: bool = True
    sources: List[str] = []
    suggested_questions: List[str] = []


# ─── Report ───────────────────────────────────────────────────────────────────

class ReportSection(BaseModel):
    title: str
    section_type: str  # fact, analysis, inference, ai_summary
    content: str
    metadata: Optional[dict] = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    title: str
    sections: List[ReportSection]
    summary: Optional[str]
    generated_by: str
    status: str
    created_at: datetime



# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    demo_mode: bool


# ─── Error ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


# Update forward references
LoginResponse.model_rebuild()
