"""ClinVar data pipeline for fetching and loading genetic variant data."""

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Variant, Gene
from app.services.base_pipeline import BasePipeline
from app.utils.http_client import HTTPClient
from app.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class ClinVarPipeline(BasePipeline):
    """
    Pipeline for fetching variant data from NCBI ClinVar.

    Uses NCBI E-utilities API to fetch variant information including:
    - Variant names and identifiers
    - Gene associations
    - Clinical significance
    - Disease associations
    - Allele frequencies

    API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25501/
    """

    EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self):
        """Initialize ClinVar pipeline."""
        super().__init__("ClinVar")

        # Set up rate limiter (3 requests/sec without API key, 10 with key)
        rate_limit = (
            settings.NCBI_RATE_LIMIT
            if settings.NCBI_API_KEY
            else 3
        )

        self.rate_limiter = RateLimiter(
            calls_per_second=rate_limit,
            name="NCBI_EUtils"
        )

        # HTTP client
        self.client: Optional[HTTPClient] = None

        # Common parameters for NCBI API
        self.common_params = {
            "tool": settings.NCBI_TOOL,
            "email": settings.NCBI_EMAIL or "variantiq@example.com",
        }

        if settings.NCBI_API_KEY:
            self.common_params["api_key"] = settings.NCBI_API_KEY

    async def extract(
        self,
        full_refresh: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract variant data from ClinVar.

        Args:
            full_refresh: If True, fetch all data; if False, fetch recent updates
            limit: Maximum number of variants to fetch

        Returns:
            List of raw variant records
        """
        self.client = HTTPClient(
            rate_limiter=self.rate_limiter,
            name="ClinVar",
            timeout=60
        )

        async with self.client:
            # Step 1: Search for variant IDs
            variant_ids = await self._search_variants(
                full_refresh=full_refresh,
                limit=limit
            )

            if not variant_ids:
                self.logger.warning("No variant IDs found")
                return []

            self.logger.info(f"Found {len(variant_ids)} variant IDs")

            # Step 2: Fetch detailed variant data
            variants = await self._fetch_variant_details(variant_ids)

            return variants

    async def _search_variants(
        self,
        full_refresh: bool = False,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Search for ClinVar variant IDs.

        Args:
            full_refresh: Get all variants or just recent updates
            limit: Maximum number of IDs to return

        Returns:
            List of ClinVar variation IDs
        """
        # Build search query
        # Focus on pathogenic/likely pathogenic variants with clinical significance
        query_parts = [
            "clinvar[filter]",
            "(pathogenic[filter] OR likely pathogenic[filter])",
        ]

        # For incremental updates, only get recent submissions
        if not full_refresh:
            checkpoint = self.load_checkpoint()
            if checkpoint and "last_update" in checkpoint:
                last_update = datetime.fromisoformat(checkpoint["last_update"])
                # Get variants updated in last 30 days
                mindate = (datetime.utcnow() - timedelta(days=30)).strftime("%Y/%m/%d")
                query_parts.append(f"{mindate}[pdat]")
            else:
                # First run: get variants from last 90 days
                mindate = (datetime.utcnow() - timedelta(days=90)).strftime("%Y/%m/%d")
                query_parts.append(f"{mindate}[pdat]")

        query = " AND ".join(query_parts)

        # Parameters for search
        params = {
            **self.common_params,
            "db": "clinvar",
            "term": query,
            "retmax": str(limit if limit else 10000),  # Max 10k per request
            "retmode": "json",
            "sort": "relevance",
        }

        self.logger.info(f"Searching ClinVar with query: {query}")

        # Execute search
        url = f"{self.EUTILS_BASE_URL}/esearch.fcgi"
        response = await self.client.get(url, params=params)

        # Parse response
        result = response.get("esearchresult", {})
        variant_ids = result.get("idlist", [])

        self.logger.info(f"Search returned {len(variant_ids)} variant IDs")

        return variant_ids

    async def _fetch_variant_details(
        self,
        variant_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch detailed information for variant IDs.

        Args:
            variant_ids: List of ClinVar variation IDs

        Returns:
            List of variant detail dictionaries
        """
        variants = []

        # Fetch in batches (NCBI allows up to 500 IDs per request)
        batch_size = 200

        for i in range(0, len(variant_ids), batch_size):
            batch_ids = variant_ids[i:i + batch_size]

            self.logger.info(
                f"Fetching batch {i // batch_size + 1}/"
                f"{(len(variant_ids) + batch_size - 1) // batch_size}"
            )

            params = {
                **self.common_params,
                "db": "clinvar",
                "id": ",".join(batch_ids),
                "rettype": "vcv",  # Variation records
                "retmode": "xml",
            }

            url = f"{self.EUTILS_BASE_URL}/efetch.fcgi"
            response = await self.client.get(url, params=params)

            # Parse XML response
            batch_variants = self._parse_clinvar_xml(response)
            variants.extend(batch_variants)

        return variants

    def _parse_clinvar_xml(self, xml_data: str) -> List[Dict[str, Any]]:
        """
        Parse ClinVar XML response.

        Args:
            xml_data: XML response string

        Returns:
            List of parsed variant dictionaries
        """
        variants = []

        try:
            root = ET.fromstring(xml_data)

            for vcv in root.findall(".//VariationArchive"):
                try:
                    variant = self._parse_variant_record(vcv)
                    if variant:
                        variants.append(variant)
                except Exception as e:
                    self.logger.warning(f"Failed to parse variant record: {e}")
                    self.stats["errors"] += 1

        except ET.ParseError as e:
            self.logger.error(f"XML parsing error: {e}")
            self.stats["errors"] += 1

        return variants

    def _parse_variant_record(self, vcv_element: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse individual variant record from XML.

        Args:
            vcv_element: VariationArchive XML element

        Returns:
            Parsed variant dictionary or None
        """
        # Get variant name
        variant_name_elem = vcv_element.find(".//VariationName/ElementValue[@Type='Preferred']")
        if variant_name_elem is None:
            return None

        variant_name = variant_name_elem.text

        # Get gene symbol
        gene_elem = vcv_element.find(".//Gene[@GeneSymbol]")
        gene_symbol = gene_elem.get("GeneSymbol") if gene_elem is not None else None

        if not gene_symbol:
            return None

        # Get genomic location
        sequence_location = vcv_element.find(".//SequenceLocation[@Assembly='GRCh38']")
        chromosome = None
        position = None
        ref_allele = None
        alt_allele = None

        if sequence_location is not None:
            chromosome = sequence_location.get("Chr")
            position_str = sequence_location.get("positionVCF")
            if position_str:
                try:
                    position = int(position_str)
                except ValueError:
                    pass
            ref_allele = sequence_location.get("referenceAlleleVCF")
            alt_allele = sequence_location.get("alternateAlleleVCF")

        # Get rsID
        rsid = None
        for xref in vcv_element.findall(".//XRef"):
            if xref.get("DB") == "dbSNP":
                rsid = f"rs{xref.get('ID')}"
                break

        # Get clinical significance
        clin_sig_elem = vcv_element.find(".//ClinicalSignificance/Description")
        clinical_significance = clin_sig_elem.text if clin_sig_elem is not None else None

        # Get disease associations
        diseases = []
        for trait in vcv_element.findall(".//Trait[@Type='Disease']"):
            name_elem = trait.find(".//Name/ElementValue[@Type='Preferred']")
            if name_elem is not None and name_elem.text:
                diseases.append(name_elem.text)

        # Get allele frequency (if available)
        allele_frequency = None
        freq_elem = vcv_element.find(".//AlleleFrequency")
        if freq_elem is not None:
            freq_value = freq_elem.get("FrequencyValue")
            if freq_value:
                try:
                    allele_frequency = float(freq_value)
                except ValueError:
                    pass

        return {
            "variant_name": variant_name,
            "gene_symbol": gene_symbol,
            "chromosome": chromosome,
            "position": position,
            "ref_allele": ref_allele,
            "alt_allele": alt_allele,
            "rsid": rsid,
            "clinical_significance": clinical_significance,
            "disease_associations": diseases if diseases else None,
            "allele_frequency": allele_frequency,
        }

    async def transform(
        self,
        raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Transform raw ClinVar data.

        Args:
            raw_data: Raw variant records

        Returns:
            Transformed variant records
        """
        transformed = []

        for record in raw_data:
            # Clean and normalize data
            transformed_record = {
                "variant_name": record["variant_name"].strip(),
                "gene_symbol": record["gene_symbol"].upper().strip(),
                "chromosome": record.get("chromosome"),
                "position": record.get("position"),
                "ref_allele": record.get("ref_allele"),
                "alt_allele": record.get("alt_allele"),
                "rsid": record.get("rsid"),
                "clinical_significance": record.get("clinical_significance"),
                "disease_associations": record.get("disease_associations"),
                "allele_frequency": record.get("allele_frequency"),
            }

            transformed.append(transformed_record)

        return transformed

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate variant record.

        Args:
            record: Variant record

        Returns:
            True if valid, False otherwise
        """
        # Must have variant name and gene symbol
        if not record.get("variant_name") or not record.get("gene_symbol"):
            return False

        # Variant name should not be too long
        if len(record["variant_name"]) > 255:
            return False

        return True

    async def load(
        self,
        db: AsyncSession,
        data: List[Dict[str, Any]]
    ) -> None:
        """
        Load variants into database.

        Args:
            db: Database session
            data: Validated variant records
        """
        # First, ensure all genes exist
        await self._ensure_genes_exist(db, data)

        # Then upsert variants
        for record in data:
            try:
                # Upsert variant
                stmt = insert(Variant).values(**record)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["variant_name"],
                    set_={
                        "gene_symbol": stmt.excluded.gene_symbol,
                        "chromosome": stmt.excluded.chromosome,
                        "position": stmt.excluded.position,
                        "ref_allele": stmt.excluded.ref_allele,
                        "alt_allele": stmt.excluded.alt_allele,
                        "rsid": stmt.excluded.rsid,
                        "clinical_significance": stmt.excluded.clinical_significance,
                        "disease_associations": stmt.excluded.disease_associations,
                        "allele_frequency": stmt.excluded.allele_frequency,
                        "updated_at": datetime.utcnow(),
                    }
                )

                result = await db.execute(stmt)

                if result.rowcount == 1:
                    self.stats["inserted"] += 1
                else:
                    self.stats["updated"] += 1

            except Exception as e:
                self.logger.warning(f"Failed to load variant {record['variant_name']}: {e}")
                self.stats["errors"] += 1

        # Commit all changes
        await db.commit()

        # Save checkpoint
        self.save_checkpoint({
            "last_update": datetime.utcnow().isoformat(),
            "total_variants": self.stats["inserted"] + self.stats["updated"],
        })

    async def _ensure_genes_exist(
        self,
        db: AsyncSession,
        data: List[Dict[str, Any]]
    ) -> None:
        """
        Ensure all gene symbols exist in database.

        Args:
            db: Database session
            data: Variant records containing gene symbols
        """
        # Get unique gene symbols
        gene_symbols = set(record["gene_symbol"] for record in data)

        for gene_symbol in gene_symbols:
            try:
                # Check if gene exists
                stmt = select(Gene).where(Gene.gene_symbol == gene_symbol)
                result = await db.execute(stmt)
                gene = result.scalar_one_or_none()

                if not gene:
                    # Insert new gene
                    gene = Gene(gene_symbol=gene_symbol)
                    db.add(gene)

            except Exception as e:
                self.logger.warning(f"Error ensuring gene {gene_symbol} exists: {e}")

        # Commit genes
        await db.commit()
