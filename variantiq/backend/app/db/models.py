"""SQLAlchemy database models."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class Variant(Base, TimestampMixin):
    """Genetic variant from ClinVar."""

    __tablename__ = "variants"

    variant_id: Mapped[int] = mapped_column(primary_key=True)
    variant_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    gene_symbol: Mapped[str] = mapped_column(String(50), index=True)
    chromosome: Mapped[Optional[str]] = mapped_column(String(10))
    position: Mapped[Optional[int]] = mapped_column(Integer)
    ref_allele: Mapped[Optional[str]] = mapped_column(String(1000))
    alt_allele: Mapped[Optional[str]] = mapped_column(String(1000))
    rsid: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    clinical_significance: Mapped[Optional[str]] = mapped_column(String(100))
    disease_associations: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    allele_frequency: Mapped[Optional[float]] = mapped_column(Float)

    # Relationships
    druggability: Mapped[List["VariantDruggability"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan"
    )
    market_analyses: Mapped[List["MarketAnalysis"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Variant(id={self.variant_id}, name='{self.variant_name}', gene='{self.gene_symbol}')>"


class Gene(Base, TimestampMixin):
    """Gene information."""

    __tablename__ = "genes"

    gene_id: Mapped[int] = mapped_column(primary_key=True)
    gene_symbol: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    gene_name: Mapped[Optional[str]] = mapped_column(Text)
    chromosome: Mapped[Optional[str]] = mapped_column(String(10))
    gene_type: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    pathways: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    functions: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))

    def __repr__(self) -> str:
        return f"<Gene(id={self.gene_id}, symbol='{self.gene_symbol}')>"


class Drug(Base, TimestampMixin):
    """Drug information from DrugBank."""

    __tablename__ = "drugs"

    drug_id: Mapped[int] = mapped_column(primary_key=True)
    drug_name: Mapped[str] = mapped_column(String(255), index=True)
    drugbank_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    drug_type: Mapped[Optional[str]] = mapped_column(String(100))
    mechanism_of_action: Mapped[Optional[str]] = mapped_column(Text)
    indication: Mapped[Optional[str]] = mapped_column(Text)
    approval_status: Mapped[Optional[str]] = mapped_column(String(50))
    approval_date: Mapped[Optional[datetime]] = mapped_column(Date)
    patent_expiry: Mapped[Optional[datetime]] = mapped_column(Date)
    targets: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))

    def __repr__(self) -> str:
        return f"<Drug(id={self.drug_id}, name='{self.drug_name}', status='{self.approval_status}')>"


class ClinicalTrial(Base, TimestampMixin):
    """Clinical trial from ClinicalTrials.gov."""

    __tablename__ = "clinical_trials"

    trial_id: Mapped[int] = mapped_column(primary_key=True)
    nct_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text)
    phase: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    sponsor: Mapped[Optional[str]] = mapped_column(String(255))
    intervention: Mapped[Optional[str]] = mapped_column(Text)
    condition: Mapped[Optional[str]] = mapped_column(Text)
    target_gene: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    target_variant: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    enrollment: Mapped[Optional[int]] = mapped_column(Integer)
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    completion_date: Mapped[Optional[datetime]] = mapped_column(Date)
    results_available: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_outcome: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index('idx_trials_gene_variant', 'target_gene', 'target_variant'),
    )

    def __repr__(self) -> str:
        return f"<ClinicalTrial(id={self.trial_id}, nct_id='{self.nct_id}', phase='{self.phase}')>"


class VariantDruggability(Base, TimestampMixin):
    """ML-predicted druggability scores for variants."""

    __tablename__ = "variant_druggability"

    druggability_id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.variant_id", ondelete="CASCADE"),
        nullable=False
    )
    druggability_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    features: Mapped[Optional[dict]] = mapped_column(JSONB)
    prediction_date: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    variant: Mapped["Variant"] = relationship(back_populates="druggability")

    __table_args__ = (
        Index('idx_druggability_score', 'druggability_score'),
        Index('uq_variant_model', 'variant_id', 'model_version', unique=True),
    )

    def __repr__(self) -> str:
        return f"<VariantDruggability(id={self.druggability_id}, variant_id={self.variant_id}, score={self.druggability_score:.3f})>"


class MarketAnalysis(Base, TimestampMixin):
    """Market size and financial analysis for variants."""

    __tablename__ = "market_analysis"

    analysis_id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.variant_id", ondelete="CASCADE"),
        nullable=False
    )
    disease: Mapped[str] = mapped_column(String(255), nullable=False)
    patient_population: Mapped[Optional[int]] = mapped_column(Integer)
    prevalence_rate: Mapped[Optional[float]] = mapped_column(Float)
    market_size_usd: Mapped[Optional[int]] = mapped_column(BigInteger)
    growth_rate: Mapped[Optional[float]] = mapped_column(Float)
    geographic_distribution: Mapped[Optional[dict]] = mapped_column(JSONB)
    data_source: Mapped[Optional[str]] = mapped_column(String(255))
    analysis_date: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    variant: Mapped["Variant"] = relationship(back_populates="market_analyses")

    def __repr__(self) -> str:
        return f"<MarketAnalysis(id={self.analysis_id}, variant_id={self.variant_id}, disease='{self.disease}')>"


class Publication(Base, TimestampMixin):
    """Scientific publications from PubMed."""

    __tablename__ = "publications"

    pub_id: Mapped[int] = mapped_column(primary_key=True)
    pmid: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    journal: Mapped[Optional[str]] = mapped_column(String(255))
    publication_date: Mapped[Optional[datetime]] = mapped_column(Date)
    citation_count: Mapped[Optional[int]] = mapped_column(Integer)
    mentioned_variants: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    mentioned_genes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    mentioned_drugs: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))

    __table_args__ = (
        Index('idx_pubs_variants', 'mentioned_variants', postgresql_using='gin'),
        Index('idx_pubs_genes', 'mentioned_genes', postgresql_using='gin'),
    )

    def __repr__(self) -> str:
        return f"<Publication(id={self.pub_id}, pmid='{self.pmid}')>"


class Patent(Base, TimestampMixin):
    """Patent information."""

    __tablename__ = "patents"

    patent_id: Mapped[int] = mapped_column(primary_key=True)
    patent_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    assignee: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    filing_date: Mapped[Optional[datetime]] = mapped_column(Date)
    grant_date: Mapped[Optional[datetime]] = mapped_column(Date)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(Date, index=True)
    status: Mapped[Optional[str]] = mapped_column(String(50))
    related_genes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    related_variants: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    claims_count: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        Index('idx_patents_genes', 'related_genes', postgresql_using='gin'),
        Index('idx_patents_variants', 'related_variants', postgresql_using='gin'),
    )

    def __repr__(self) -> str:
        return f"<Patent(id={self.patent_id}, number='{self.patent_number}', assignee='{self.assignee}')>"


# Import all models to ensure they're registered with Base
__all__ = [
    "Variant",
    "Gene",
    "Drug",
    "ClinicalTrial",
    "VariantDruggability",
    "MarketAnalysis",
    "Publication",
    "Patent",
]
