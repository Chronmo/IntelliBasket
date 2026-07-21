"""Read-only query repository for dashboard and recommendation endpoints."""

from __future__ import annotations

import hashlib
import math
from datetime import date

from sqlalchemy import Select, func, literal, or_, select
from sqlalchemy.orm import Session

from intellibasket.serving.models import (
    AssociationRuleRecord,
    BusinessOverviewRecord,
    MonthlySaleRecord,
    RfmCustomerSnapshotRecord,
    RfmSegmentSummaryRecord,
    RuleDriftRecord,
    SegmentMigrationRecord,
    SyntheticTransactionRecord,
    TopProductRecord,
)


class AnalyticsRepository:
    """Encapsulate all read-only serving queries."""

    def __init__(self, databaseSession: Session) -> None:
        self._databaseSession = databaseSession

    def getOverview(self) -> BusinessOverviewRecord | None:
        return self._databaseSession.scalar(select(BusinessOverviewRecord).limit(1))

    def getMonthlySales(self) -> list[MonthlySaleRecord]:
        return list(
            self._databaseSession.scalars(
                select(MonthlySaleRecord).order_by(MonthlySaleRecord.invoiceMonth)
            )
        )

    def getLatestSnapshotDate(self) -> date | None:
        return self._databaseSession.scalar(select(func.max(RfmSegmentSummaryRecord.snapshotDate)))

    def getSegments(self, snapshotDate: date | None) -> list[RfmSegmentSummaryRecord]:
        effectiveDate = snapshotDate or self.getLatestSnapshotDate()
        if effectiveDate is None:
            return []
        return list(
            self._databaseSession.scalars(
                select(RfmSegmentSummaryRecord)
                .where(RfmSegmentSummaryRecord.snapshotDate == effectiveDate)
                .order_by(RfmSegmentSummaryRecord.totalMonetary.desc())
            )
        )

    def getCustomers(
        self,
        snapshotDate: date | None,
        segmentCode: str | None,
        page: int,
        pageSize: int,
    ) -> tuple[list[RfmCustomerSnapshotRecord], int, date | None]:
        effectiveDate = snapshotDate or self.getLatestSnapshotDate()
        if effectiveDate is None:
            return [], 0, None
        conditions = [RfmCustomerSnapshotRecord.snapshotDate == effectiveDate]
        if segmentCode:
            conditions.append(RfmCustomerSnapshotRecord.segmentCode == segmentCode)
        countStatement = (
            select(func.count()).select_from(RfmCustomerSnapshotRecord).where(*conditions)
        )
        totalCount = int(self._databaseSession.scalar(countStatement) or 0)
        statement = (
            select(RfmCustomerSnapshotRecord)
            .where(*conditions)
            .order_by(RfmCustomerSnapshotRecord.monetary.desc())
            .offset((page - 1) * pageSize)
            .limit(pageSize)
        )
        return list(self._databaseSession.scalars(statement)), totalCount, effectiveDate

    def getMigrations(
        self,
        fromSnapshotDate: date | None,
        toSnapshotDate: date | None,
    ) -> list[SegmentMigrationRecord]:
        statement: Select[tuple[SegmentMigrationRecord]] = select(SegmentMigrationRecord)
        if fromSnapshotDate:
            statement = statement.where(SegmentMigrationRecord.fromSnapshotDate == fromSnapshotDate)
        if toSnapshotDate:
            statement = statement.where(SegmentMigrationRecord.toSnapshotDate == toSnapshotDate)
        return list(
            self._databaseSession.scalars(
                statement.order_by(SegmentMigrationRecord.customerCount.desc()).limit(500)
            )
        )

    def getRules(
        self,
        segmentCode: str,
        minLift: float,
        minConfidence: float,
        productCode: str | None,
        limit: int,
    ) -> list[AssociationRuleRecord]:
        statement = select(AssociationRuleRecord).where(
            AssociationRuleRecord.segmentCode == segmentCode,
            AssociationRuleRecord.lift >= minLift,
            AssociationRuleRecord.confidence >= minConfidence,
        )
        if productCode:
            productPattern = f"%|{productCode}|%"
            statement = statement.where(
                or_(
                    (literal("|") + AssociationRuleRecord.antecedentCodes + literal("|")).like(
                        productPattern
                    ),
                    (literal("|") + AssociationRuleRecord.consequentCodes + literal("|")).like(
                        productPattern
                    ),
                )
            )
        return list(
            self._databaseSession.scalars(
                statement.order_by(AssociationRuleRecord.rankScore.desc()).limit(limit)
            )
        )

    def getRuleDrift(self, driftStatus: str | None, limit: int) -> list[RuleDriftRecord]:
        statement = select(RuleDriftRecord)
        if driftStatus:
            statement = statement.where(RuleDriftRecord.driftStatus == driftStatus)
        return list(
            self._databaseSession.scalars(
                statement.order_by(RuleDriftRecord.currentLift.desc()).limit(limit)
            )
        )

    def getTopProducts(self, limit: int) -> list[TopProductRecord]:
        return list(
            self._databaseSession.scalars(
                select(TopProductRecord).order_by(TopProductRecord.salesAmount.desc()).limit(limit)
            )
        )

    def getAugmentationSummary(self) -> dict[str, object]:
        """Summarize model-generated rows without mixing them into source provenance."""
        summary = self._databaseSession.execute(
            select(
                func.count(SyntheticTransactionRecord.syntheticLineId),
                func.count(func.distinct(SyntheticTransactionRecord.invoiceNo)),
                func.count(func.distinct(SyntheticTransactionRecord.customerId)),
                func.sum(SyntheticTransactionRecord.itemAmount),
                func.avg(SyntheticTransactionRecord.generationConfidence),
                func.min(SyntheticTransactionRecord.invoiceTs),
                func.max(SyntheticTransactionRecord.invoiceTs),
                func.max(SyntheticTransactionRecord.generationBatchId),
                func.max(SyntheticTransactionRecord.generationModel),
            )
        ).one()
        syntheticRowCount = int(summary[0] or 0)
        return {
            "enabled": syntheticRowCount > 0,
            "syntheticRowCount": syntheticRowCount,
            "syntheticOrderCount": int(summary[1] or 0),
            "syntheticCustomerCount": int(summary[2] or 0),
            "predictedSalesAmount": round(float(summary[3] or 0), 2),
            "averageConfidence": round(float(summary[4] or 0), 6),
            "forecastStart": summary[5].isoformat() if summary[5] else None,
            "forecastEnd": summary[6].isoformat() if summary[6] else None,
            "generationBatchId": summary[7],
            "generationModel": summary[8],
        }

    def getSyntheticCompanionPredictions(
        self,
        productCode: str,
        segmentCode: str,
        minLift: float,
        limit: int,
    ) -> list[dict[str, object]]:
        """Predict companions from the isolated model-generated transaction table."""
        segmentConditions = []
        if segmentCode != "ALL":
            segmentConditions.append(SyntheticTransactionRecord.sourceSegmentCode == segmentCode)
        anchorInvoices = (
            select(SyntheticTransactionRecord.invoiceNo)
            .where(
                SyntheticTransactionRecord.stockCode == productCode,
                *segmentConditions,
            )
            .distinct()
            .subquery()
        )
        anchorBasketCount = int(
            self._databaseSession.scalar(select(func.count()).select_from(anchorInvoices)) or 0
        )
        totalBasketCount = int(
            self._databaseSession.scalar(
                select(func.count(func.distinct(SyntheticTransactionRecord.invoiceNo))).where(
                    *segmentConditions
                )
            )
            or 0
        )
        if anchorBasketCount == 0 or totalBasketCount == 0:
            return []

        companionCoverage = (
            select(
                SyntheticTransactionRecord.stockCode.label("stockCode"),
                SyntheticTransactionRecord.productName.label("productName"),
                func.count(func.distinct(SyntheticTransactionRecord.invoiceNo)).label(
                    "basketCount"
                ),
            )
            .where(*segmentConditions)
            .group_by(
                SyntheticTransactionRecord.stockCode,
                SyntheticTransactionRecord.productName,
            )
            .subquery()
        )
        pairCoverage = (
            select(
                SyntheticTransactionRecord.stockCode.label("stockCode"),
                SyntheticTransactionRecord.productName.label("productName"),
                func.count(func.distinct(SyntheticTransactionRecord.invoiceNo)).label(
                    "pairBasketCount"
                ),
            )
            .where(
                SyntheticTransactionRecord.invoiceNo.in_(select(anchorInvoices.c.invoiceNo)),
                SyntheticTransactionRecord.stockCode != productCode,
                *segmentConditions,
            )
            .group_by(
                SyntheticTransactionRecord.stockCode,
                SyntheticTransactionRecord.productName,
            )
            .subquery()
        )
        rows = self._databaseSession.execute(
            select(
                pairCoverage.c.stockCode,
                pairCoverage.c.productName,
                pairCoverage.c.pairBasketCount,
                companionCoverage.c.basketCount,
            )
            .join(
                companionCoverage,
                (pairCoverage.c.stockCode == companionCoverage.c.stockCode)
                & (pairCoverage.c.productName == companionCoverage.c.productName),
            )
            .order_by(pairCoverage.c.pairBasketCount.desc())
            .limit(max(limit * 5, 20))
        ).all()
        anchorName = self._databaseSession.scalar(
            select(func.max(SyntheticTransactionRecord.productName)).where(
                SyntheticTransactionRecord.stockCode == productCode
            )
        )
        predictions: list[dict[str, object]] = []
        minimumPredictionCoverage = max(2, math.ceil(totalBasketCount * 0.002))
        for row in rows:
            pairBasketCount = int(row[2])
            confidence = pairBasketCount / anchorBasketCount
            support = pairBasketCount / totalBasketCount
            companionProbability = int(row[3]) / totalBasketCount
            lift = confidence / companionProbability if companionProbability else 0
            if lift < minLift or confidence < 0.25 or pairBasketCount < minimumPredictionCoverage:
                continue
            ruleId = hashlib.sha1(
                f"MODEL:{segmentCode}:{productCode}>{row[0]}".encode()
            ).hexdigest()[:16]
            predictions.append(
                {
                    "ruleId": ruleId,
                    "segmentCode": segmentCode,
                    "segmentName": "模型预测场景",
                    "antecedentCodes": productCode,
                    "antecedentNames": anchorName or productCode,
                    "consequentCodes": str(row[0]),
                    "consequentNames": str(row[1]),
                    "support": round(support, 6),
                    "confidence": round(confidence, 6),
                    "lift": round(lift, 6),
                    "coverageBasketCount": pairBasketCount,
                    "scopeBasketCount": totalBasketCount,
                    "rankScore": round(confidence * lift * math.log1p(pairBasketCount), 6),
                    "strategy": "预测组合",
                    "reason": (
                        f"模型增强场景置信度{confidence:.1%}，提升度{lift:.2f}，"
                        f"覆盖{pairBasketCount}张预测购物篮"
                    ),
                    "dataBasis": "MODEL_PREDICTION",
                    "sourceType": "MODEL_PREDICTION",
                }
            )
            if len(predictions) >= limit:
                break
        return predictions
