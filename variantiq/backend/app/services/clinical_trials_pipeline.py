"""Clinical Trials data pipeline for fetching trial information."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import ClinicalTrial
from app.services.base_pipeline import BasePipeline
from app.utils.http_client import HTTPClient
from app.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class ClinicalTrialsPipeline(BasePipeline):
    """
    Pipeline for fetching clinical trial data from ClinicalTrials.gov.

    Uses ClinicalTrials.gov API v2 to fetch:
    - Trial metadata
    - Phase and status
    - Sponsors and interventions
    - Target genes and conditions
    - Enrollment and dates

    API Documentation: https://clinicaltrials.gov/data-api/about-api
    """

    API_BASE_URL = "https://clinicaltrials.gov/api/v2"

    def __init__(self):
        """Initialize Clinical Trials pipeline."""
        super().__init__("ClinicalTrials")

        # Rate limiter (no official limit, but be respectful)
        self.rate_limiter = RateLimiter(
            calls_per_second=2,
            name="ClinicalTrials_API"
        )

        self.client: Optional[HTTPClient] = None

    async def extract(
        self,
        full_refresh: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract clinical trial data.

        Args:
            full_refresh: If True, fetch all trials; if False, fetch recent updates
            limit: Maximum number of trials to fetch

        Returns:
            List of raw trial records
        """
        self.client = HTTPClient(
            rate_limiter=self.rate_limiter,
            name="ClinicalTrials",
            timeout=60
        )

        async with self.client:
            # Search for oncology/gene therapy trials
            trials = await self._search_trials(
                full_refresh=full_refresh,
                limit=limit
            )

            return trials

    async def _search_trials(
        self,
        full_refresh: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant clinical trials.

        Args:
            full_refresh: Get all trials or just recent updates
            limit: Maximum number of trials

        Returns:
            List of trial records
        """
        trials = []

        # Define search queries for different therapeutic areas
        search_queries = [
            # Cancer genomics trials
            "cancer AND (mutation OR variant OR genomic)",
            # Gene therapy
            "gene therapy",
            # Targeted therapy
            "targeted therapy AND biomarker",
            # Precision medicine
            "precision medicine AND genetic",
        ]

        # Limit queries if limit is set
        max_per_query = (limit // len(search_queries)) if limit else 100

        for query in search_queries:
            try:
                query_trials = await self._fetch_trials_by_query(
                    query=query,
                    full_refresh=full_refresh,
                    limit=max_per_query
                )
                trials.extend(query_trials)

                if limit and len(trials) >= limit:
                    trials = trials[:limit]
                    break

            except Exception as e:
                self.logger.error(f"Error searching trials with query '{query}': {e}")
                self.stats["errors"] += 1

        return trials

    async def _fetch_trials_by_query(
        self,
        query: str,
        full_refresh: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch trials matching a search query.

        Args:
            query: Search query
            full_refresh: Get all matching trials or recent only
            limit: Maximum number of trials

        Returns:
            List of trial records
        """
        # Build filter parameters
        filter_params = {
            "query.cond": query,
        }

        # For incremental updates, filter by update date
        if not full_refresh:
            checkpoint = self.load_checkpoint()
            if checkpoint and "last_update" in checkpoint:
                # Get trials updated since last run
                last_update = datetime.fromisoformat(checkpoint["last_update"])
                min_date = last_update.strftime("%Y-%m-%d")
            else:
                # First run: get trials from last 6 months
                min_date = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")

            filter_params["filter.advanced"] = f"AREA[LastUpdatePostDate]RANGE[{min_date},MAX]"

        # Request parameters
        params = {
            "format": "json",
            "pageSize": min(limit, 100),  # Max 100 per page
            "query.term": query,
        }

        params.update(filter_params)

        url = f"{self.API_BASE_URL}/studies"

        self.logger.info(f"Searching trials: {query}")

        try:
            response = await self.client.get(url, params=params)

            # Parse response
            studies = response.get("studies", [])

            self.logger.info(f"Found {len(studies)} trials for query: {query}")

            return studies

        except Exception as e:
            self.logger.error(f"Error fetching trials: {e}")
            return []

    async def transform(
        self,
        raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Transform raw trial data.

        Args:
            raw_data: Raw trial records from API

        Returns:
            Transformed trial records
        """
        transformed = []

        for trial in raw_data:
            try:
                protocol_section = trial.get("protocolSection", {})
                identification = protocol_section.get("identificationModule", {})
                status = protocol_section.get("statusModule", {})
                description = protocol_section.get("descriptionModule", {})
                design = protocol_section.get("designModule", {})
                arms_interventions = protocol_section.get("armsInterventionsModule", {})
                conditions = protocol_section.get("conditionsModule", {})
                sponsor = protocol_section.get("sponsorCollaboratorsModule", {})
                enrollment = design.get("enrollmentInfo", {})

                # Extract key fields
                nct_id = identification.get("nctId")
                if not nct_id:
                    continue

                # Parse phases
                phase_list = design.get("phases", [])
                phase = phase_list[0] if phase_list else None

                # Parse interventions to find target genes
                interventions = arms_interventions.get("interventions", [])
                intervention_text = " | ".join(
                    [f"{i.get('type', '')}: {i.get('name', '')}" for i in interventions]
                )

                # Extract dates
                start_date_struct = status.get("startDateStruct", {})
                completion_date_struct = status.get("completionDateStruct", {})

                transformed_trial = {
                    "nct_id": nct_id,
                    "title": identification.get("officialTitle") or identification.get("briefTitle"),
                    "phase": phase,
                    "status": status.get("overallStatus"),
                    "sponsor": sponsor.get("leadSponsor", {}).get("name"),
                    "intervention": intervention_text,
                    "condition": " | ".join(conditions.get("conditions", [])),
                    "enrollment": enrollment.get("count"),
                    "start_date": self._parse_date(start_date_struct.get("date")),
                    "completion_date": self._parse_date(completion_date_struct.get("date")),
                    "primary_outcome": description.get("briefSummary"),
                    "results_available": False,  # TODO: Check for results
                    # Will be enriched later with gene/variant mapping
                    "target_gene": None,
                    "target_variant": None,
                }

                transformed.append(transformed_trial)

            except Exception as e:
                self.logger.warning(f"Error transforming trial: {e}")
                self.stats["errors"] += 1

        return transformed

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string to datetime.

        Args:
            date_str: Date string in various formats

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None

        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m",
            "%Y",
            "%B %d, %Y",
            "%B %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate trial record.

        Args:
            record: Trial record

        Returns:
            True if valid, False otherwise
        """
        # Must have NCT ID
        if not record.get("nct_id"):
            return False

        # NCT ID format validation
        nct_id = record["nct_id"]
        if not nct_id.startswith("NCT") or len(nct_id) != 11:
            return False

        return True

    async def load(
        self,
        db: AsyncSession,
        data: List[Dict[str, Any]]
    ) -> None:
        """
        Load clinical trials into database.

        Args:
            db: Database session
            data: Validated trial records
        """
        for record in data:
            try:
                # Upsert trial
                stmt = insert(ClinicalTrial).values(**record)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["nct_id"],
                    set_={
                        "title": stmt.excluded.title,
                        "phase": stmt.excluded.phase,
                        "status": stmt.excluded.status,
                        "sponsor": stmt.excluded.sponsor,
                        "intervention": stmt.excluded.intervention,
                        "condition": stmt.excluded.condition,
                        "enrollment": stmt.excluded.enrollment,
                        "start_date": stmt.excluded.start_date,
                        "completion_date": stmt.excluded.completion_date,
                        "primary_outcome": stmt.excluded.primary_outcome,
                        "results_available": stmt.excluded.results_available,
                        "updated_at": datetime.utcnow(),
                    }
                )

                result = await db.execute(stmt)

                if result.rowcount == 1:
                    self.stats["inserted"] += 1
                else:
                    self.stats["updated"] += 1

            except Exception as e:
                self.logger.warning(f"Failed to load trial {record['nct_id']}: {e}")
                self.stats["errors"] += 1

        # Commit all changes
        await db.commit()

        # Save checkpoint
        self.save_checkpoint({
            "last_update": datetime.utcnow().isoformat(),
            "total_trials": self.stats["inserted"] + self.stats["updated"],
        })
