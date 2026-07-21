"""Dynamic RFM scoring, segmentation, and migration analysis."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from intellibasket.analytics.models import RfmConfig

SEGMENT_NAMES = {
    "CHAMPIONS": "重要价值客户",
    "LOYAL": "重要保持客户",
    "POTENTIAL": "重要发展客户",
    "NEW": "新客户",
    "AT_RISK": "重要挽留客户",
    "HIBERNATING": "流失风险客户",
    "PROMISING": "潜力客户",
    "GENERAL": "一般客户",
}


def scoreSeries(
    values: pd.Series,
    scoreBins: int,
    higherIsBetter: bool,
) -> pd.Series:
    """Assign deterministic quantile scores while handling tied values."""
    if values.empty:
        return pd.Series(dtype="int64", index=values.index)
    effectiveBins = max(1, min(scoreBins, len(values)))
    rankedValues = values.rank(method="first", ascending=True)
    rawScores = pd.qcut(
        rankedValues,
        q=effectiveBins,
        labels=list(range(1, effectiveBins + 1)),
    ).astype(int)
    if higherIsBetter:
        return rawScores
    return effectiveBins + 1 - rawScores


def assignSegmentCode(rScore: int, fScore: int, mScore: int) -> str:
    """Map RFM scores to an actionable customer segment."""
    fmScore = (fScore + mScore) / 2
    if rScore >= 4 and fmScore >= 4:
        return "CHAMPIONS"
    if rScore >= 3 and fmScore >= 3:
        return "LOYAL"
    if rScore >= 4 and fmScore >= 2:
        return "POTENTIAL"
    if rScore >= 4 and fmScore < 2:
        return "NEW"
    if rScore <= 2 and fmScore >= 4:
        return "AT_RISK"
    if rScore <= 2 and fmScore >= 2:
        return "HIBERNATING"
    if rScore >= 3:
        return "PROMISING"
    return "GENERAL"


def calculateRfm(
    transactions: pd.DataFrame,
    snapshotDate: pd.Timestamp,
    config: RfmConfig,
    observationStart: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Calculate customer RFM values and segment membership for one snapshot."""
    normalizedSnapshot = pd.Timestamp(snapshotDate).normalize()
    inclusiveEnd = normalizedSnapshot + pd.Timedelta(1, unit="D")
    eligibleTransactions = transactions.loc[transactions["invoiceTs"].lt(inclusiveEnd)].copy()
    if observationStart is not None:
        eligibleTransactions = eligibleTransactions.loc[
            eligibleTransactions["invoiceTs"].ge(pd.Timestamp(observationStart))
        ]
    if eligibleTransactions.empty:
        return pd.DataFrame()

    rfmFrame = (
        eligibleTransactions.groupby("customerId", as_index=False)
        .agg(
            latestPurchaseTs=("invoiceTs", "max"),
            frequency=("invoiceNo", "nunique"),
            monetary=("itemAmount", "sum"),
        )
        .sort_values("customerId")
        .reset_index(drop=True)
    )
    rfmFrame["snapshotDate"] = normalizedSnapshot
    rfmFrame["recencyDays"] = (
        normalizedSnapshot - rfmFrame["latestPurchaseTs"].dt.normalize()
    ).dt.days
    rfmFrame["rScore"] = scoreSeries(
        rfmFrame["recencyDays"], config.scoreBins, higherIsBetter=False
    )
    rfmFrame["fScore"] = scoreSeries(rfmFrame["frequency"], config.scoreBins, higherIsBetter=True)
    rfmFrame["mScore"] = scoreSeries(rfmFrame["monetary"], config.scoreBins, higherIsBetter=True)
    rfmFrame["rfmScore"] = (
        rfmFrame["rScore"].astype(str)
        + rfmFrame["fScore"].astype(str)
        + rfmFrame["mScore"].astype(str)
    )
    rfmFrame["segmentCode"] = [
        assignSegmentCode(rScore, fScore, mScore)
        for rScore, fScore, mScore in zip(
            rfmFrame["rScore"],
            rfmFrame["fScore"],
            rfmFrame["mScore"],
            strict=True,
        )
    ]
    rfmFrame["segmentName"] = rfmFrame["segmentCode"].map(SEGMENT_NAMES)
    rfmFrame["monetary"] = rfmFrame["monetary"].round(2)
    return rfmFrame[
        [
            "snapshotDate",
            "customerId",
            "latestPurchaseTs",
            "recencyDays",
            "frequency",
            "monetary",
            "rScore",
            "fScore",
            "mScore",
            "rfmScore",
            "segmentCode",
            "segmentName",
        ]
    ]


