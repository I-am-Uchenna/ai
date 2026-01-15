"""PubMed data pipeline for fetching scientific publications."""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Publication
from app.services.base_pipeline import BasePipeline
from app.utils.http_client import HTTPClient
from app.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class PubMedPipeline(BasePipeline):
    """
    Pipeline for fetching publication data from PubMed.

    Uses NCBI E-utilities API to fetch:
    - Publication metadata
    - Abstracts
    - Gene and variant mentions
    - Citation counts (from external sources)

    API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25501/
    """

    EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Common gene symbols to search for
    TARGET_GENES = [
        "EGFR", "TP53", "KRAS", "BRAF", "PIK3CA",
        "BRCA1", "BRCA2", "ALK", "MET", "ROS1",
        "HER2", "ERBB2", "RET", "NTRK", "FGFR",
    ]

    def __init__(self):
        """Initialize PubMed pipeline."""
        super().__init__("PubMed")

        # Set up rate limiter (same as ClinVar)
        rate_limit = (
            settings.NCBI_RATE_LIMIT
            if settings.NCBI_API_KEY
            else 3
        )

        self.rate_limiter = RateLimiter(
            calls_per_second=rate_limit,
            name="PubMed_EUtils"
        )

        self.client: Optional[HTTPClient] = None

        # Common parameters
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
        Extract publication data from PubMed.

        Args:
            full_refresh: If True, fetch all pubs; if False, fetch recent only
            limit: Maximum number of publications to fetch

        Returns:
            List of raw publication records
        """
        self.client = HTTPClient(
            rate_limiter=self.rate_limiter,
            name="PubMed",
            timeout=60
        )

        async with self.client:
            publications = []

            # Search for publications by target genes
            for gene in self.TARGET_GENES[:5]:  # Limit for demo
                try:
                    gene_pubs = await self._search_publications_by_gene(
                        gene=gene,
                        full_refresh=full_refresh,
                        limit=limit // len(self.TARGET_GENES[:5]) if limit else 20
                    )
                    publications.extend(gene_pubs)

                    if limit and len(publications) >= limit:
                        publications = publications[:limit]
                        break

                except Exception as e:
                    self.logger.error(f"Error fetching publications for {gene}: {e}")
                    self.stats["errors"] += 1

            return publications

    async def _search_publications_by_gene(
        self,
        gene: str,
        full_refresh: bool = False,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search PubMed for publications mentioning a gene.

        Args:
            gene: Gene symbol
            full_refresh: Get all publications or recent only
            limit: Maximum number of publications

        Returns:
            List of publication records
        """
        # Build search query
        query_parts = [
            f"{gene}[Title/Abstract]",
            "(mutation[Title/Abstract] OR variant[Title/Abstract])",
            "(cancer[MeSH] OR neoplasm[MeSH] OR therapy[MeSH])",
        ]

        # For incremental updates, limit by publication date
        if not full_refresh:
            checkpoint = self.load_checkpoint()
            if checkpoint and "last_update" in checkpoint:
                # Get publications from last 30 days
                mindate = (datetime.utcnow() - timedelta(days=30)).strftime("%Y/%m/%d")
            else:
                # First run: get publications from last 12 months
                mindate = (datetime.utcnow() - timedelta(days=365)).strftime("%Y/%m/%d")

            query_parts.append(f"{mindate}[pdat]")

        query = " AND ".join(query_parts)

        # Step 1: Search for PMIDs
        pmids = await self._search_pmids(query, limit)

        if not pmids:
            return []

        # Step 2: Fetch publication details
        publications = await self._fetch_publication_details(pmids)

        return publications

    async def _search_pmids(self, query: str, limit: int) -> List[str]:
        """
        Search for PubMed IDs matching query.

        Args:
            query: Search query
            limit: Maximum number of PMIDs

        Returns:
            List of PMIDs
        """
        params = {
            **self.common_params,
            "db": "pubmed",
            "term": query,
            "retmax": str(limit),
            "retmode": "json",
            "sort": "relevance",
        }

        url = f"{self.EUTILS_BASE_URL}/esearch.fcgi"

        self.logger.info(f"Searching PubMed: {query}")

        response = await self.client.get(url, params=params)

        # Parse response
        result = response.get("esearchresult", {})
        pmids = result.get("idlist", [])

        self.logger.info(f"Found {len(pmids)} publications")

        return pmids

    async def _fetch_publication_details(
        self,
        pmids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch detailed information for PMIDs.

        Args:
            pmids: List of PubMed IDs

        Returns:
            List of publication dictionaries
        """
        publications = []

        # Fetch in batches
        batch_size = 100

        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]

            self.logger.info(
                f"Fetching batch {i // batch_size + 1}/"
                f"{(len(pmids) + batch_size - 1) // batch_size}"
            )

            params = {
                **self.common_params,
                "db": "pubmed",
                "id": ",".join(batch_pmids),
                "rettype": "abstract",
                "retmode": "xml",
            }

            url = f"{self.EUTILS_BASE_URL}/efetch.fcgi"
            response = await self.client.get(url, params=params)

            # Parse XML response
            batch_pubs = self._parse_pubmed_xml(response)
            publications.extend(batch_pubs)

        return publications

    def _parse_pubmed_xml(self, xml_data: str) -> List[Dict[str, Any]]:
        """
        Parse PubMed XML response.

        Args:
            xml_data: XML response string

        Returns:
            List of parsed publication dictionaries
        """
        publications = []

        try:
            root = ET.fromstring(xml_data)

            for article in root.findall(".//PubmedArticle"):
                try:
                    pub = self._parse_article(article)
                    if pub:
                        publications.append(pub)
                except Exception as e:
                    self.logger.warning(f"Failed to parse article: {e}")
                    self.stats["errors"] += 1

        except ET.ParseError as e:
            self.logger.error(f"XML parsing error: {e}")
            self.stats["errors"] += 1

        return publications

    def _parse_article(self, article: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse individual article from XML.

        Args:
            article: PubmedArticle XML element

        Returns:
            Parsed publication dictionary or None
        """
        # Get PMID
        pmid_elem = article.find(".//PMID")
        if pmid_elem is None:
            return None

        pmid = pmid_elem.text

        # Get title
        title_elem = article.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else None

        # Get abstract
        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join(
            elem.text for elem in abstract_parts if elem.text
        ) if abstract_parts else None

        # Get authors
        authors = []
        for author in article.findall(".//Author"):
            last_name = author.findtext("LastName", "")
            fore_name = author.findtext("ForeName", "")
            if last_name:
                authors.append(f"{fore_name} {last_name}".strip())

        # Get journal
        journal_elem = article.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else None

        # Get publication date
        pub_date = self._parse_publication_date(article)

        # Extract mentioned genes and variants from text
        text = f"{title or ''} {abstract or ''}"
        mentioned_genes = self._extract_genes(text)
        mentioned_variants = self._extract_variants(text)

        return {
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors if authors else None,
            "journal": journal,
            "publication_date": pub_date,
            "citation_count": None,  # TODO: Fetch from external API
            "mentioned_genes": mentioned_genes if mentioned_genes else None,
            "mentioned_variants": mentioned_variants if mentioned_variants else None,
            "mentioned_drugs": None,  # TODO: Extract drug names
        }

    def _parse_publication_date(self, article: ET.Element) -> Optional[datetime]:
        """
        Parse publication date from article XML.

        Args:
            article: PubmedArticle XML element

        Returns:
            Publication date or None
        """
        # Try article date first
        pub_date = article.find(".//PubDate")
        if pub_date is not None:
            year = pub_date.findtext("Year")
            month = pub_date.findtext("Month")
            day = pub_date.findtext("Day")

            if year:
                try:
                    if month and day:
                        # Convert month name to number if needed
                        if not month.isdigit():
                            month_map = {
                                "Jan": "01", "Feb": "02", "Mar": "03",
                                "Apr": "04", "May": "05", "Jun": "06",
                                "Jul": "07", "Aug": "08", "Sep": "09",
                                "Oct": "10", "Nov": "11", "Dec": "12",
                            }
                            month = month_map.get(month[:3], "01")

                        date_str = f"{year}-{month}-{day}"
                        return datetime.strptime(date_str, "%Y-%m-%d")
                    elif month:
                        if not month.isdigit():
                            month = "01"
                        date_str = f"{year}-{month}-01"
                        return datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        date_str = f"{year}-01-01"
                        return datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass

        return None

    def _extract_genes(self, text: str) -> List[str]:
        """
        Extract gene symbols from text.

        Args:
            text: Article text (title + abstract)

        Returns:
            List of gene symbols found
        """
        if not text:
            return []

        genes = []
        text_upper = text.upper()

        # Look for known gene symbols
        all_genes = self.TARGET_GENES + [
            "AKT1", "PTEN", "NRAS", "KIT", "PDGFRA",
            "IDH1", "IDH2", "JAK2", "MPL", "CALR",
        ]

        for gene in all_genes:
            # Use word boundaries to avoid partial matches
            pattern = rf"\b{gene}\b"
            if re.search(pattern, text_upper):
                genes.append(gene)

        return list(set(genes))  # Remove duplicates

    def _extract_variants(self, text: str) -> List[str]:
        """
        Extract variant names from text.

        Args:
            text: Article text

        Returns:
            List of variant names found
        """
        if not text:
            return []

        variants = []

        # Pattern for variants like "EGFR L858R", "BRAF V600E"
        pattern = r"\b([A-Z]{2,6})\s+([A-Z]\d+[A-Z])\b"
        matches = re.findall(pattern, text)

        for gene, mutation in matches:
            variants.append(f"{gene} {mutation}")

        return list(set(variants))  # Remove duplicates

    async def transform(
        self,
        raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Transform raw publication data.

        Args:
            raw_data: Raw publication records

        Returns:
            Transformed publication records
        """
        # Data is already well-structured from parsing
        return raw_data

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate publication record.

        Args:
            record: Publication record

        Returns:
            True if valid, False otherwise
        """
        # Must have PMID
        if not record.get("pmid"):
            return False

        # Must have title or abstract
        if not record.get("title") and not record.get("abstract"):
            return False

        return True

    async def load(
        self,
        db: AsyncSession,
        data: List[Dict[str, Any]]
    ) -> None:
        """
        Load publications into database.

        Args:
            db: Database session
            data: Validated publication records
        """
        for record in data:
            try:
                # Upsert publication
                stmt = insert(Publication).values(**record)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["pmid"],
                    set_={
                        "title": stmt.excluded.title,
                        "abstract": stmt.excluded.abstract,
                        "authors": stmt.excluded.authors,
                        "journal": stmt.excluded.journal,
                        "publication_date": stmt.excluded.publication_date,
                        "citation_count": stmt.excluded.citation_count,
                        "mentioned_genes": stmt.excluded.mentioned_genes,
                        "mentioned_variants": stmt.excluded.mentioned_variants,
                        "mentioned_drugs": stmt.excluded.mentioned_drugs,
                        "updated_at": datetime.utcnow(),
                    }
                )

                result = await db.execute(stmt)

                if result.rowcount == 1:
                    self.stats["inserted"] += 1
                else:
                    self.stats["updated"] += 1

            except Exception as e:
                self.logger.warning(f"Failed to load publication {record['pmid']}: {e}")
                self.stats["errors"] += 1

        # Commit all changes
        await db.commit()

        # Save checkpoint
        self.save_checkpoint({
            "last_update": datetime.utcnow().isoformat(),
            "total_publications": self.stats["inserted"] + self.stats["updated"],
        })
