"""Natural language query endpoint."""

import re
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import Variant
from app.models.schemas import QueryRequest, QueryResponse, VariantIntelligenceResponse
from app.api.v1.endpoints.intelligence import get_variant_intelligence

router = APIRouter()


@router.post("/", response_model=QueryResponse)
async def query_variants(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    """
    Natural language query interface for variant intelligence.

    Parses natural language queries and returns relevant variant intelligence.

    Examples:
    - "EGFR L858R druggability"
    - "What drugs target BRAF V600E?"
    - "Clinical trials for KRAS G12C"
    - "Market size for ALK fusion"

    Args:
        request: Query request with natural language query
        db: Database session

    Returns:
        Query results with variant intelligence

    Raises:
        HTTPException: If query cannot be parsed
    """
    start_time = time.time()

    # Parse query to extract gene, variant, intent
    parsed = _parse_query(request.query)

    if not parsed["gene"] and not parsed["variant_name"]:
        raise HTTPException(
            status_code=400,
            detail="Could not extract gene or variant from query. "
                   "Please include a gene symbol (e.g., EGFR) or variant name (e.g., EGFR L858R)"
        )

    # Search for matching variants
    variants = await _search_variants(
        db,
        gene=parsed["gene"],
        variant_name=parsed["variant_name"]
    )

    if not variants:
        raise HTTPException(
            status_code=404,
            detail=f"No variants found matching query: {request.query}"
        )

    # Get intelligence for each variant
    results = []
    for variant in variants[:5]:  # Limit to top 5 results
        intelligence = await get_variant_intelligence(
            variant_id=variant.variant_id,
            include_trials=request.options.get("include_trials", True),
            include_drugs=request.options.get("include_drugs", True),
            include_publications=request.options.get("include_publications", True),
            db=db
        )
        results.append(intelligence)

    processing_time_ms = (time.time() - start_time) * 1000

    return QueryResponse(
        query=request.query,
        results=results,
        total_results=len(results),
        processing_time_ms=processing_time_ms
    )


def _parse_query(query: str) -> dict:
    """
    Parse natural language query to extract structured information.

    Args:
        query: Natural language query

    Returns:
        Parsed query components
    """
    query_upper = query.upper()

    # Common gene symbols to look for
    gene_symbols = [
        "EGFR", "TP53", "KRAS", "BRAF", "PIK3CA",
        "BRCA1", "BRCA2", "ALK", "MET", "ROS1",
        "HER2", "ERBB2", "RET", "NTRK", "FGFR",
        "AKT1", "PTEN", "NRAS", "KIT", "PDGFRA",
    ]

    # Extract gene
    gene = None
    for gene_symbol in gene_symbols:
        if re.search(rf"\b{gene_symbol}\b", query_upper):
            gene = gene_symbol
            break

    # Extract variant (e.g., "L858R", "V600E", "G12C")
    variant_pattern = r"\b([A-Z]\d+[A-Z])\b"
    variant_match = re.search(variant_pattern, query_upper)

    variant_name = None
    if gene and variant_match:
        mutation = variant_match.group(1)
        variant_name = f"{gene} {mutation}"

    # Extract intent (what the user is looking for)
    intent = "general"
    if any(word in query.lower() for word in ["drug", "therapy", "treatment", "medication"]):
        intent = "drugs"
    elif any(word in query.lower() for word in ["trial", "clinical", "study"]):
        intent = "trials"
    elif any(word in query.lower() for word in ["market", "size", "patient", "prevalence"]):
        intent = "market"
    elif any(word in query.lower() for word in ["druggable", "druggability", "targetable"]):
        intent = "druggability"

    return {
        "gene": gene,
        "variant_name": variant_name,
        "intent": intent,
    }


async def _search_variants(
    db: AsyncSession,
    gene: str = None,
    variant_name: str = None
) -> List[Variant]:
    """
    Search for variants matching criteria.

    Args:
        db: Database session
        gene: Gene symbol
        variant_name: Variant name

    Returns:
        List of matching variants
    """
    query = select(Variant)

    if variant_name:
        # Exact match on variant name
        query = query.where(Variant.variant_name == variant_name)
    elif gene:
        # All variants in gene
        query = query.where(Variant.gene_symbol == gene)

    # Order by clinical significance (prioritize pathogenic)
    query = query.order_by(
        Variant.clinical_significance.desc().nullslast()
    ).limit(10)

    result = await db.execute(query)
    variants = result.scalars().all()

    return list(variants)


@router.get("/suggestions")
async def get_query_suggestions(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get sample queries and available genes for query assistance.

    Args:
        db: Database session

    Returns:
        Query suggestions and available data
    """
    # Get available genes
    gene_query = select(Variant.gene_symbol).distinct().limit(20)
    gene_result = await db.execute(gene_query)
    available_genes = gene_result.scalars().all()

    # Sample queries
    sample_queries = [
        "EGFR L858R druggability and market size",
        "What drugs target BRAF V600E?",
        "Clinical trials for KRAS G12C mutation",
        "Show me all BRCA1 pathogenic variants",
        "ALK fusion therapies and clinical data",
        "HER2 amplification treatment options",
    ]

    return {
        "sample_queries": sample_queries,
        "available_genes": available_genes,
        "query_tips": [
            "Include gene symbol (e.g., EGFR, BRAF, KRAS)",
            "Optionally add mutation (e.g., L858R, V600E, G12C)",
            "Specify what you're looking for: drugs, trials, market data, druggability",
        ]
    }
