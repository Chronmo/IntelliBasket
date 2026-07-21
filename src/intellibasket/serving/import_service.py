"""Idempotent import of analytical CSV and JSON outputs into the serving database."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from intellibasket.serving.models import (
    AssociationRuleRecord,
    BusinessOverviewRecord,
    MonthlySaleRecord,
    RfmCustomerSnapshotRecord,
    RfmSegmentSummaryRecord,
    RuleDriftRecord,
    SegmentMigrationRecord,
    TopProductRecord,
)


def parseInteger(rawValue: str) -> int:
    return int(float(rawValue))


def parseOptionalInteger(rawValue: str) -> int | None:
    return None if rawValue == "" else parseInteger(rawValue)


def parseDecimal(rawValue: str) -> Decimal:
    return Decimal(rawValue)


def parseOptionalDecimal(rawValue: str) -> Decimal | None:
    return None if rawValue == "" else Decimal(rawValue)


def parseDate(rawValue: str) -> date:
    return date.fromisoformat(rawValue[:10])


def parseDatetime(rawValue: str) -> datetime:
    return datetime.fromisoformat(rawValue)


def readCsvRecords(
    csvPath: Path,
    converters: dict[str, Callable[[str], Any]],
) -> list[dict[str, Any]]:
    """Read camelCase CSV records and convert explicitly typed fields."""
    with csvPath.open(encoding="utf-8-sig", newline="") as csvFile:
        records = list(csv.DictReader(csvFile))
    for record in records:
        for fieldName, converter in converters.items():
            record[fieldName] = converter(record[fieldName])
    return records


class ServingDataImporter:
    """Replace all analytical serving tables in one controlled import."""

    def __init__(self, sessionFactory: sessionmaker[Session]) -> None:
        self._sessionFactory = sessionFactory

    def importDirectory(self, outputDirectory: Path) -> dict[str, int]:
        """Import a complete analytics output directory idempotently."""
        overview = json.loads(
            (outputDirectory / "businessOverview.json").read_text(encoding="utf-8")
        )
        overview["salesAmount"] = Decimal(str(overview["salesAmount"]))
        overview["averageBasketAmount"] = Decimal(str(overview["averageBasketAmount"]))
        overview["minInvoiceTs"] = parseDatetime(overview["minInvoiceTs"])
        overview["maxInvoiceTs"] = parseDatetime(overview["maxInvoiceTs"])

        importDefinitions: list[tuple[type[Any], list[dict[str, Any]]]] = [
            (BusinessOverviewRecord, [overview]),
            (
                MonthlySaleRecord,
                readCsvRecords(
                    outputDirectory / "monthlySales.csv",
                    {
                        "customerCount": parseInteger,
                        "orderCount": parseInteger,
                        "productCount": parseInteger,
                        "itemQuantity": parseInteger,
                        "salesAmount": parseDecimal,
                        "averageBasketAmount": parseDecimal,
                    },
                ),
            ),
            (
                RfmCustomerSnapshotRecord,
                readCsvRecords(
                    outputDirectory / "rfmSnapshots.csv",
                    {
                        "snapshotDate": parseDate,
                        "latestPurchaseTs": parseDatetime,
                        "recencyDays": parseInteger,
                        "frequency": parseInteger,
                        "monetary": parseDecimal,
                        "rScore": parseInteger,
                        "fScore": parseInteger,
                        "mScore": parseInteger,
                    },
                ),
            ),
            (
                RfmSegmentSummaryRecord,
                readCsvRecords(
                    outputDirectory / "rfmSegmentSummary.csv",
                    {
                        "snapshotDate": parseDate,
                        "customerCount": parseInteger,
                        "totalMonetary": parseDecimal,
                        "averageRecencyDays": parseDecimal,
                        "averageFrequency": parseDecimal,
                        "averageMonetary": parseDecimal,
                        "customerShare": parseDecimal,
                        "monetaryShare": parseDecimal,
                    },
                ),
            ),
            (
                SegmentMigrationRecord,
                readCsvRecords(
                    outputDirectory / "segmentMigrations.csv",
                    {
                        "customerCount": parseInteger,
                        "fromSnapshotDate": parseDate,
                        "toSnapshotDate": parseDate,
                    },
                ),
            ),
            (
                AssociationRuleRecord,
                readCsvRecords(
                    outputDirectory / "associationRules.csv",
                    {
                        "support": parseDecimal,
                        "confidence": parseDecimal,
                        "lift": parseDecimal,
                        "leverage": parseOptionalDecimal,
                        "conviction": parseOptionalDecimal,
                        "coverageBasketCount": parseInteger,
                        "scopeBasketCount": parseInteger,
                        "rankScore": parseDecimal,
                    },
                ),
            ),
            (
                RuleDriftRecord,
                readCsvRecords(
                    outputDirectory / "ruleDrift.csv",
                    {
                        "previousSupport": parseOptionalDecimal,
                        "previousConfidence": parseOptionalDecimal,
                        "previousLift": parseOptionalDecimal,
                        "previousCoverageBasketCount": parseOptionalInteger,
                        "currentSupport": parseOptionalDecimal,
                        "currentConfidence": parseOptionalDecimal,
                        "currentLift": parseOptionalDecimal,
                        "currentCoverageBasketCount": parseOptionalInteger,
                        "liftDelta": parseOptionalDecimal,
                        "supportDelta": parseOptionalDecimal,
                    },
                ),
            ),
            (
                TopProductRecord,
                readCsvRecords(
                    outputDirectory / "topProducts.csv",
                    {
                        "orderCount": parseInteger,
                        "customerCount": parseInteger,
                        "itemQuantity": parseInteger,
                        "salesAmount": parseDecimal,
                    },
                ),
            ),
        ]

        importedCounts: dict[str, int] = {}
        with self._sessionFactory() as databaseSession:
            try:
                for modelType, records in importDefinitions:
                    databaseSession.execute(delete(modelType))
                    if records:
                        databaseSession.bulk_insert_mappings(modelType, records)
                    importedCounts[modelType.__tablename__] = len(records)
                databaseSession.commit()
            except Exception:
                databaseSession.rollback()
                raise
        return importedCounts
