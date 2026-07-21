from __future__ import annotations

import pandas as pd

from intellibasket.analytics.augmentation import (
    AugmentationConfig,
    buildAugmentedTransactions,
    generateSyntheticTransactions,
)


def buildSourceTransactions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    baskets = {
        "I1": ("C1", ["A", "B", "C"]),
        "I2": ("C1", ["A", "B"]),
        "I3": ("C2", ["A", "B", "D"]),
        "I4": ("C2", ["A", "C"]),
        "I5": ("C3", ["B", "C", "D"]),
        "I6": ("C3", ["A", "B"]),
    }
    for invoiceIndex, (invoiceNo, (customerId, stockCodes)) in enumerate(baskets.items(), start=1):
        for productIndex, stockCode in enumerate(stockCodes, start=1):
            rows.append(
                {
                    "invoiceNo": invoiceNo,
                    "customerId": customerId,
                    "invoiceTs": pd.Timestamp("2024-01-01") + pd.Timedelta(invoiceIndex, unit="D"),
                    "stockCode": stockCode,
                    "productName": f"Product {stockCode}",
                    "itemQuantity": productIndex,
                    "itemAmount": float(productIndex * 10),
                }
            )
    return pd.DataFrame(rows)


def testGenerateSyntheticTransactionsIsTraceableAndPositive() -> None:
    sourceTransactions = buildSourceTransactions()
    customerSegments = pd.DataFrame(
        [
            {"customerId": "C1", "segmentCode": "CHAMPIONS"},
            {"customerId": "C2", "segmentCode": "LOYAL"},
            {"customerId": "C3", "segmentCode": "LOYAL"},
        ]
    )
    config = AugmentationConfig(
        targetRowCount=10_000,
        syntheticCustomerCount=10,
        topAnchorCount=4,
        relationshipProductLimit=4,
        minimumPairBasketCount=1,
        randomSeed=42,
        generationBatchId="TEST-BATCH",
    )

    syntheticFrame, qualityReport = generateSyntheticTransactions(
        sourceTransactions,
        customerSegments,
        config,
    )

    assert len(syntheticFrame) == 10_000
    assert syntheticFrame["syntheticLineId"].is_unique
    assert syntheticFrame["invoiceNo"].str.startswith("SYN-TEST-BATCH").all()
    assert syntheticFrame["itemQuantity"].gt(0).all()
    assert syntheticFrame["itemAmount"].gt(0).all()
    assert syntheticFrame["generationConfidence"].between(0.58, 0.98).all()
    assert syntheticFrame.groupby("invoiceNo")["stockCode"].nunique().ge(2).all()
    assert qualityReport["allAmountsPositive"] is True
    assert qualityReport["relationshipAnchorCoverage"] == 1.0


def testBuildAugmentedTransactionsRetainsExplicitOrigins() -> None:
    sourceTransactions = buildSourceTransactions()
    syntheticFrame = pd.DataFrame(
        [
            {
                "syntheticLineId": "B-0001",
                "invoiceNo": "SYN-B-1",
                "customerId": "C1",
                "invoiceTs": pd.Timestamp("2024-02-01"),
                "stockCode": "A",
                "productName": "Product A",
                "itemQuantity": 2,
                "itemAmount": 20.0,
                "sourceSegmentCode": "CHAMPIONS",
                "generationConfidence": 0.9,
                "generationModel": "testModel",
                "generationBatchId": "B",
            }
        ]
    )

    augmentedFrame = buildAugmentedTransactions(sourceTransactions, syntheticFrame, "B")

    assert set(augmentedFrame["dataOrigin"]) == {"REAL", "MODEL_GENERATED"}
    assert augmentedFrame.iloc[-1]["generationBatchId"] == "B"
