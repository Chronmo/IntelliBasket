"""Relational serving models mapped from analytical outputs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from intellibasket.serving.database import Base


class BusinessOverviewRecord(Base):
    __tablename__ = "business_overview"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customerCount: Mapped[int] = mapped_column("customer_count", Integer)
    orderCount: Mapped[int] = mapped_column("order_count", Integer)
    productCount: Mapped[int] = mapped_column("product_count", Integer)
    itemQuantity: Mapped[int] = mapped_column("item_quantity", Integer)
    salesAmount: Mapped[Decimal] = mapped_column("sales_amount", Numeric(20, 2))
    averageBasketAmount: Mapped[Decimal] = mapped_column("average_basket_amount", Numeric(20, 2))
    minInvoiceTs: Mapped[datetime] = mapped_column("min_invoice_ts", DateTime)
    maxInvoiceTs: Mapped[datetime] = mapped_column("max_invoice_ts", DateTime)


class MonthlySaleRecord(Base):
    __tablename__ = "monthly_sale"

    invoiceMonth: Mapped[str] = mapped_column("invoice_month", String(7), primary_key=True)
    customerCount: Mapped[int] = mapped_column("customer_count", Integer)
    orderCount: Mapped[int] = mapped_column("order_count", Integer)
    productCount: Mapped[int] = mapped_column("product_count", Integer)
    itemQuantity: Mapped[int] = mapped_column("item_quantity", Integer)
    salesAmount: Mapped[Decimal] = mapped_column("sales_amount", Numeric(20, 2))
    averageBasketAmount: Mapped[Decimal] = mapped_column("average_basket_amount", Numeric(20, 2))


class RfmCustomerSnapshotRecord(Base):
    __tablename__ = "rfm_customer_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "customer_id", name="uq_rfm_snapshot_customer"),
        Index("ix_rfm_snapshot_segment", "snapshot_date", "segment_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshotDate: Mapped[date] = mapped_column("snapshot_date", Date)
    customerId: Mapped[str] = mapped_column("customer_id", String(32))
    latestPurchaseTs: Mapped[datetime] = mapped_column("latest_purchase_ts", DateTime)
    recencyDays: Mapped[int] = mapped_column("recency_days", Integer)
    frequency: Mapped[int] = mapped_column(Integer)
    monetary: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    rScore: Mapped[int] = mapped_column("r_score", Integer)
    fScore: Mapped[int] = mapped_column("f_score", Integer)
    mScore: Mapped[int] = mapped_column("m_score", Integer)
    rfmScore: Mapped[str] = mapped_column("rfm_score", String(8))
    segmentCode: Mapped[str] = mapped_column("segment_code", String(32))
    segmentName: Mapped[str] = mapped_column("segment_name", String(64))


class RfmSegmentSummaryRecord(Base):
    __tablename__ = "rfm_segment_summary"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "segment_code", name="uq_rfm_summary_segment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshotDate: Mapped[date] = mapped_column("snapshot_date", Date)
    segmentCode: Mapped[str] = mapped_column("segment_code", String(32))
    segmentName: Mapped[str] = mapped_column("segment_name", String(64))
    customerCount: Mapped[int] = mapped_column("customer_count", Integer)
    totalMonetary: Mapped[Decimal] = mapped_column("total_monetary", Numeric(20, 2))
    averageRecencyDays: Mapped[Decimal] = mapped_column("average_recency_days", Numeric(12, 2))
    averageFrequency: Mapped[Decimal] = mapped_column("average_frequency", Numeric(12, 2))
    averageMonetary: Mapped[Decimal] = mapped_column("average_monetary", Numeric(20, 2))
    customerShare: Mapped[Decimal] = mapped_column("customer_share", Numeric(12, 6))
    monetaryShare: Mapped[Decimal] = mapped_column("monetary_share", Numeric(12, 6))


class SegmentMigrationRecord(Base):
    __tablename__ = "segment_migration"
    __table_args__ = (
        Index("ix_segment_migration_dates", "from_snapshot_date", "to_snapshot_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fromSegmentCode: Mapped[str] = mapped_column("from_segment_code", String(32))
    fromSegmentName: Mapped[str] = mapped_column("from_segment_name", String(64))
    toSegmentCode: Mapped[str] = mapped_column("to_segment_code", String(32))
    toSegmentName: Mapped[str] = mapped_column("to_segment_name", String(64))
    customerCount: Mapped[int] = mapped_column("customer_count", Integer)
    fromSnapshotDate: Mapped[date] = mapped_column("from_snapshot_date", Date)
    toSnapshotDate: Mapped[date] = mapped_column("to_snapshot_date", Date)


class AssociationRuleRecord(Base):
    __tablename__ = "association_rule"
    __table_args__ = (
        Index("ix_rule_segment_rank", "segment_code", "rank_score"),
        Index("ix_rule_lift", "lift"),
    )

    ruleId: Mapped[str] = mapped_column("rule_id", String(40), primary_key=True)
    segmentCode: Mapped[str] = mapped_column("segment_code", String(32))
    segmentName: Mapped[str] = mapped_column("segment_name", String(64))
    antecedentCodes: Mapped[str] = mapped_column("antecedent_codes", Text)
    antecedentNames: Mapped[str] = mapped_column("antecedent_names", Text)
    consequentCodes: Mapped[str] = mapped_column("consequent_codes", Text)
    consequentNames: Mapped[str] = mapped_column("consequent_names", Text)
    support: Mapped[Decimal] = mapped_column(Numeric(14, 8))
    confidence: Mapped[Decimal] = mapped_column(Numeric(14, 8))
    lift: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    leverage: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    conviction: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    coverageBasketCount: Mapped[int] = mapped_column("coverage_basket_count", Integer)
    scopeBasketCount: Mapped[int] = mapped_column("scope_basket_count", Integer)
    rankScore: Mapped[Decimal] = mapped_column("rank_score", Numeric(18, 8))


class RuleDriftRecord(Base):
    __tablename__ = "rule_drift"
    __table_args__ = (Index("ix_rule_drift_status", "drift_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    segmentCode: Mapped[str] = mapped_column("segment_code", String(32))
    segmentName: Mapped[str | None] = mapped_column("segment_name", String(64), nullable=True)
    antecedentCodes: Mapped[str] = mapped_column("antecedent_codes", Text)
    antecedentNames: Mapped[str | None] = mapped_column("antecedent_names", Text, nullable=True)
    consequentCodes: Mapped[str] = mapped_column("consequent_codes", Text)
    consequentNames: Mapped[str | None] = mapped_column("consequent_names", Text, nullable=True)
    previousSupport: Mapped[Decimal | None] = mapped_column(
        "previous_support", Numeric(14, 8), nullable=True
    )
    previousConfidence: Mapped[Decimal | None] = mapped_column(
        "previous_confidence", Numeric(14, 8), nullable=True
    )
    previousLift: Mapped[Decimal | None] = mapped_column(
        "previous_lift", Numeric(18, 8), nullable=True
    )
    previousCoverageBasketCount: Mapped[int | None] = mapped_column(
        "previous_coverage_basket_count", Integer, nullable=True
    )
    currentSupport: Mapped[Decimal | None] = mapped_column(
        "current_support", Numeric(14, 8), nullable=True
    )
    currentConfidence: Mapped[Decimal | None] = mapped_column(
        "current_confidence", Numeric(14, 8), nullable=True
    )
    currentLift: Mapped[Decimal | None] = mapped_column(
        "current_lift", Numeric(18, 8), nullable=True
    )
    currentCoverageBasketCount: Mapped[int | None] = mapped_column(
        "current_coverage_basket_count", Integer, nullable=True
    )
    liftDelta: Mapped[Decimal | None] = mapped_column("lift_delta", Numeric(18, 8), nullable=True)
    supportDelta: Mapped[Decimal | None] = mapped_column(
        "support_delta", Numeric(14, 8), nullable=True
    )
    driftStatus: Mapped[str] = mapped_column("drift_status", String(16))


class TopProductRecord(Base):
    __tablename__ = "top_product"

    stockCode: Mapped[str] = mapped_column("stock_code", String(64), primary_key=True)
    # Historical Online Retail II rows occasionally reuse a stock code with a
    # changed description, so product identity in this aggregate is composite.
    productName: Mapped[str] = mapped_column("product_name", String(512), primary_key=True)
    orderCount: Mapped[int] = mapped_column("order_count", Integer)
    customerCount: Mapped[int] = mapped_column("customer_count", Integer)
    itemQuantity: Mapped[int] = mapped_column("item_quantity", Integer)
    salesAmount: Mapped[Decimal] = mapped_column("sales_amount", Numeric(20, 2))


class SyntheticTransactionRecord(Base):
    """Traceable model-generated transaction line kept separate from source facts."""

    __tablename__ = "synthetic_transaction"
    __table_args__ = (
        Index("ix_synthetic_batch", "generation_batch_id"),
        Index("ix_synthetic_customer", "customer_id"),
        Index("ix_synthetic_invoice", "invoice_no"),
        Index("ix_synthetic_stock_segment", "stock_code", "source_segment_code"),
    )

    syntheticLineId: Mapped[str] = mapped_column("synthetic_line_id", String(64), primary_key=True)
    invoiceNo: Mapped[str] = mapped_column("invoice_no", String(128))
    customerId: Mapped[str] = mapped_column("customer_id", String(32))
    invoiceTs: Mapped[datetime] = mapped_column("invoice_ts", DateTime)
    stockCode: Mapped[str] = mapped_column("stock_code", String(64))
    productName: Mapped[str] = mapped_column("product_name", String(512))
    itemQuantity: Mapped[int] = mapped_column("item_quantity", Integer)
    itemAmount: Mapped[Decimal] = mapped_column("item_amount", Numeric(20, 4))
    sourceSegmentCode: Mapped[str] = mapped_column("source_segment_code", String(32))
    generationConfidence: Mapped[Decimal] = mapped_column("generation_confidence", Numeric(10, 6))
    generationModel: Mapped[str] = mapped_column("generation_model", String(64))
    generationBatchId: Mapped[str] = mapped_column("generation_batch_id", String(64))
