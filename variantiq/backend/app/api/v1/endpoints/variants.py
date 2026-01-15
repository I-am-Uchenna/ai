"""Variant endpoints for searching and retrieving variant data."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import Variant
from app.models.schemas import VariantResponse

router = APIRouter()


@router.get("/", response_model=List[VariantResponse])
async def list_variants(
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    clinical_significance: Optional[str] = Query(None, description="Filter by clinical significance"),
    search: Optional[str] = Query(None, description="Search in variant name or gene"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: AsyncSession = Depends(get_db)
) -> List[VariantResponse]:
    """
    List variants with optional filtering.

    Args:
        gene: Filter by gene symbol
        clinical_significance: Filter by clinical significance
        search: Search term for variant name or gene
        skip: Pagination offset
        limit: Maximum number of results
        db: Database session

    Returns:
        List of variants
    """
    query = select(Variant)

    # Apply filters
    if gene:
        query = query.where(Variant.gene_symbol == gene.upper())

    if clinical_significance:
        query = query.where(
            Variant.clinical_significance.ilike(f"%{clinical_significance}%")
        )

    if search:
        query = query.where(
            or_(
                Variant.variant_name.ilike(f"%{search}%"),
                Variant.gene_symbol.ilike(f"%{search}%")
            )
        )

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query
    result = await db.execute(query)
    variants = result.scalars().all()

    return variants


@router.get("/{variant_id}", response_model=VariantResponse)
async def get_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db)
) -> VariantResponse:
    """
    Get variant by ID.

    Args:
        variant_id: Variant ID
        db: Database session

    Returns:
        Variant details

    Raises:
        HTTPException: If variant not found
    """
    query = select(Variant).where(Variant.variant_id == variant_id)
    result = await db.execute(query)
    variant = result.scalar_one_or_none()

    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    return variant


@router.get("/search/by-name/{variant_name}", response_model=VariantResponse)
async def get_variant_by_name(
    variant_name: str,
    db: AsyncSession = Depends(get_db)
) -> VariantResponse:
    """
    Get variant by name (e.g., "EGFR L858R").

    Args:
        variant_name: Variant name
        db: Database session

    Returns:
        Variant details

    Raises:
        HTTPException: If variant not found
    """
    query = select(Variant).where(Variant.variant_name == variant_name)
    result = await db.execute(query)
    variant = result.scalar_one_or_none()

    if not variant:
        raise HTTPException(
            status_code=404,
            detail=f"Variant '{variant_name}' not found"
        )

    return variant


@router.get("/genes/list", response_model=List[str])
async def list_genes(
    db: AsyncSession = Depends(get_db)
) -> List[str]:
    """
    Get list of all unique genes in the database.

    Args:
        db: Database session

    Returns:
        List of gene symbols
    """
    query = select(Variant.gene_symbol).distinct().order_by(Variant.gene_symbol)
    result = await db.execute(query)
    genes = result.scalars().all()

    return genes


@router.get("/stats/summary")
async def get_variant_stats(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get variant database statistics.

    Args:
        db: Database session

    Returns:
        Statistics summary
    """
    # Total variants
    total_query = select(func.count(Variant.variant_id))
    total_result = await db.execute(total_query)
    total_variants = total_result.scalar()

    # Variants by clinical significance
    sig_query = select(
        Variant.clinical_significance,
        func.count(Variant.variant_id)
    ).group_by(Variant.clinical_significance)
    sig_result = await db.execute(sig_query)
    by_significance = {row[0]: row[1] for row in sig_result.all()}

    # Unique genes
    genes_query = select(func.count(func.distinct(Variant.gene_symbol)))
    genes_result = await db.execute(genes_query)
    unique_genes = genes_result.scalar()

    return {
        "total_variants": total_variants,
        "unique_genes": unique_genes,
        "by_clinical_significance": by_significance,
    }
