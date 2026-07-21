from __future__ import annotations

import pandas as pd

from intellibasket.analytics.models import RfmConfig
from intellibasket.analytics.rfm import calculateRfm, summarizeSegments


def buildRfmTransactions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for customerIndex in range(1, 11):
        for orderIndex in range(customerIndex):
            rows.append(
                {
                    "customerId": f"C{customerIndex:02d}",
                    "invoiceNo": f"I{customerIndex:02d}-{orderIndex:02d}",
                    "invoiceTs": pd.Timestamp("2021-01-01")
                    + pd.Timedelta(customerIndex * 8 + orderIndex, unit="D"),
                    "stockCode": "A",
                    "productName": "Product A",
                    "itemQuantity": 1,
                    "itemAmount": float(customerIndex * 10),
                }
            )
    return pd.DataFrame(rows)


def testCalculateRfmCreatesScoresAndSegments() -> None:
    rfmFrame = calculateRfm(
        buildRfmTransactions(),
        snapshotDate=pd.Timestamp("2021-05-01"),
        config=RfmConfig(),
    )

    assert len(rfmFrame) == 10
    assert set(rfmFrame["rScore"]) == {1, 2, 3, 4, 5}
    assert set(rfmFrame["fScore"]) == {1, 2, 3, 4, 5}
    assert rfmFrame.loc[rfmFrame["customerId"].eq("C10"), "mScore"].iloc[0] == 5
    assert rfmFrame["segmentName"].notna().all()


def testSummarizeSegmentsReconcilesCustomersAndMonetary() -> None:
    rfmFrame = calculateRfm(
        buildRfmTransactions(),
        snapshotDate=pd.Timestamp("2021-05-01"),
        config=RfmConfig(),
    )
    segmentSummary = summarizeSegments(rfmFrame)

    assert segmentSummary["customerCount"].sum() == 10
    assert round(segmentSummary["customerShare"].sum(), 6) == 1.0
    assert round(segmentSummary["totalMonetary"].sum(), 2) == round(rfmFrame["monetary"].sum(), 2)