def buildSnapshotDates(
    transactions: pd.DataFrame,
    config: RfmConfig,
) -> list[pd.Timestamp]:
    """Build month-end snapshot dates after the configured history period."""
    minDate = transactions["invoiceTs"].min().normalize()
    maxDate = transactions["invoiceTs"].max().normalize()
    firstEligibleDate = minDate + pd.Timedelta(config.minimumHistoryDays, unit="D")
    snapshotDates = list(
        pd.date_range(
            firstEligibleDate,
            maxDate,
            freq=config.snapshotFrequency,
        )
    )
    finalSnapshotDate = maxDate + pd.Timedelta(1, unit="D")
    if not snapshotDates or snapshotDates[-1].normalize() != finalSnapshotDate.normalize():
        snapshotDates.append(finalSnapshotDate)
    return snapshotDates


def calculateMonthlySnapshots(
    transactions: pd.DataFrame,
    config: RfmConfig,
) -> pd.DataFrame:
    """Calculate RFM membership for every month-end snapshot."""
    snapshotFrames = [
        calculateRfm(transactions, snapshotDate, config)
        for snapshotDate in buildSnapshotDates(transactions, config)
    ]
    nonemptyFrames = [snapshotFrame for snapshotFrame in snapshotFrames if not snapshotFrame.empty]
    if not nonemptyFrames:
        return pd.DataFrame()
    return pd.concat(nonemptyFrames, ignore_index=True)


def summarizeSegments(rfmFrame: pd.DataFrame) -> pd.DataFrame:
    """Summarize customer scale and monetary contribution by segment."""
    if rfmFrame.empty:
        return pd.DataFrame()
    segmentSummary = (
        rfmFrame.groupby(["snapshotDate", "segmentCode", "segmentName"], as_index=False)
        .agg(
            customerCount=("customerId", "nunique"),
            totalMonetary=("monetary", "sum"),
            averageRecencyDays=("recencyDays", "mean"),
            averageFrequency=("frequency", "mean"),
            averageMonetary=("monetary", "mean"),
        )
        .sort_values(["snapshotDate", "totalMonetary"], ascending=[True, False])
    )
    snapshotCustomerTotals = segmentSummary.groupby("snapshotDate")["customerCount"].transform(
        "sum"
    )
    snapshotMonetaryTotals = segmentSummary.groupby("snapshotDate")["totalMonetary"].transform(
        "sum"
    )
    segmentSummary["customerShare"] = (
        segmentSummary["customerCount"] / snapshotCustomerTotals
    ).round(6)
    segmentSummary["monetaryShare"] = (
        segmentSummary["totalMonetary"] / snapshotMonetaryTotals
    ).round(6)
    numericColumns: Iterable[str] = (
        "totalMonetary",
        "averageRecencyDays",
        "averageFrequency",
        "averageMonetary",
    )
    segmentSummary[list(numericColumns)] = segmentSummary[list(numericColumns)].round(2)
    return segmentSummary


def calculateSegmentMigrations(snapshotFrame: pd.DataFrame) -> pd.DataFrame:
    """Count customer movements between consecutive snapshots."""
    if snapshotFrame.empty:
        return pd.DataFrame()
    orderedSnapshots = sorted(snapshotFrame["snapshotDate"].drop_duplicates())
    migrationFrames: list[pd.DataFrame] = []
    for previousDate, currentDate in zip(orderedSnapshots[:-1], orderedSnapshots[1:], strict=True):
        previousFrame = snapshotFrame.loc[
            snapshotFrame["snapshotDate"].eq(previousDate),
            ["customerId", "segmentCode", "segmentName"],
        ].rename(
            columns={
                "segmentCode": "fromSegmentCode",
                "segmentName": "fromSegmentName",
            }
        )
        currentFrame = snapshotFrame.loc[
            snapshotFrame["snapshotDate"].eq(currentDate),
            ["customerId", "segmentCode", "segmentName"],
        ].rename(
            columns={
                "segmentCode": "toSegmentCode",
                "segmentName": "toSegmentName",
            }
        )
        mergedFrame = previousFrame.merge(currentFrame, on="customerId", how="inner")
        migrationFrame = (
            mergedFrame.groupby(
                [
                    "fromSegmentCode",
                    "fromSegmentName",
                    "toSegmentCode",
                    "toSegmentName",
                ],
                as_index=False,
            )
            .agg(customerCount=("customerId", "nunique"))
            .assign(fromSnapshotDate=previousDate, toSnapshotDate=currentDate)
        )
        migrationFrames.append(migrationFrame)
    if not migrationFrames:
        return pd.DataFrame()
    return pd.concat(migrationFrames, ignore_index=True)
