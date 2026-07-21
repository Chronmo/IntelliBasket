"""Global, segmented, and time-comparative market basket mining."""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth

from intellibasket.analytics.models import BasketMiningConfig

NON_MERCHANDISE_CODES = {
    "ADJUST",
    "BANK CHARGES",
    "C2",
    "D",
    "DCGS0003",
    "DOT",
    "M",
    "POST",
    "S",
    "TEST001",
    "TEST002",
}

RULE_COLUMNS = [
    "ruleId",
    "segmentCode",
    "segmentName",
    "antecedentCodes",
    "antecedentNames",
    "consequentCodes",
    "consequentNames",
    "support",
    "confidence",
    "lift",
    "leverage",
    "conviction",
    "coverageBasketCount",
    "scopeBasketCount",
    "rankScore",
]


def prepareBasketItems(
    transactions: pd.DataFrame,
    minBasketSize: int,
) -> pd.DataFrame:
    """Remove service codes and baskets that cannot form an association."""
    basketItems = transactions.loc[
        ~transactions["stockCode"].str.upper().isin(NON_MERCHANDISE_CODES),
        ["invoiceNo", "customerId", "stockCode", "productName"],
    ].drop_duplicates(["invoiceNo", "stockCode"])
    basketSizes = basketItems.groupby("invoiceNo")["stockCode"].nunique()
    eligibleInvoices = basketSizes.loc[basketSizes.ge(minBasketSize)].index
    return basketItems.loc[basketItems["invoiceNo"].isin(eligibleInvoices)].copy()


def buildProductCatalog(basketItems: pd.DataFrame) -> dict[str, str]:
    """Build a stable code-to-name map for rule explanations."""
    catalogFrame = (
        basketItems.assign(productName=basketItems["productName"].fillna("未知商品"))
        .sort_values(["stockCode", "productName"])
        .drop_duplicates("stockCode", keep="last")
    )
    return dict(zip(catalogFrame["stockCode"], catalogFrame["productName"], strict=True))


def formatItemset(itemset: frozenset[str], separator: str = "|") -> str:
    """Serialize an itemset deterministically for APIs and CSV files."""
    return separator.join(sorted(str(item) for item in itemset))


def formatItemNames(itemset: frozenset[str], productCatalog: dict[str, str]) -> str:
    """Serialize human-readable names in the same order as product codes."""
    return "|".join(productCatalog.get(code, code) for code in sorted(itemset))


def buildRuleId(segmentCode: str, antecedentCodes: str, consequentCodes: str) -> str:
    """Build a stable identifier for rule comparison and API lookup."""
    rawIdentifier = f"{segmentCode}:{antecedentCodes}>{consequentCodes}"
    return hashlib.sha1(rawIdentifier.encode("utf-8")).hexdigest()[:16]


def mineScopeRules(
    basketItems: pd.DataFrame,
    segmentCode: str,
    segmentName: str,
    minSupport: float,
    config: BasketMiningConfig,
) -> pd.DataFrame:
    """Mine association rules for one global or customer-segment scope."""
    scopeBasketCount = basketItems["invoiceNo"].nunique()
    if scopeBasketCount < 2:
        return pd.DataFrame(columns=RULE_COLUMNS)

    productSupport = (
        basketItems.groupby("stockCode")["invoiceNo"].nunique().sort_values(ascending=False)
    )
    minimumCoverage = max(2, math.ceil(scopeBasketCount * minSupport))
    eligibleProducts = productSupport.loc[productSupport.ge(minimumCoverage)].head(
        config.maxProducts
    )
    scopedItems = basketItems.loc[basketItems["stockCode"].isin(eligibleProducts.index)].copy()
    filteredBasketSizes = scopedItems.groupby("invoiceNo")["stockCode"].nunique()
    scopedItems = scopedItems.loc[
        scopedItems["invoiceNo"].isin(filteredBasketSizes.loc[filteredBasketSizes.ge(2)].index)
    ]
    scopeBasketCount = scopedItems["invoiceNo"].nunique()
    if scopeBasketCount < 2 or scopedItems["stockCode"].nunique() < 2:
        return pd.DataFrame(columns=RULE_COLUMNS)

    basketMatrix = pd.crosstab(scopedItems["invoiceNo"], scopedItems["stockCode"]).astype(bool)
    frequentItemsets = fpgrowth(
        basketMatrix,
        min_support=minSupport,
        use_colnames=True,
        max_len=config.maxItemsetLength,
    )
    if frequentItemsets.empty:
        return pd.DataFrame(columns=RULE_COLUMNS)
    with np.errstate(divide="ignore", invalid="ignore"):
        rawRules = association_rules(
            frequentItemsets,
            metric="confidence",
            min_threshold=config.minConfidence,
        )
    rawRules = rawRules.loc[rawRules["lift"].ge(config.minLift)].copy()
    if rawRules.empty:
        return pd.DataFrame(columns=RULE_COLUMNS)

    productCatalog = buildProductCatalog(scopedItems)
    rawRules["segmentCode"] = segmentCode
    rawRules["segmentName"] = segmentName
    rawRules["antecedentCodes"] = rawRules["antecedents"].map(formatItemset)
    rawRules["antecedentNames"] = rawRules["antecedents"].map(
        lambda itemset: formatItemNames(itemset, productCatalog)
    )
    rawRules["consequentCodes"] = rawRules["consequents"].map(formatItemset)
    rawRules["consequentNames"] = rawRules["consequents"].map(
        lambda itemset: formatItemNames(itemset, productCatalog)
    )
    rawRules["coverageBasketCount"] = np.rint(rawRules["support"] * scopeBasketCount).astype(int)
    rawRules["scopeBasketCount"] = scopeBasketCount
    rawRules["rankScore"] = (
        rawRules["lift"] * rawRules["confidence"] * np.log1p(rawRules["coverageBasketCount"])
    )
    rawRules["ruleId"] = [
        buildRuleId(segmentCode, antecedentCodes, consequentCodes)
        for antecedentCodes, consequentCodes in zip(
            rawRules["antecedentCodes"], rawRules["consequentCodes"], strict=True
        )
    ]
    rawRules = rawRules.sort_values(
        ["rankScore", "lift", "coverageBasketCount"], ascending=False
    ).head(config.topRulesPerScope)
    numericColumns = ["support", "confidence", "lift", "leverage", "conviction", "rankScore"]
    rawRules[numericColumns] = rawRules[numericColumns].replace([np.inf, -np.inf], np.nan)
    rawRules[numericColumns] = rawRules[numericColumns].round(6)
    return rawRules[RULE_COLUMNS].reset_index(drop=True)


