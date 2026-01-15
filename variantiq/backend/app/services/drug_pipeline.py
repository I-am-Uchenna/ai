"""Drug data pipeline for loading drug information.

Note: DrugBank requires a paid API key. This pipeline provides a simplified
approach using seed data of common oncology drugs. For production, integrate
with DrugBank API or use the full XML download.
"""

from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Drug
from app.services.base_pipeline import BasePipeline

logger = get_logger(__name__)


class DrugPipeline(BasePipeline):
    """
    Pipeline for loading drug data.

    For demo purposes, uses curated seed data of common targeted therapies.
    In production, would integrate with DrugBank API or XML export.
    """

    # Curated list of major targeted cancer therapies
    SEED_DRUGS = [
        {
            "drug_name": "Osimertinib",
            "drugbank_id": "DB09330",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "Irreversible EGFR tyrosine kinase inhibitor targeting T790M resistance mutation",
            "indication": "EGFR mutation-positive non-small cell lung cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2015, 11, 13),
            "patent_expiry": datetime(2030, 12, 31),
            "targets": ["EGFR", "EGFR T790M"],
        },
        {
            "drug_name": "Erlotinib",
            "drugbank_id": "DB00530",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "EGFR tyrosine kinase inhibitor",
            "indication": "EGFR mutation-positive non-small cell lung cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2004, 11, 18),
            "patent_expiry": datetime(2022, 11, 18),
            "targets": ["EGFR"],
        },
        {
            "drug_name": "Gefitinib",
            "drugbank_id": "DB00317",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "EGFR tyrosine kinase inhibitor",
            "indication": "EGFR mutation-positive non-small cell lung cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2003, 5, 5),
            "patent_expiry": datetime(2019, 5, 5),
            "targets": ["EGFR"],
        },
        {
            "drug_name": "Dabrafenib",
            "drugbank_id": "DB08912",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "BRAF kinase inhibitor",
            "indication": "BRAF V600E/K mutation-positive melanoma and NSCLC",
            "approval_status": "Approved",
            "approval_date": datetime(2013, 5, 29),
            "patent_expiry": datetime(2028, 5, 29),
            "targets": ["BRAF", "BRAF V600E"],
        },
        {
            "drug_name": "Vemurafenib",
            "drugbank_id": "DB08881",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "BRAF kinase inhibitor",
            "indication": "BRAF V600E mutation-positive melanoma",
            "approval_status": "Approved",
            "approval_date": datetime(2011, 8, 17),
            "patent_expiry": datetime(2026, 8, 17),
            "targets": ["BRAF", "BRAF V600E"],
        },
        {
            "drug_name": "Trastuzumab",
            "drugbank_id": "DB00072",
            "drug_type": "Monoclonal Antibody",
            "mechanism_of_action": "HER2/ERBB2 receptor antagonist",
            "indication": "HER2-positive breast cancer and gastric cancer",
            "approval_status": "Approved",
            "approval_date": datetime(1998, 9, 25),
            "patent_expiry": datetime(2019, 6, 1),
            "targets": ["HER2", "ERBB2"],
        },
        {
            "drug_name": "Pertuzumab",
            "drugbank_id": "DB06366",
            "drug_type": "Monoclonal Antibody",
            "mechanism_of_action": "HER2/ERBB2 dimerization inhibitor",
            "indication": "HER2-positive breast cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2012, 6, 8),
            "patent_expiry": datetime(2027, 6, 8),
            "targets": ["HER2", "ERBB2"],
        },
        {
            "drug_name": "Crizotinib",
            "drugbank_id": "DB08865",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "ALK and ROS1 tyrosine kinase inhibitor",
            "indication": "ALK or ROS1 positive non-small cell lung cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2011, 8, 26),
            "patent_expiry": datetime(2026, 8, 26),
            "targets": ["ALK", "ROS1", "MET"],
        },
        {
            "drug_name": "Alectinib",
            "drugbank_id": "DB09015",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "ALK tyrosine kinase inhibitor",
            "indication": "ALK-positive non-small cell lung cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2015, 12, 11),
            "patent_expiry": datetime(2030, 12, 11),
            "targets": ["ALK"],
        },
        {
            "drug_name": "Olaparib",
            "drugbank_id": "DB09074",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "PARP inhibitor",
            "indication": "BRCA-mutated ovarian, breast, prostate, and pancreatic cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2014, 12, 19),
            "patent_expiry": datetime(2029, 12, 19),
            "targets": ["PARP1", "PARP2", "BRCA1", "BRCA2"],
        },
        {
            "drug_name": "Rucaparib",
            "drugbank_id": "DB11652",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "PARP inhibitor",
            "indication": "BRCA-mutated ovarian and prostate cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2016, 12, 19),
            "patent_expiry": datetime(2031, 12, 19),
            "targets": ["PARP1", "PARP2", "BRCA1", "BRCA2"],
        },
        {
            "drug_name": "Imatinib",
            "drugbank_id": "DB00619",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "BCR-ABL, KIT, and PDGFRA tyrosine kinase inhibitor",
            "indication": "CML, GIST, and other cancers",
            "approval_status": "Approved",
            "approval_date": datetime(2001, 5, 10),
            "patent_expiry": datetime(2015, 5, 10),
            "targets": ["BCR-ABL", "KIT", "PDGFRA"],
        },
        {
            "drug_name": "Sotorasib",
            "drugbank_id": "DB15825",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "KRAS G12C inhibitor",
            "indication": "KRAS G12C mutation-positive non-small cell lung cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2021, 5, 28),
            "patent_expiry": datetime(2036, 5, 28),
            "targets": ["KRAS", "KRAS G12C"],
        },
        {
            "drug_name": "Adagrasib",
            "drugbank_id": "DB16836",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "KRAS G12C inhibitor",
            "indication": "KRAS G12C mutation-positive non-small cell lung cancer",
            "approval_status": "Approved",
            "approval_date": datetime(2022, 12, 12),
            "patent_expiry": datetime(2037, 12, 12),
            "targets": ["KRAS", "KRAS G12C"],
        },
        {
            "drug_name": "Larotrectinib",
            "drugbank_id": "DB11894",
            "drug_type": "Small Molecule",
            "mechanism_of_action": "TRK inhibitor",
            "indication": "NTRK fusion-positive solid tumors",
            "approval_status": "Approved",
            "approval_date": datetime(2018, 11, 26),
            "patent_expiry": datetime(2033, 11, 26),
            "targets": ["NTRK1", "NTRK2", "NTRK3"],
        },
    ]

    def __init__(self):
        """Initialize Drug pipeline."""
        super().__init__("Drugs")

    async def extract(
        self,
        full_refresh: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract drug data (from seed data).

        Args:
            full_refresh: Ignored for seed data
            limit: Maximum number of drugs

        Returns:
            List of drug records
        """
        drugs = self.SEED_DRUGS.copy()

        if limit:
            drugs = drugs[:limit]

        self.logger.info(f"Loaded {len(drugs)} drugs from seed data")

        return drugs

    async def transform(
        self,
        raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Transform drug data (already clean).

        Args:
            raw_data: Raw drug records

        Returns:
            Transformed drug records
        """
        return raw_data

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate drug record.

        Args:
            record: Drug record

        Returns:
            True if valid, False otherwise
        """
        # Must have drug name and drugbank ID
        if not record.get("drug_name") or not record.get("drugbank_id"):
            return False

        return True

    async def load(
        self,
        db: AsyncSession,
        data: List[Dict[str, Any]]
    ) -> None:
        """
        Load drugs into database.

        Args:
            db: Database session
            data: Validated drug records
        """
        for record in data:
            try:
                # Upsert drug
                stmt = insert(Drug).values(**record)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["drugbank_id"],
                    set_={
                        "drug_name": stmt.excluded.drug_name,
                        "drug_type": stmt.excluded.drug_type,
                        "mechanism_of_action": stmt.excluded.mechanism_of_action,
                        "indication": stmt.excluded.indication,
                        "approval_status": stmt.excluded.approval_status,
                        "approval_date": stmt.excluded.approval_date,
                        "patent_expiry": stmt.excluded.patent_expiry,
                        "targets": stmt.excluded.targets,
                        "updated_at": datetime.utcnow(),
                    }
                )

                result = await db.execute(stmt)

                if result.rowcount == 1:
                    self.stats["inserted"] += 1
                else:
                    self.stats["updated"] += 1

            except Exception as e:
                self.logger.warning(f"Failed to load drug {record['drug_name']}: {e}")
                self.stats["errors"] += 1

        # Commit all changes
        await db.commit()

        self.logger.info(
            f"Loaded {self.stats['inserted']} new drugs, "
            f"{self.stats['updated']} updated"
        )
