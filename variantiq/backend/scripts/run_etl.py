#!/usr/bin/env python3
"""
ETL Orchestration Script

Runs all data pipelines to populate the database with genomic,
clinical, and drug data from external sources.

Usage:
    python scripts/run_etl.py --full-refresh
    python scripts/run_etl.py --pipelines clinvar,drugs
    python scripts/run_etl.py --limit 100
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.base import AsyncSessionLocal
from app.services.clinvar_pipeline import ClinVarPipeline
from app.services.clinical_trials_pipeline import ClinicalTrialsPipeline
from app.services.drug_pipeline import DrugPipeline
from app.services.pubmed_pipeline import PubMedPipeline

# Setup logging
setup_logging()
logger = get_logger(__name__)


AVAILABLE_PIPELINES = {
    "clinvar": ClinVarPipeline,
    "trials": ClinicalTrialsPipeline,
    "pubmed": PubMedPipeline,
    "drugs": DrugPipeline,
}


async def run_pipeline(
    pipeline_class,
    full_refresh: bool = False,
    limit: int = None
) -> dict:
    """
    Run a single pipeline.

    Args:
        pipeline_class: Pipeline class to instantiate
        full_refresh: Whether to do full refresh
        limit: Limit number of records

    Returns:
        Pipeline statistics
    """
    pipeline = pipeline_class()

    async with AsyncSessionLocal() as db:
        try:
            stats = await pipeline.run(
                db=db,
                full_refresh=full_refresh,
                limit=limit
            )
            return stats
        except Exception as e:
            logger.exception(f"Pipeline {pipeline.name} failed: {e}")
            return {"error": str(e)}


async def run_all_pipelines(
    pipeline_names: list = None,
    full_refresh: bool = False,
    limit: int = None,
    parallel: bool = False
) -> dict:
    """
    Run multiple pipelines.

    Args:
        pipeline_names: List of pipeline names to run (None = all)
        full_refresh: Whether to do full refresh
        limit: Limit number of records per pipeline
        parallel: Run pipelines in parallel

    Returns:
        Combined statistics from all pipelines
    """
    # Determine which pipelines to run
    if pipeline_names:
        pipelines_to_run = {
            name: AVAILABLE_PIPELINES[name]
            for name in pipeline_names
            if name in AVAILABLE_PIPELINES
        }
    else:
        pipelines_to_run = AVAILABLE_PIPELINES

    logger.info(f"Running pipelines: {', '.join(pipelines_to_run.keys())}")
    logger.info(f"Full refresh: {full_refresh}, Limit: {limit}, Parallel: {parallel}")

    all_stats = {}

    if parallel:
        # Run pipelines in parallel
        tasks = [
            run_pipeline(pipeline_class, full_refresh, limit)
            for pipeline_class in pipelines_to_run.values()
        ]
        results = await asyncio.gather(*tasks)

        for name, stats in zip(pipelines_to_run.keys(), results):
            all_stats[name] = stats
    else:
        # Run pipelines sequentially
        for name, pipeline_class in pipelines_to_run.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"Starting pipeline: {name}")
            logger.info(f"{'='*60}\n")

            stats = await run_pipeline(pipeline_class, full_refresh, limit)
            all_stats[name] = stats

            logger.info(f"\n{'='*60}")
            logger.info(f"Pipeline {name} completed")
            logger.info(f"Stats: {stats}")
            logger.info(f"{'='*60}\n")

    return all_stats


def print_summary(all_stats: dict):
    """Print summary of all pipeline results."""
    logger.info("\n" + "="*60)
    logger.info("ETL SUMMARY")
    logger.info("="*60)

    total_inserted = 0
    total_updated = 0
    total_errors = 0
    total_duration = 0

    for pipeline_name, stats in all_stats.items():
        if "error" in stats:
            logger.error(f"❌ {pipeline_name}: FAILED - {stats['error']}")
            continue

        logger.info(f"\n{pipeline_name.upper()}:")
        logger.info(f"  Total records: {stats.get('total_records', 0)}")
        logger.info(f"  Inserted: {stats.get('inserted', 0)}")
        logger.info(f"  Updated: {stats.get('updated', 0)}")
        logger.info(f"  Skipped: {stats.get('skipped', 0)}")
        logger.info(f"  Errors: {stats.get('errors', 0)}")
        logger.info(f"  Duration: {stats.get('duration_seconds', 0):.2f}s")

        total_inserted += stats.get('inserted', 0)
        total_updated += stats.get('updated', 0)
        total_errors += stats.get('errors', 0)
        total_duration += stats.get('duration_seconds', 0)

    logger.info("\n" + "-"*60)
    logger.info("TOTALS:")
    logger.info(f"  Total inserted: {total_inserted}")
    logger.info(f"  Total updated: {total_updated}")
    logger.info(f"  Total errors: {total_errors}")
    logger.info(f"  Total duration: {total_duration:.2f}s")
    logger.info("="*60 + "\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run ETL pipelines to populate VariantIQ database"
    )

    parser.add_argument(
        "--pipelines",
        type=str,
        help=f"Comma-separated list of pipelines to run. Available: {', '.join(AVAILABLE_PIPELINES.keys())}",
    )

    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Do full refresh instead of incremental update"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of records per pipeline (for testing)"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run pipelines in parallel (faster but more resource intensive)"
    )

    args = parser.parse_args()

    # Parse pipeline names
    pipeline_names = None
    if args.pipelines:
        pipeline_names = [p.strip() for p in args.pipelines.split(",")]
        # Validate pipeline names
        invalid = [p for p in pipeline_names if p not in AVAILABLE_PIPELINES]
        if invalid:
            logger.error(f"Invalid pipeline names: {', '.join(invalid)}")
            logger.error(f"Available pipelines: {', '.join(AVAILABLE_PIPELINES.keys())}")
            return 1

    logger.info("Starting ETL process...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database: {settings.DATABASE_URL}")

    try:
        # Run pipelines
        all_stats = await run_all_pipelines(
            pipeline_names=pipeline_names,
            full_refresh=args.full_refresh,
            limit=args.limit,
            parallel=args.parallel
        )

        # Print summary
        print_summary(all_stats)

        logger.info("✅ ETL process completed successfully")
        return 0

    except Exception as e:
        logger.exception(f"❌ ETL process failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
