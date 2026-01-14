"""Pydantic models for API request/response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "str_strip_whitespace": True,
    }


# Variant schemas
class VariantBase(BaseSchema):
    """Base variant schema."""

    variant_name: str = Field(..., description="Variant name (e.g., 'EGFR L858R')")
    gene_symbol: str = Field(..., description="Gene symbol (e.g., 'EGFR')")
    chromosome: Optional[str] = Field(None, description="Chromosome")
    position: Optional[int] = Field(None, description="Genomic position")
    ref_allele: Optional[str] = Field(None, description="Reference allele")
    alt_allele: Optional[str] = Field(None, description="Alternate allele")
    rsid: Optional[str] = Field(None, description="dbSNP ID")
    clinical_significance: Optional[str] = Field(None, description="Clinical significance")
    disease_associations: Optional[List[str]] = Field(None, description="Associated diseases")
    allele_frequency: Optional[float] = Field(None, ge=0, le=1, description="Allele frequency")


class VariantCreate(VariantBase):
    """Schema for creating a variant."""
    pass


class VariantResponse(VariantBase):
    """Schema for variant response."""

    variant_id: int
    created_at: datetime
    updated_at: datetime


# Druggability schemas
class DruggabilityScore(BaseSchema):
    """Druggability score schema."""

    score: float = Field(..., ge=0, le=1, description="Druggability score (0-1)")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    model_version: str = Field(..., description="Model version")
    factors: Optional[List[Dict[str, Any]]] = Field(None, description="Contributing factors")
    prediction_date: datetime


# Market analysis schemas
class MarketAnalysisResponse(BaseSchema):
    """Market analysis response schema."""

    disease: str
    patient_population: Optional[int] = Field(None, description="Total patient population")
    prevalence_rate: Optional[float] = Field(None, description="Disease prevalence rate")
    market_size_usd: Optional[int] = Field(None, description="Market size in USD")
    market_size_formatted: Optional[str] = Field(None, description="Formatted market size")
    growth_rate: Optional[float] = Field(None, description="Annual growth rate")
    geographic_distribution: Optional[Dict[str, Any]] = Field(None)
    data_source: Optional[str] = None
    analysis_date: datetime

    @field_validator("market_size_formatted", mode="before")
    @classmethod
    def format_market_size(cls, v, info) -> Optional[str]:
        """Format market size with proper suffixes."""
        if not info.data.get("market_size_usd"):
            return None

        size = info.data["market_size_usd"]
        if size >= 1_000_000_000:
            return f"${size / 1_000_000_000:.1f}B"
        elif size >= 1_000_000:
            return f"${size / 1_000_000:.1f}M"
        else:
            return f"${size:,}"


# Clinical trial schemas
class ClinicalTrialResponse(BaseSchema):
    """Clinical trial response schema."""

    trial_id: int
    nct_id: str
    title: Optional[str]
    phase: Optional[str]
    status: Optional[str]
    sponsor: Optional[str]
    condition: Optional[str]
    enrollment: Optional[int]
    start_date: Optional[datetime]
    completion_date: Optional[datetime]
    results_available: bool


class TrialStatistics(BaseSchema):
    """Trial statistics schema."""

    total: int = Field(..., description="Total number of trials")
    active: int = Field(..., description="Active trials")
    completed: int = Field(..., description="Completed trials")
    by_phase: Dict[str, int] = Field(..., description="Trials by phase")
    by_status: Dict[str, int] = Field(..., description="Trials by status")
    success_rate: Optional[float] = Field(None, description="Historical success rate")


# Drug schemas
class DrugResponse(BaseSchema):
    """Drug response schema."""

    drug_id: int
    drug_name: str
    drugbank_id: Optional[str]
    drug_type: Optional[str]
    mechanism_of_action: Optional[str]
    indication: Optional[str]
    approval_status: Optional[str]
    approval_date: Optional[datetime]
    patent_expiry: Optional[datetime]
    targets: Optional[List[str]]


# Patent schemas
class PatentResponse(BaseSchema):
    """Patent response schema."""

    patent_id: int
    patent_number: str
    title: Optional[str]
    assignee: Optional[str]
    filing_date: Optional[datetime]
    grant_date: Optional[datetime]
    expiry_date: Optional[datetime]
    status: Optional[str]
    claims_count: Optional[int]


class PatentLandscape(BaseSchema):
    """Patent landscape schema."""

    total_patents: int
    active_patents: int
    expiring_soon: List[PatentResponse]
    by_assignee: Dict[str, int]
    recent_filings: List[PatentResponse]


# Publication schemas
class PublicationResponse(BaseSchema):
    """Publication response schema."""

    pub_id: int
    pmid: str
    title: Optional[str]
    journal: Optional[str]
    publication_date: Optional[datetime]
    citation_count: Optional[int]


# Competitive intelligence schemas
class CompetitiveIntelligence(BaseSchema):
    """Competitive intelligence schema."""

    competitors: List[str] = Field(..., description="List of competing companies")
    competing_drugs: List[DrugResponse] = Field(..., description="Competing drugs")
    competing_trials: List[ClinicalTrialResponse] = Field(..., description="Competing trials")
    market_share: Optional[Dict[str, float]] = Field(None, description="Estimated market share")


# Investment intelligence schemas
class InvestmentIntelligence(BaseSchema):
    """Investment intelligence schema."""

    total_funding: Optional[int] = Field(None, description="Total funding in USD")
    recent_rounds: Optional[List[Dict[str, Any]]] = Field(None, description="Recent funding rounds")
    key_investors: Optional[List[str]] = Field(None, description="Key investors")
    ipo_potential: Optional[float] = Field(None, ge=0, le=1, description="IPO potential score")


# Comprehensive variant intelligence response
class VariantIntelligenceResponse(BaseSchema):
    """Comprehensive variant intelligence response."""

    variant: VariantResponse
    druggability: Optional[DruggabilityScore] = None
    drugs: List[DrugResponse] = Field(default_factory=list)
    clinical_trials: Optional[TrialStatistics] = None
    market: Optional[MarketAnalysisResponse] = None
    patents: Optional[PatentLandscape] = None
    competition: Optional[CompetitiveIntelligence] = None
    investment: Optional[InvestmentIntelligence] = None
    publications: List[PublicationResponse] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# Query schemas
class QueryRequest(BaseSchema):
    """Natural language query request."""

    query: str = Field(..., min_length=3, max_length=500, description="Natural language query")
    options: Optional[Dict[str, bool]] = Field(
        default_factory=lambda: {
            "include_trials": True,
            "include_patents": True,
            "include_financials": True,
            "include_publications": True,
        },
        description="Query options"
    )


class QueryResponse(BaseSchema):
    """Query response schema."""

    query: str
    results: List[VariantIntelligenceResponse]
    total_results: int
    processing_time_ms: float


# Error schemas
class ErrorDetail(BaseSchema):
    """Error detail schema."""

    code: int
    message: str
    type: str
    details: Optional[Any] = None


class ErrorResponse(BaseSchema):
    """Error response schema."""

    error: ErrorDetail