def mineAssociationRules(
    transactions: pd.DataFrame,
    customerSegments: pd.DataFrame | None,
    config: BasketMiningConfig,
) -> pd.DataFrame:
    """Mine global rules and, when supplied, separate rules for every RFM segment."""
    basketItems = prepareBasketItems(transactions, config.minBasketSize)
    ruleFrames = [
        mineScopeRules(
            basketItems,
            segmentCode="ALL",
            segmentName="全部客户",
            minSupport=config.globalMinSupport,
            config=config,
        )
    ]
    if customerSegments is not None and not customerSegments.empty:
        segmentColumns = customerSegments[
            ["customerId", "segmentCode", "segmentName"]
        ].drop_duplicates("customerId")
        segmentedItems = basketItems.merge(segmentColumns, on="customerId", how="inner")
        for (segmentCode, segmentName), segmentItems in segmentedItems.groupby(
            ["segmentCode", "segmentName"]
        ):
            if segmentItems["invoiceNo"].nunique() < config.minSegmentBaskets:
                continue
            ruleFrames.append(
                mineScopeRules(
                    segmentItems,
                    segmentCode=str(segmentCode),
                    segmentName=str(segmentName),
                    minSupport=config.segmentMinSupport,
                    config=config,
                )
            )
    nonemptyFrames = [ruleFrame for ruleFrame in ruleFrames if not ruleFrame.empty]
    if not nonemptyFrames:
        return pd.DataFrame(columns=RULE_COLUMNS)
    return pd.concat(nonemptyFrames, ignore_index=True)


def calculateRuleDrift(
    previousRules: pd.DataFrame,
    currentRules: pd.DataFrame,
    stableThreshold: float = 0.1,
) -> pd.DataFrame:
    """Compare rule strength across two periods and classify relationship drift."""
    keyColumns = ["segmentCode", "antecedentCodes", "consequentCodes"]
    metricColumns = ["support", "confidence", "lift", "coverageBasketCount"]
    previousFrame = previousRules[keyColumns + metricColumns].rename(
        columns={
            columnName: f"previous{columnName[0].upper()}{columnName[1:]}"
            for columnName in metricColumns
        }
    )
    currentFrame = currentRules[
        keyColumns + ["segmentName", "antecedentNames", "consequentNames"] + metricColumns
    ].rename(
        columns={
            columnName: f"current{columnName[0].upper()}{columnName[1:]}"
            for columnName in metricColumns
        }
    )
    driftFrame = previousFrame.merge(currentFrame, on=keyColumns, how="outer")
    driftFrame["liftDelta"] = driftFrame["currentLift"] - driftFrame["previousLift"]
    driftFrame["supportDelta"] = driftFrame["currentSupport"] - driftFrame["previousSupport"]

    def classifyRule(row: pd.Series) -> str:
        if pd.isna(row["previousLift"]):
            return "NEW"
        if pd.isna(row["currentLift"]):
            return "DROPPED"
        if row["liftDelta"] > stableThreshold:
            return "GROWING"
        if row["liftDelta"] < -stableThreshold:
            return "DECLINING"
        return "STABLE"

    driftFrame["driftStatus"] = driftFrame.apply(classifyRule, axis=1)
    return driftFrame.sort_values(
        ["driftStatus", "currentLift"], ascending=[True, False], na_position="last"
    ).reset_index(drop=True)
