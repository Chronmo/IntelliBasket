"""Read-only query repository for dashboard and recommendation endpoints."""

from __future__ import annotations

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
