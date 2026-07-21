"""End-to-end analytical pipeline from Hive DWS export to serving datasets."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from intellibasket.analytics.basket import calculateRuleDrift, mineAssociationRules
from intellibasket.analytics.models import AnalyticsConfig
from intellibasket.analytics.rfm import (
    calculateMonthlySnapshots,
    calculateSegmentMigrations,
    summarizeSegments,
)

HIVE_BASKET_COLUMNS = [
    "invoiceNo",
    "customerId",
    "invoiceTs",
    "stockCode",
    "productName",
    "itemQuantity",
    "itemAmount",
    "dataOrigin",
    "sourceSegmentCode",
    "generationConfidence",
    "generationBatchId",
]


def loadHiveBasketItems(inputPath: Path) -> pd.DataFrame:
    """Load the headerless Hive DWS basket-item export."""
    transactions = pd.read_csv(
        inputPath,
        sep="\t",
        names=HIVE_BASKET_COLUMNS,
        dtype={
            "invoiceNo": "string",
            "customerId": "string",
            "stockCode": "string",
            "productName": "string",
        },
        parse_dates=["invoiceTs"],
    )
    transactions["itemQuantity"] = pd.to_numeric(transactions["itemQuantity"], errors="coerce")
    transactions["itemAmount"] = pd.to_numeric(transactions["itemAmount"], errors="coerce")
    transactions["dataOrigin"] = transactions["dataOrigin"].fillna("REAL")
    transactions["generationConfidence"] = pd.to_numeric(
        transactions["generationConfidence"], errors="coerce"
    ).fillna(1.0)
    transactions = transactions.dropna(
        subset=["invoiceNo", "customerId", "invoiceTs", "stockCode", "itemAmount"]
    )
    return transactions


def calculateBusinessOverview(transactions: pd.DataFrame) -> dict[str, object]:
    """Build top-level KPIs from valid DWS basket items."""
    basketAmounts = transactions.groupby("invoiceNo")["itemAmount"].sum()
    return {
        "customerCount": int(transactions["customerId"].nunique()),
        "orderCount": int(transactions["invoiceNo"].nunique()),
        "productCount": int(transactions["stockCode"].nunique()),
        "itemQuantity": int(transactions["itemQuantity"].sum()),
        "salesAmount": round(float(transactions["itemAmount"].sum()), 2),
        "averageBasketAmount": round(float(basketAmounts.mean()), 2),
        "minInvoiceTs": transactions["invoiceTs"].min().isoformat(),
        "maxInvoiceTs": transactions["invoiceTs"].max().isoformat(),
    }


def calculateMonthlySales(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate monthly customer, order, sales, and basket KPIs."""
    monthlyFrame = transactions.assign(
        invoiceMonth=transactions["invoiceTs"].dt.to_period("M").astype(str)
    )
    monthlySales = (
        monthlyFrame.groupby("invoiceMonth", as_index=False)
        .agg(
            customerCount=("customerId", "nunique"),
            orderCount=("invoiceNo", "nunique"),
            productCount=("stockCode", "nunique"),
            itemQuantity=("itemQuantity", "sum"),
            salesAmount=("itemAmount", "sum"),
        )
        .sort_values("invoiceMonth")
    )
    monthlySales["averageBasketAmount"] = monthlySales["salesAmount"] / monthlySales["orderCount"]
    monthlySales[["salesAmount", "averageBasketAmount"]] = monthlySales[
        ["salesAmount", "averageBasketAmount"]
    ].round(2)
    return monthlySales


def calculateTopProducts(transactions: pd.DataFrame, limit: int = 100) -> pd.DataFrame:
    """Rank products using both sales and basket coverage."""
    return (
        transactions.groupby(["stockCode", "productName"], as_index=False)
        .agg(
            orderCount=("invoiceNo", "nunique"),
            customerCount=("customerId", "nunique"),
            itemQuantity=("itemQuantity", "sum"),
            salesAmount=("itemAmount", "sum"),
        )
        .sort_values(["salesAmount", "orderCount"], ascending=False)
        .head(limit)
        .assign(salesAmount=lambda frame: frame["salesAmount"].round(2))
        .reset_index(drop=True)
    )


class AnalyticsPipeline:
    """Coordinate RFM, basket mining, drift analysis, and output persistence."""

    def __init__(self, config: AnalyticsConfig) -> None:
        self._config = config

    def run(self, inputPath: Path, outputDirectory: Path) -> dict[str, object]:
        """Execute the complete analytics pipeline and return its manifest."""
        outputDirectory.mkdir(parents=True, exist_ok=True)
        transactions = loadHiveBasketItems(inputPath)
        snapshotFrame = calculateMonthlySnapshots(transactions, self._config.rfm)
        finalSnapshotDate = snapshotFrame["snapshotDate"].max()
        finalRfmFrame = snapshotFrame.loc[
            snapshotFrame["snapshotDate"].eq(finalSnapshotDate)
        ].copy()
        segmentSummary = summarizeSegments(snapshotFrame)
        migrations = calculateSegmentMigrations(snapshotFrame)
        associationRules = mineAssociationRules(
            transactions,
            finalRfmFrame,
            self._config.basket,
        )

        maxInvoiceDate = transactions["invoiceTs"].max()
        currentStart = maxInvoiceDate - pd.DateOffset(years=1)
        previousStart = currentStart - pd.DateOffset(years=1)
        previousTransactions = transactions.loc[
            transactions["invoiceTs"].ge(previousStart) & transactions["invoiceTs"].lt(currentStart)
        ]
        currentTransactions = transactions.loc[transactions["invoiceTs"].ge(currentStart)]
        previousRules = mineAssociationRules(
            previousTransactions,
            customerSegments=None,
            config=self._config.basket,
        )
        currentRules = mineAssociationRules(
            currentTransactions,
            customerSegments=None,
            config=self._config.basket,
        )
        ruleDrift = calculateRuleDrift(previousRules, currentRules)

        outputFrames = {
            "rfmSnapshots": snapshotFrame,
            "rfmCustomers": finalRfmFrame,
            "rfmSegmentSummary": segmentSummary,
            "segmentMigrations": migrations,
            "associationRules": associationRules,
            "ruleDrift": ruleDrift,
            "monthlySales": calculateMonthlySales(transactions),
            "topProducts": calculateTopProducts(transactions),
        }
        outputFiles: dict[str, str] = {}
        for outputName, outputFrame in outputFrames.items():
            outputPath = outputDirectory / f"{outputName}.csv"
            outputFrame.to_csv(outputPath, index=False, encoding="utf-8-sig")
            outputFiles[outputName] = str(outputPath)

        overview = calculateBusinessOverview(transactions)
        overviewPath = outputDirectory / "businessOverview.json"
        overviewPath.write_text(
            json.dumps(overview, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        outputFiles["businessOverview"] = str(overviewPath)

        manifest = {
            "inputPath": str(inputPath.resolve()),
            "outputDirectory": str(outputDirectory.resolve()),
            "finalSnapshotDate": pd.Timestamp(finalSnapshotDate).date().isoformat(),
            "transactionRowCount": len(transactions),
            "rfmCustomerCount": len(finalRfmFrame),
            "associationRuleCount": len(associationRules),
            "ruleDriftCount": len(ruleDrift),
            "config": {
                "rfm": asdict(self._config.rfm),
                "basket": asdict(self._config.basket),
            },
            "outputs": outputFiles,
        }
        manifestPath = outputDirectory / "manifest.json"
        manifestPath.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest
