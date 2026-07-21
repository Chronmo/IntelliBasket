"""Traceable customer-product-amount prediction for scenario data augmentation."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SYNTHETIC_MODEL_NAME = "segmentAwareCooccurrenceV1"
AUGMENTED_COLUMNS = [
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
SYNTHETIC_OUTPUT_COLUMNS = [
    "syntheticLineId",
    "invoiceNo",
    "customerId",
    "invoiceTs",
    "stockCode",
    "productName",
    "itemQuantity",
    "itemAmount",
    "sourceSegmentCode",
    "generationConfidence",
    "generationModel",
    "generationBatchId",
]


@dataclass(frozen=True, slots=True)
class AugmentationConfig:
    """Controls deterministic scenario generation from observed relationships."""

    targetRowCount: int = 60_000
    syntheticCustomerCount: int = 600
    topAnchorCount: int = 100
    relationshipProductLimit: int = 350
    maxProductsPerSourceBasket: int = 20
    minimumPairBasketCount: int = 4
    minimumBasketSize: int = 3
    maximumBasketSize: int = 6
    forecastMonths: int = 6
    randomSeed: int = 20_260_721
    generationBatchId: str = "AUG-20260721-01"

    def validate(self) -> None:
        if self.targetRowCount < 10_000:
            raise ValueError("targetRowCount must be at least 10,000")
        if self.minimumBasketSize < 2:
            raise ValueError("minimumBasketSize must be at least 2")
        if self.maximumBasketSize < self.minimumBasketSize:
            raise ValueError("maximumBasketSize must not be smaller than minimumBasketSize")


@dataclass(frozen=True, slots=True)
class ProductRelation:
    """Directed product relationship estimated from observed basket co-occurrence."""

    companionCode: str
    pairBasketCount: int
    confidence: float
    lift: float
    score: float
    generationConfidence: float


def normalizeTransactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Keep positive, attributable transaction values required by the generator."""
    normalized = transactions.copy()
    normalized["invoiceTs"] = pd.to_datetime(normalized["invoiceTs"], errors="coerce")
    normalized["itemQuantity"] = pd.to_numeric(normalized["itemQuantity"], errors="coerce")
    normalized["itemAmount"] = pd.to_numeric(normalized["itemAmount"], errors="coerce")
    normalized = normalized.dropna(
        subset=["invoiceNo", "customerId", "invoiceTs", "stockCode", "itemQuantity", "itemAmount"]
    )
    return normalized.loc[normalized["itemQuantity"].gt(0) & normalized["itemAmount"].gt(0)].copy()


def buildProductProfiles(transactions: pd.DataFrame) -> pd.DataFrame:
    """Estimate stable names, unit prices, quantities, sales, and basket coverage."""
    pricedItems = transactions.assign(
        unitPrice=transactions["itemAmount"] / transactions["itemQuantity"]
    )

    def mostFrequentName(names: pd.Series) -> str:
        modes = names.dropna().astype(str).mode()
        return modes.iat[0] if not modes.empty else "UNKNOWN PRODUCT"

    profiles = (
        pricedItems.groupby("stockCode", as_index=False)
        .agg(
            productName=("productName", mostFrequentName),
            medianUnitPrice=("unitPrice", "median"),
            medianQuantity=("itemQuantity", "median"),
            basketCount=("invoiceNo", "nunique"),
            salesAmount=("itemAmount", "sum"),
        )
        .loc[lambda frame: frame["medianUnitPrice"].gt(0)]
        .sort_values(["salesAmount", "basketCount"], ascending=False)
        .reset_index(drop=True)
    )
    profiles["medianQuantity"] = profiles["medianQuantity"].clip(1, 72)
    return profiles


def buildRelationshipGraph(
    transactions: pd.DataFrame,
    productProfiles: pd.DataFrame,
    config: AugmentationConfig,
) -> dict[str, list[ProductRelation]]:
    """Calculate directed confidence and lift for popular-product co-occurrences."""
    eligibleCodes = set(
        productProfiles.head(config.relationshipProductLimit)["stockCode"].astype(str)
    )
    popularityRank = {
        str(code): rank
        for rank, code in enumerate(productProfiles["stockCode"].astype(str), start=1)
    }
    basketProducts = (
        transactions.loc[transactions["stockCode"].astype(str).isin(eligibleCodes)]
        .drop_duplicates(["invoiceNo", "stockCode"])
        .groupby("invoiceNo")["stockCode"]
        .agg(list)
    )
    pairCounts: Counter[tuple[str, str]] = Counter()
    productBasketCounts: Counter[str] = Counter()
    for rawCodes in basketProducts:
        uniqueCodes = sorted(
            {str(code) for code in rawCodes},
            key=lambda code: popularityRank.get(code, math.inf),
        )[: config.maxProductsPerSourceBasket]
        productBasketCounts.update(uniqueCodes)
        pairCounts.update(combinations(sorted(uniqueCodes), 2))

    sourceBasketCount = int(transactions["invoiceNo"].nunique())
    relationshipGraph: dict[str, list[ProductRelation]] = defaultdict(list)
    for (leftCode, rightCode), pairBasketCount in pairCounts.items():
        if pairBasketCount < config.minimumPairBasketCount:
            continue
        for anchorCode, companionCode in ((leftCode, rightCode), (rightCode, leftCode)):
            anchorCount = productBasketCounts[anchorCode]
            companionCount = productBasketCounts[companionCode]
            confidence = pairBasketCount / anchorCount
            lift = pairBasketCount * sourceBasketCount / (anchorCount * companionCount)
            score = confidence * math.log1p(max(lift, 0)) * math.log1p(pairBasketCount)
            generationConfidence = float(
                np.clip(
                    0.52
                    + min(confidence, 1) * 0.2
                    + min(math.log1p(max(lift, 0)) / math.log(6), 1) * 0.13
                    + min(pairBasketCount / 150, 1) * 0.13,
                    0.58,
                    0.98,
                )
            )
            relationshipGraph[anchorCode].append(
                ProductRelation(
                    companionCode=companionCode,
                    pairBasketCount=pairBasketCount,
                    confidence=confidence,
                    lift=lift,
                    score=score,
                    generationConfidence=generationConfidence,
                )
            )
    for anchorCode in relationshipGraph:
        relationshipGraph[anchorCode].sort(key=lambda relation: relation.score, reverse=True)
    return dict(relationshipGraph)


def buildSegmentContext(
    transactions: pd.DataFrame,
    customerSegments: pd.DataFrame,
) -> tuple[
    dict[str, list[str]],
    dict[str, np.ndarray],
    dict[str, list[str]],
    dict[str, tuple[list[str], np.ndarray]],
    dict[str, float],
    dict[str, float],
]:
    """Build segment customer pools, product affinities, and spending baselines."""
    segmentMap = (
        customerSegments[["customerId", "segmentCode"]]
        .drop_duplicates("customerId")
        .assign(customerId=lambda frame: frame["customerId"].astype(str))
    )
    segmentedTransactions = transactions.assign(
        customerId=transactions["customerId"].astype(str),
        stockCode=transactions["stockCode"].astype(str),
    ).merge(segmentMap, on="customerId", how="inner")

    customerOrderCounts = (
        segmentedTransactions.groupby(["segmentCode", "customerId"])["invoiceNo"]
        .nunique()
        .reset_index(name="orderCount")
    )
    customersBySegment: dict[str, list[str]] = {}
    customerWeightsBySegment: dict[str, np.ndarray] = {}
    for segmentCode, segmentCustomers in customerOrderCounts.groupby("segmentCode"):
        customersBySegment[str(segmentCode)] = segmentCustomers["customerId"].tolist()
        weights = np.sqrt(segmentCustomers["orderCount"].to_numpy(dtype=float))
        customerWeightsBySegment[str(segmentCode)] = weights / weights.sum()

    segmentProducts: dict[str, list[str]] = {}
    productCounts = (
        segmentedTransactions.groupby(["segmentCode", "stockCode"])["invoiceNo"]
        .nunique()
        .reset_index(name="basketCount")
        .sort_values(["segmentCode", "basketCount"], ascending=[True, False])
    )
    for segmentCode, products in productCounts.groupby("segmentCode"):
        segmentProducts[str(segmentCode)] = products.head(150)["stockCode"].tolist()

    anchorSegmentChoices: dict[str, tuple[list[str], np.ndarray]] = {}
    anchorSegments = (
        segmentedTransactions.groupby(["stockCode", "segmentCode"])["invoiceNo"]
        .nunique()
        .reset_index(name="basketCount")
    )
    for stockCode, choices in anchorSegments.groupby("stockCode"):
        weights = choices["basketCount"].to_numpy(dtype=float)
        anchorSegmentChoices[str(stockCode)] = (
            choices["segmentCode"].astype(str).tolist(),
            weights / weights.sum(),
        )

    basketAmounts = (
        segmentedTransactions.groupby(["invoiceNo", "customerId", "segmentCode"])["itemAmount"]
        .sum()
        .reset_index(name="basketAmount")
    )
    customerBudget = (
        basketAmounts.groupby("customerId")["basketAmount"].median().astype(float).to_dict()
    )
    segmentBudget = (
        basketAmounts.groupby("segmentCode")["basketAmount"].median().astype(float).to_dict()
    )
    return (
        customersBySegment,
        customerWeightsBySegment,
        segmentProducts,
        anchorSegmentChoices,
        customerBudget,
        segmentBudget,
    )


def buildSyntheticCustomerPools(
    segmentCodes: list[str],
    segmentSizes: dict[str, int],
    syntheticCustomerCount: int,
    rng: np.random.Generator,
) -> dict[str, list[str]]:
    """Assign transparent synthetic customer identifiers to observed segment proportions."""
    sizeWeights = np.array([segmentSizes[segmentCode] for segmentCode in segmentCodes], dtype=float)
    sizeWeights /= sizeWeights.sum()
    assignedSegments = rng.choice(segmentCodes, size=syntheticCustomerCount, p=sizeWeights)
    pools: dict[str, list[str]] = defaultdict(list)
    for customerIndex, segmentCode in enumerate(assignedSegments, start=1):
        pools[str(segmentCode)].append(f"SYN-C{customerIndex:06d}")
    return dict(pools)


def chooseProducts(
    anchorCode: str,
    segmentCode: str,
    basketSize: int,
    relationshipGraph: dict[str, list[ProductRelation]],
    segmentProducts: dict[str, list[str]],
    fallbackProducts: list[str],
    rng: np.random.Generator,
) -> tuple[list[str], float]:
    """Choose one relationship-backed companion, then segment-relevant basket fillers."""
    selectedCodes = [anchorCode]
    relations = relationshipGraph.get(anchorCode, [])
    relationConfidence = 0.58
    if relations:
        primaryRelation = relations[0]
        selectedCodes.append(primaryRelation.companionCode)
        relationConfidence = primaryRelation.generationConfidence

    candidateCodes: list[str] = []
    candidateCodes.extend(relation.companionCode for relation in relations[1:10])
    candidateCodes.extend(segmentProducts.get(segmentCode, []))
    candidateCodes.extend(fallbackProducts)
    candidateCodes = list(dict.fromkeys(candidateCodes))
    candidateCodes = [code for code in candidateCodes if code not in selectedCodes]

    while len(selectedCodes) < basketSize and candidateCodes:
        candidateIndex = int(rng.integers(0, min(len(candidateCodes), 30)))
        selectedCodes.append(candidateCodes.pop(candidateIndex))
    return selectedCodes, relationConfidence


def generateSyntheticTransactions(
    transactions: pd.DataFrame,
    customerSegments: pd.DataFrame,
    config: AugmentationConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Generate traceable future scenario transactions from empirical joint relationships."""
    config.validate()
    sourceTransactions = normalizeTransactions(transactions)
    rng = np.random.default_rng(config.randomSeed)
    productProfiles = buildProductProfiles(sourceTransactions)
    relationshipGraph = buildRelationshipGraph(sourceTransactions, productProfiles, config)
    profileMap = productProfiles.set_index("stockCode").to_dict(orient="index")
    anchorCodes = [
        str(code)
        for code in productProfiles.head(config.topAnchorCount)["stockCode"]
        if str(code) in relationshipGraph
    ]
    if not anchorCodes:
        raise ValueError("No relationship-backed anchor products are available")

    (
        customersBySegment,
        customerWeightsBySegment,
        segmentProducts,
        anchorSegmentChoices,
        customerBudget,
        segmentBudget,
    ) = buildSegmentContext(sourceTransactions, customerSegments)
    segmentCodes = sorted(customersBySegment)
    segmentSizes = {code: len(customersBySegment[code]) for code in segmentCodes}
    syntheticCustomersBySegment = buildSyntheticCustomerPools(
        segmentCodes,
        segmentSizes,
        config.syntheticCustomerCount,
        rng,
    )
    fallbackProducts = productProfiles.head(config.relationshipProductLimit)["stockCode"].tolist()

    maxInvoiceTs = sourceTransactions["invoiceTs"].max()
    forecastStart = maxInvoiceTs.normalize() + pd.Timedelta(1, unit="D")
    forecastEnd = forecastStart + pd.DateOffset(months=config.forecastMonths)
    forecastSeconds = int((forecastEnd - forecastStart).total_seconds())

    generatedRows: list[dict[str, Any]] = []
    generatedInvoiceCount = 0
    while len(generatedRows) < config.targetRowCount:
        anchorCode = anchorCodes[generatedInvoiceCount % len(anchorCodes)]
        segmentChoices = anchorSegmentChoices.get(anchorCode)
        if segmentChoices:
            segmentCode = str(rng.choice(segmentChoices[0], p=segmentChoices[1]))
        else:
            segmentCode = str(rng.choice(segmentCodes))

        useSyntheticCustomer = bool(
            syntheticCustomersBySegment.get(segmentCode) and rng.random() < 0.2
        )
        if useSyntheticCustomer:
            customerId = str(rng.choice(syntheticCustomersBySegment[segmentCode]))
            baseBudget = segmentBudget.get(segmentCode, 100.0)
        else:
            customerId = str(
                rng.choice(
                    customersBySegment[segmentCode],
                    p=customerWeightsBySegment[segmentCode],
                )
            )
            baseBudget = customerBudget.get(customerId, segmentBudget.get(segmentCode, 100.0))

        remainingRows = config.targetRowCount - len(generatedRows)
        desiredBasketSize = int(
            rng.integers(config.minimumBasketSize, config.maximumBasketSize + 1)
        )
        basketSize = min(desiredBasketSize, remainingRows)
        if basketSize < 2 and generatedRows:
            break
        selectedCodes, relationConfidence = chooseProducts(
            anchorCode,
            segmentCode,
            basketSize,
            relationshipGraph,
            segmentProducts,
            fallbackProducts,
            rng,
        )
        if len(selectedCodes) < 2:
            continue

        generatedInvoiceCount += 1
        invoiceNo = f"SYN-{config.generationBatchId}-{generatedInvoiceCount:07d}"
        randomSecond = int(rng.integers(0, max(forecastSeconds, 1)))
        invoiceTs = forecastStart + pd.Timedelta(randomSecond, unit="s")
        invoiceTs = invoiceTs.replace(
            hour=int(rng.integers(8, 19)), minute=int(rng.integers(0, 60))
        )

        targetBudget = float(
            np.clip(
                rng.lognormal(mean=math.log(max(baseBudget, 10)), sigma=0.32),
                8,
                5_000,
            )
        )
        baseQuantities: list[int] = []
        rawAmounts: list[float] = []
        for stockCode in selectedCodes:
            profile = profileMap[stockCode]
            medianQuantity = max(float(profile["medianQuantity"]), 1)
            baseQuantity = int(np.clip(round(medianQuantity * rng.lognormal(0, 0.25)), 1, 72))
            baseQuantities.append(baseQuantity)
            rawAmounts.append(baseQuantity * float(profile["medianUnitPrice"]))
        amountScale = targetBudget / max(sum(rawAmounts), 0.01)

        for stockCode, baseQuantity in zip(selectedCodes, baseQuantities, strict=True):
            profile = profileMap[stockCode]
            quantity = int(np.clip(round(baseQuantity * amountScale), 1, 96))
            itemAmount = round(quantity * float(profile["medianUnitPrice"]), 4)
            syntheticLineId = f"{config.generationBatchId}-{len(generatedRows) + 1:08d}"
            generatedRows.append(
                {
                    "syntheticLineId": syntheticLineId,
                    "invoiceNo": invoiceNo,
                    "customerId": customerId,
                    "invoiceTs": invoiceTs,
                    "stockCode": stockCode,
                    "productName": str(profile["productName"]),
                    "itemQuantity": quantity,
                    "itemAmount": itemAmount,
                    "sourceSegmentCode": segmentCode,
                    "generationConfidence": round(relationConfidence, 6),
                    "generationModel": SYNTHETIC_MODEL_NAME,
                    "generationBatchId": config.generationBatchId,
                }
            )
            if len(generatedRows) >= config.targetRowCount:
                break

    syntheticFrame = pd.DataFrame(generatedRows, columns=SYNTHETIC_OUTPUT_COLUMNS)
    qualityReport = {
        "generationBatchId": config.generationBatchId,
        "generationModel": SYNTHETIC_MODEL_NAME,
        "syntheticRowCount": int(len(syntheticFrame)),
        "syntheticOrderCount": int(syntheticFrame["invoiceNo"].nunique()),
        "syntheticCustomerCount": int(syntheticFrame["customerId"].nunique()),
        "newSyntheticCustomerCount": int(
            syntheticFrame["customerId"].astype(str).str.startswith("SYN-C").sum()
            if syntheticFrame.empty
            else syntheticFrame.loc[
                syntheticFrame["customerId"].astype(str).str.startswith("SYN-C"), "customerId"
            ].nunique()
        ),
        "anchorProductCount": len(anchorCodes),
        "relationshipAnchorCoverage": round(
            len(anchorCodes) / min(config.topAnchorCount, len(productProfiles)), 6
        ),
        "averageGenerationConfidence": round(
            float(syntheticFrame["generationConfidence"].mean()), 6
        ),
        "minimumGenerationConfidence": round(
            float(syntheticFrame["generationConfidence"].min()), 6
        ),
        "salesAmount": round(float(syntheticFrame["itemAmount"].sum()), 2),
        "allAmountsPositive": bool(syntheticFrame["itemAmount"].gt(0).all()),
        "allQuantitiesPositive": bool(syntheticFrame["itemQuantity"].gt(0).all()),
        "forecastStart": syntheticFrame["invoiceTs"].min().isoformat(),
        "forecastEnd": syntheticFrame["invoiceTs"].max().isoformat(),
        "config": asdict(config),
    }
    return syntheticFrame, qualityReport


def buildAugmentedTransactions(
    sourceTransactions: pd.DataFrame,
    syntheticTransactions: pd.DataFrame,
    generationBatchId: str,
) -> pd.DataFrame:
    """Append model-generated rows while retaining explicit origin metadata."""
    realFrame = sourceTransactions.copy()
    realFrame["dataOrigin"] = "REAL"
    realFrame["sourceSegmentCode"] = ""
    realFrame["generationConfidence"] = 1.0
    realFrame["generationBatchId"] = ""
    syntheticFrame = syntheticTransactions.copy()
    syntheticFrame["dataOrigin"] = "MODEL_GENERATED"
    syntheticFrame["generationBatchId"] = generationBatchId
    return pd.concat(
        [realFrame[AUGMENTED_COLUMNS], syntheticFrame[AUGMENTED_COLUMNS]],
        ignore_index=True,
    )


def runAugmentation(
    sourceTransactions: pd.DataFrame,
    customerSegments: pd.DataFrame,
    outputPath: Path,
    syntheticOutputPath: Path,
    manifestPath: Path,
    config: AugmentationConfig,
) -> dict[str, Any]:
    """Generate, persist, and profile an augmented analytical input."""
    syntheticFrame, qualityReport = generateSyntheticTransactions(
        sourceTransactions,
        customerSegments,
        config,
    )
    augmentedFrame = buildAugmentedTransactions(
        normalizeTransactions(sourceTransactions),
        syntheticFrame,
        config.generationBatchId,
    )
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    syntheticOutputPath.parent.mkdir(parents=True, exist_ok=True)
    manifestPath.parent.mkdir(parents=True, exist_ok=True)
    augmentedFrame.to_csv(
        outputPath,
        sep="\t",
        header=False,
        index=False,
        encoding="utf-8",
        date_format="%Y-%m-%d %H:%M:%S",
    )
    syntheticFrame.to_csv(
        syntheticOutputPath,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%d %H:%M:%S",
    )
    manifest = {
        **qualityReport,
        "realRowCount": int(len(sourceTransactions)),
        "augmentedRowCount": int(len(augmentedFrame)),
        "augmentedInputPath": str(outputPath.resolve()),
        "syntheticOutputPath": str(syntheticOutputPath.resolve()),
    }
    manifestPath.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
