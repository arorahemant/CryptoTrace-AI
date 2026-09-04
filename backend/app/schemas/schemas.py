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
    ACCEPTED = "accepted"
    INVESTIGATING = "investigating"
    REVIEW = "review"
    COMPLETED = "completed"


class BlockchainSchema(str, Enum):
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    TRON = "tron"
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


class AssetActionTypeSchema(str, Enum):
    FREEZE_REQUEST = "freeze_request"
    PRESERVATION_REQUEST = "preservation_request"


class AssetActionStatusSchema(str, Enum):
    DRAFT = "draft"
    PREPARED = "prepared"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    ACTIONED = "actioned"
    DECLINED = "declined"
    MORE_INFORMATION_REQUIRED = "more_information_required"


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
    asset: Optional[str] = Field(default=None, max_length=50)
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
    asset: Optional[str] = None
    source_submission_reference: Optional[str] = None
    analysis_status: str = "analysis_not_connected"
    analysis_message: str = "Analysis provider status is unavailable."
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
    asset: Optional[str] = Field(default=None, max_length=50)
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
    asset: str
    analysis_status: str
    analysis_message: str
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


class AssetActionRequestCreate(BaseModel):
    target_wallet: str = Field(..., min_length=3, max_length=255)
    action_type: AssetActionTypeSchema
    evidence_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    finding_ids: List[UUID] = Field(default_factory=list, max_length=100)


class AssetActionStatusUpdate(BaseModel):
    status: AssetActionStatusSchema


class AssetActionReadiness(BaseModel):
    case_id: UUID
    ready: bool
    destination_wallet: Optional[str]
    asset: Optional[str]
    observed_amount: Optional[float]
    last_movement_at: Optional[datetime]
    attribution_status: str
    attribution_confidence: str
    attribution_entity: Optional[str] = None
    attribution_provenance: str = "unknown"
    attribution_source_reference: Optional[str] = None
    attribution_reasoning: Optional[str] = None
    attribution_evidence_ids: List[UUID] = Field(default_factory=list)
    attribution_transaction_hashes: List[str] = Field(default_factory=list)
    supporting_transaction_hash: Optional[str]
    supporting_finding_id: Optional[UUID]
    evidence_count: int
    evidence_ids: List[UUID] = Field(default_factory=list)
    finding_ids: List[UUID] = Field(default_factory=list)
    checks: List[dict[str, Any]]


class AssetActionRequestResponse(BaseModel):
    id: UUID
    case_id: UUID
    actor_id: UUID
    target_wallet: str
    action_type: AssetActionTypeSchema
    status: AssetActionStatusSchema
    evidence_ids: List[UUID]
    finding_ids: List[UUID]
    observed_asset: Optional[str]
    observed_amount: Optional[float]
    last_movement_at: Optional[datetime]
    attribution_status: str
    attribution_confidence: str
    attribution_entity: Optional[str] = None
    attribution_provenance: str = "unknown"
    attribution_source_reference: Optional[str] = None
    attribution_reasoning: Optional[str] = None
    supporting_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class RecommendationPrioritySchema(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationTypeSchema(str, Enum):
    REVIEW_HIGHEST_VALUE_INTERMEDIARY = "review_highest_value_intermediary"
    INSPECT_STRONGEST_FINDING = "inspect_strongest_finding"
    REVIEW_DESTINATION_ATTRIBUTION = "review_destination_attribution"
    PRESERVE_SUPPORTING_EVIDENCE = "preserve_supporting_evidence"
    PREPARE_ASSET_ACTION_REQUEST = "prepare_asset_action_request"


class InvestigatorRecommendation(BaseModel):
    recommendation_id: str
    case_id: UUID
    type: RecommendationTypeSchema
    title: str
    action: str
    factual_reason: str
    priority: RecommendationPrioritySchema
    evidence_ids: List[UUID] = Field(default_factory=list)
    transaction_hashes: List[str] = Field(default_factory=list)
    finding_ids: List[UUID] = Field(default_factory=list)
    target_wallet: Optional[str] = None
    deterministic_source: str
    created_at: datetime


class RecommendationsResponse(BaseModel):
    case_id: UUID
    recommendations: List[InvestigatorRecommendation]


# ─── Public case validation ─────────────────────────────────────────────────

class PublicCaseFact(BaseModel):
    fact_id: str
    label: str
    value: str
    source_locator: str


class PublicCaseResponse(BaseModel):
    case_id: str
    title: str
    case_label: str
    source_authority: str
    source_type: str
    source_url: str
    jurisdiction: str
    publication_date: str
    blockchain: str
    network_note: str
    asset: str
    publicly_disclosed_wallets: List[str] = Field(default_factory=list)
    wallet_disclosure_note: str
    disclosed_transaction_references: List[str] = Field(default_factory=list)
    transaction_disclosure_note: str
    provenance: str
    analysis_availability: str
    analysis_note: str
    facts: List[PublicCaseFact]
    outcome_note: str


class PublicCaseComparisonRow(BaseModel):
    element: str
    real_case: str
    cryptotrace: str
    result: str
    why: str
    evidence: List[str] = Field(default_factory=list)
    source: str


class PublicCaseCryptoTraceResult(BaseModel):
    status: str
    message: str
    is_demo: bool
    wallets: List[str] = Field(default_factory=list)
    transaction_references: List[str] = Field(default_factory=list)
    findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    attribution: Optional[dict[str, Any]] = None


class PublicCaseAlignment(BaseModel):
    label: str
    comparable_elements: int
    matched: int
    partial: int
    not_observable: int
    not_comparable: int


class PublicCaseComparisonResponse(BaseModel):
    case: PublicCaseResponse
    source: dict[str, str]
    cryptotrace: PublicCaseCryptoTraceResult
    rows: List[PublicCaseComparisonRow]
    alignment: PublicCaseAlignment
    limitations: str


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
    vasp_attribution_status: str = "unknown"
    vasp_provenance: str = "unknown"
    vasp_source_reference: Optional[str] = None
    vasp_reasoning: Optional[str] = None
    vasp_supporting_evidence_ids: List[UUID] = Field(default_factory=list)
    vasp_supporting_transaction_hashes: List[str] = Field(default_factory=list)
    vasp_verified_at: Optional[datetime] = None


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
    attribution_status: str = "unknown"
    provenance: str = "unknown"
    source_reference: Optional[str] = None
    reasoning: Optional[str] = None
    supporting_evidence_ids: List[UUID] = Field(default_factory=list)
    supporting_transaction_hashes: List[str] = Field(default_factory=list)
    verified_at: Optional[datetime] = None



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
