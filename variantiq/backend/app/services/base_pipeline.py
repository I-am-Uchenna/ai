"""Base data pipeline class for all data sources."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BasePipeline(ABC):
    """
    Abstract base class for data pipelines.

    All data source pipelines (ClinVar, DrugBank, etc.) inherit from this class.

    Features:
    - Standardized ETL workflow
    - Progress tracking
    - Error handling
    - Data validation
    - Incremental updates
    """

    def __init__(self, name: str):
        """
        Initialize pipeline.

        Args:
            name: Pipeline name for logging and tracking
        """
        self.name = name
        self.logger = get_logger(f"pipeline.{name}")

        # Statistics
        self.stats = {
            "total_records": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0,
        }

        # Paths
        self.raw_data_dir = Path(settings.RAW_DATA_DIR) / name.lower()
        self.processed_data_dir = Path(settings.PROCESSED_DATA_DIR) / name.lower()

        # Create directories
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        db: AsyncSession,
        full_refresh: bool = False,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run the complete ETL pipeline.

        Args:
            db: Database session
            full_refresh: If True, reload all data; if False, incremental update
            limit: Optional limit on number of records to process

        Returns:
            dict: Pipeline execution statistics
        """
        self.logger.info(
            f"Starting {self.name} pipeline "
            f"(full_refresh={full_refresh}, limit={limit})"
        )
        self.stats["start_time"] = datetime.utcnow()

        try:
            # Step 1: Extract data from source
            self.logger.info("Step 1/4: Extracting data...")
            raw_data = await self.extract(full_refresh=full_refresh, limit=limit)
            self.stats["total_records"] = len(raw_data)
            self.logger.info(f"Extracted {len(raw_data)} records")

            if not raw_data:
                self.logger.warning("No data extracted, pipeline complete")
                return self._finalize_stats()

            # Step 2: Transform/clean data
            self.logger.info("Step 2/4: Transforming data...")
            transformed_data = await self.transform(raw_data)
            self.logger.info(f"Transformed {len(transformed_data)} records")

            # Step 3: Validate data
            self.logger.info("Step 3/4: Validating data...")
            validated_data = await self.validate(transformed_data)
            self.logger.info(f"Validated {len(validated_data)} records")

            # Step 4: Load data into database
            self.logger.info("Step 4/4: Loading data to database...")
            await self.load(db, validated_data)
            self.logger.info(
                f"Loaded {self.stats['inserted']} new, "
                f"{self.stats['updated']} updated, "
                f"{self.stats['skipped']} skipped, "
                f"{self.stats['errors']} errors"
            )

            self.logger.info(f"{self.name} pipeline completed successfully")

        except Exception as e:
            self.logger.exception(f"{self.name} pipeline failed: {e}")
            self.stats["errors"] += 1
            raise

        finally:
            return self._finalize_stats()

    @abstractmethod
    async def extract(
        self,
        full_refresh: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract data from source.

        Args:
            full_refresh: If True, get all data; if False, get updates only
            limit: Optional limit on number of records

        Returns:
            List of raw data records
        """
        pass

    @abstractmethod
    async def transform(
        self,
        raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Transform/clean raw data.

        Args:
            raw_data: Raw extracted data

        Returns:
            Transformed data ready for validation
        """
        pass

    async def validate(
        self,
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate transformed data.

        Default implementation returns all data.
        Override for custom validation.

        Args:
            data: Transformed data

        Returns:
            Validated data ready for loading
        """
        valid_data = []

        for record in data:
            try:
                if self.validate_record(record):
                    valid_data.append(record)
                else:
                    self.stats["skipped"] += 1
            except Exception as e:
                self.logger.warning(
                    f"Validation failed for record: {e}"
                )
                self.stats["errors"] += 1

        return valid_data

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate a single record.

        Override for custom validation logic.

        Args:
            record: Data record

        Returns:
            True if valid, False otherwise
        """
        return True

    @abstractmethod
    async def load(
        self,
        db: AsyncSession,
        data: List[Dict[str, Any]]
    ) -> None:
        """
        Load validated data into database.

        Args:
            db: Database session
            data: Validated data to load
        """
        pass

    def _finalize_stats(self) -> Dict[str, Any]:
        """Finalize and return statistics."""
        self.stats["end_time"] = datetime.utcnow()
        self.stats["duration_seconds"] = (
            self.stats["end_time"] - self.stats["start_time"]
        ).total_seconds()

        return self.stats

    async def process_batch(
        self,
        items: List[Any],
        processor_func,
        batch_size: int = 100,
        max_concurrency: int = 5
    ) -> List[Any]:
        """
        Process items in batches with concurrency control.

        Args:
            items: Items to process
            processor_func: Async function to process each item
            batch_size: Batch size
            max_concurrency: Maximum concurrent tasks

        Returns:
            List of processed results
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrency)

        async def process_with_semaphore(item):
            async with semaphore:
                return await processor_func(item)

        # Process in batches
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            self.logger.debug(
                f"Processing batch {i // batch_size + 1}/"
                f"{(len(items) + batch_size - 1) // batch_size}"
            )

            batch_results = await asyncio.gather(
                *[process_with_semaphore(item) for item in batch],
                return_exceptions=True
            )

            # Filter out exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.warning(f"Batch processing error: {result}")
                    self.stats["errors"] += 1
                else:
                    results.append(result)

        return results

    def save_checkpoint(self, checkpoint_data: Dict[str, Any]) -> None:
        """
        Save pipeline checkpoint for incremental updates.

        Args:
            checkpoint_data: Checkpoint data to save
        """
        checkpoint_file = self.processed_data_dir / "checkpoint.json"

        import json
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, default=str, indent=2)

        self.logger.info(f"Checkpoint saved to {checkpoint_file}")

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Load pipeline checkpoint.

        Returns:
            Checkpoint data if exists, None otherwise
        """
        checkpoint_file = self.processed_data_dir / "checkpoint.json"

        if not checkpoint_file.exists():
            return None

        import json
        with open(checkpoint_file, "r") as f:
            return json.load(f)
