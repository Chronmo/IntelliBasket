from __future__ import annotations

import pandas as pd

from intellibasket.analytics.basket import calculateRuleDrift, mineAssociationRules
from intellibasket.analytics.models import BasketMiningConfig


def buildBasketTransactions() -> pd.DataFrame:
    basketProducts = {
        "I1": ["A", "B"],
        "I2": ["A", "B"],
        "I3": ["A", "B", "C"],
        "I4": ["A", "B"],
        "I5": ["A", "C"],
        "I6": ["C", "D"],
    }
    rows: list[dict[str, object]] = []
    for basketIndex, (invoiceNo, stockCodes) in enumerate(basketProducts.items(), start=1):
        for stockCode in stockCodes:
            rows.append(
                {
                    "invoiceNo": invoiceNo,
                    "customerId": f"C{basketIndex}",
                    "invoiceTs": pd.Timestamp("2021-01-01") + pd.Timedelta(basketIndex, unit="D"),
                    "stockCode": stockCode,
                    "productName": f"Product {stockCode}",
                    "itemQuantity": 1,
                    "itemAmount": 10.0,
                }
            )
    return pd.DataFrame(rows)


def buildBasketConfig() -> BasketMiningConfig:
    return BasketMiningConfig(
        globalMinSupport=0.2,
        segmentMinSupport=0.2,
        minConfidence=0.5,
        minLift=0.9,
        minBasketSize=2,
        minSegmentBaskets=2,
        maxProducts=20,
        maxItemsetLength=2,
        topRulesPerScope=20,
    )


def testMineAssociationRulesFindsFrequentPair() -> None:
    rules = mineAssociationRules(
        buildBasketTransactions(),
        customerSegments=None,
        config=buildBasketConfig(),
    )

    assert not rules.empty
    assert (rules["antecedentCodes"].eq("A") & rules["consequentCodes"].eq("B")).any()
    assert rules["ruleId"].str.len().eq(16).all()


def testCalculateRuleDriftClassifiesNewAndGrowingRules() -> None:
    previousRules = pd.DataFrame(
        [
            {
                "segmentCode": "ALL",
                "antecedentCodes": "A",
                "consequentCodes": "B",
                "support": 0.2,
                "confidence": 0.5,
                "lift": 1.1,
                "coverageBasketCount": 20,
            }
        ]
    )
    currentRules = pd.DataFrame(
        [
            {
                "segmentCode": "ALL",
                "segmentName": "全部客户",
                "antecedentCodes": "A",
                "antecedentNames": "Product A",
                "consequentCodes": "B",
                "consequentNames": "Product B",
                "support": 0.3,
                "confidence": 0.7,
                "lift": 1.4,
                "coverageBasketCount": 30,
            },
            {
                "segmentCode": "ALL",
                "segmentName": "全部客户",
                "antecedentCodes": "C",
                "antecedentNames": "Product C",
                "consequentCodes": "D",
                "consequentNames": "Product D",
                "support": 0.1,
                "confidence": 0.6,
                "lift": 1.3,
                "coverageBasketCount": 10,
            },
        ]
    )

    driftFrame = calculateRuleDrift(previousRules, currentRules)

    assert set(driftFrame["driftStatus"]) == {"GROWING", "NEW"}
