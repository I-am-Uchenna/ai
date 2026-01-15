"""Intelligence endpoints for comprehensive variant analysis."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import (
    ClinicalTrial,
    Drug,
    Publication,
    Variant,
    VariantDruggability,
    MarketAnalysis,
)
from app.models.schemas import (
    ClinicalTrialResponse,
    DruggabilityScore,
    DrugResponse,
    MarketAnalysisResponse,
    PublicationResponse,
    TrialStatistics,
    VariantIntelligenceResponse,
    VariantResponse,
)

router = APIRouter()


@router.get("/{variant_id}", response_model=VariantIntelligenceResponse)
async def get_variant_intelligence(
    variant_id: int,
    include_trials: bool = True,
    include_drugs: bool = True,
    include_publications: bool = True,
    db: AsyncSession = Depends(get_db)
) -> VariantIntelligenceResponse:
    """
    Get comprehensive commercial intelligence for a variant.

    This is the core endpoint that combines data from multiple sources:
    - Variant details
    - Druggability prediction
    - Related drugs
    - Clinical trials
    - Market analysis
    - Publications

    Args:
        variant_id: Variant ID
        include_trials: Include clinical trials data
        include_drugs: Include drug data
        include_publications: Include publications data
        db: Database session

    Returns:
        Comprehensive variant intelligence

    Raises:
        HTTPException: If variant not found
    """
    # Get variant
    variant_query = select(Variant).where(Variant.variant_id == variant_id)
    variant_result = await db.execute(variant_query)
    variant = variant_result.scalar_one_or_none()

    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    # Get druggability score
    druggability = await _get_druggability(db, variant_id)

    # Get related drugs
    drugs = []
    if include_drugs:
        drugs = await _get_related_drugs(db, variant.gene_symbol, variant.variant_name)

    # Get clinical trials
    trial_stats = None
    if include_trials:
        trial_stats = await _get_trial_statistics(db, variant.gene_symbol, variant.variant_name)

    # Get market analysis
    market = await _get_market_analysis(db, variant_id)

    # Get publications
    publications = []
    if include_publications:
        publications = await _get_related_publications(
            db,
            variant.gene_symbol,
            variant.variant_name
        )

    return VariantIntelligenceResponse(
        variant=VariantResponse.model_validate(variant),
        druggability=druggability,
        drugs=drugs,
        clinical_trials=trial_stats,
        market=market,
        publications=publications,
        generated_at=datetime.utcnow()
    )


async def _get_druggability(
    db: AsyncSession,
    variant_id: int
) -> Optional[DruggabilityScore]:
    """Get druggability score for variant."""
    query = (
        select(VariantDruggability)
        .where(VariantDruggability.variant_id == variant_id)
        .order_by(VariantDruggability.prediction_date.desc())
        .limit(1)
    )

    result = await db.execute(query)
    druggability = result.scalar_one_or_none()

    if not druggability:
        return None

    return DruggabilityScore(
        score=druggability.druggability_score,
        confidence=druggability.confidence_score or 0.0,
        model_version=druggability.model_version,
        factors=druggability.features.get("factors") if druggability.features else None,
        prediction_date=druggability.prediction_date
    )


async def _get_related_drugs(
    db: AsyncSession,
    gene_symbol: str,
    variant_name: str
) -> list[DrugResponse]:
    """Get drugs targeting the gene/variant."""
    # Search for drugs that target this gene
    query = select(Drug).where(
        Drug.targets.contains([gene_symbol])
    ).limit(10)

    result = await db.execute(query)
    drugs = result.scalars().all()

    return [DrugResponse.model_validate(drug) for drug in drugs]


async def _get_trial_statistics(
    db: AsyncSession,
    gene_symbol: str,
    variant_name: str
) -> Optional[TrialStatistics]:
    """Get clinical trial statistics."""
    # Count trials mentioning this gene
    base_query = select(ClinicalTrial).where(
        (ClinicalTrial.target_gene == gene_symbol) |
        (ClinicalTrial.condition.ilike(f"%{gene_symbol}%")) |
        (ClinicalTrial.intervention.ilike(f"%{gene_symbol}%"))
    )

    # Total trials
    total_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = total_result.scalar() or 0

    # Active trials
    active_result = await db.execute(
        select(func.count()).select_from(
            base_query.where(
                ClinicalTrial.status.in_([
                    "Recruiting",
                    "Active, not recruiting",
                    "Enrolling by invitation"
                ])
            ).subquery()
        )
    )
    active = active_result.scalar() or 0

    # Completed trials
    completed_result = await db.execute(
        select(func.count()).select_from(
            base_query.where(ClinicalTrial.status == "Completed").subquery()
        )
    )
    completed = completed_result.scalar() or 0

    # By phase
    phase_result = await db.execute(
        select(ClinicalTrial.phase, func.count())
        .where(
            (ClinicalTrial.target_gene == gene_symbol) |
            (ClinicalTrial.condition.ilike(f"%{gene_symbol}%"))
        )
        .group_by(ClinicalTrial.phase)
    )
    by_phase = {row[0] or "Unknown": row[1] for row in phase_result.all()}

    # By status
    status_result = await db.execute(
        select(ClinicalTrial.status, func.count())
        .where(
            (ClinicalTrial.target_gene == gene_symbol) |
            (ClinicalTrial.condition.ilike(f"%{gene_symbol}%"))
        )
        .group_by(ClinicalTrial.status)
    )
    by_status = {row[0] or "Unknown": row[1] for row in status_result.all()}

    return TrialStatistics(
        total=total,
        active=active,
        completed=completed,
        by_phase=by_phase,
        by_status=by_status,
        success_rate=None  # TODO: Calculate from historical data
    )


async def _get_market_analysis(
    db: AsyncSession,
    variant_id: int
) -> Optional[MarketAnalysisResponse]:
    """Get market analysis for variant."""
    query = (
        select(MarketAnalysis)
        .where(MarketAnalysis.variant_id == variant_id)
        .order_by(MarketAnalysis.analysis_date.desc())
        .limit(1)
    )

    result = await db.execute(query)
    analysis = result.scalar_one_or_none()

    if not analysis:
        return None

    return MarketAnalysisResponse.model_validate(analysis)


async def _get_related_publications(
    db: AsyncSession,
    gene_symbol: str,
    variant_name: str
) -> list[PublicationResponse]:
    """Get publications mentioning gene/variant."""
    # Search for publications mentioning this gene
    query = (
        select(Publication)
        .where(Publication.mentioned_genes.contains([gene_symbol]))
        .order_by(Publication.publication_date.desc())
        .limit(10)
    )

    result = await db.execute(query)
    publications = result.scalars().all()

    return [PublicationResponse.model_validate(pub) for pub in publications]


@router.get("/gene/{gene_symbol}/summary")
async def get_gene_intelligence_summary(
    gene_symbol: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get intelligence summary for all variants in a gene.

    Args:
        gene_symbol: Gene symbol
        db: Database session

    Returns:
        Gene-level intelligence summary
    """
    gene_upper = gene_symbol.upper()

    # Count variants
    variant_count_result = await db.execute(
        select(func.count(Variant.variant_id))
        .where(Variant.gene_symbol == gene_upper)
    )
    variant_count = variant_count_result.scalar() or 0

    # Count drugs targeting this gene
    drug_count_result = await db.execute(
        select(func.count(Drug.drug_id))
        .where(Drug.targets.contains([gene_upper]))
    )
    drug_count = drug_count_result.scalar() or 0

    # Count trials
    trial_count_result = await db.execute(
        select(func.count(ClinicalTrial.trial_id))
        .where(
            (ClinicalTrial.target_gene == gene_upper) |
            (ClinicalTrial.condition.ilike(f"%{gene_upper}%"))
        )
    )
    trial_count = trial_count_result.scalar() or 0

    # Count publications
    pub_count_result = await db.execute(
        select(func.count(Publication.pub_id))
        .where(Publication.mentioned_genes.contains([gene_upper]))
    )
    pub_count = pub_count_result.scalar() or 0

    return {
        "gene_symbol": gene_upper,
        "variant_count": variant_count,
        "drug_count": drug_count,
        "trial_count": trial_count,
        "publication_count": pub_count,
    }
