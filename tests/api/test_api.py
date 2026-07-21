from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from intellibasket.api.app import createApp
from intellibasket.serving.database import initializeDatabase
from intellibasket.serving.models import (
    AssociationRuleRecord,
    BusinessOverviewRecord,
    MonthlySaleRecord,
    RfmCustomerSnapshotRecord,
    RfmSegmentSummaryRecord,
    TopProductRecord,
)


def buildTestClient() -> TestClient:
    databaseEngine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    initializeDatabase(databaseEngine)
    with Session(databaseEngine) as databaseSession:
        databaseSession.add(
            BusinessOverviewRecord(
                customerCount=100,
                orderCount=250,
                productCount=80,
                itemQuantity=1200,
                salesAmount=Decimal("50000.00"),
                averageBasketAmount=Decimal("200.00"),
                minInvoiceTs=datetime(2010, 1, 1, 9, 0),
                maxInvoiceTs=datetime(2011, 1, 1, 9, 0),
            )
        )
        databaseSession.add(
            MonthlySaleRecord(
                invoiceMonth="2011-01",
                customerCount=100,
                orderCount=250,
                productCount=80,
                itemQuantity=1200,
                salesAmount=Decimal("50000.00"),
                averageBasketAmount=Decimal("200.00"),
            )
        )
        databaseSession.add(
            RfmSegmentSummaryRecord(
                snapshotDate=date(2011, 1, 2),
                segmentCode="CHAMPIONS",
                segmentName="重要价值客户",
                customerCount=20,
                totalMonetary=Decimal("30000.00"),
                averageRecencyDays=Decimal("3.00"),
                averageFrequency=Decimal("8.00"),
                averageMonetary=Decimal("1500.00"),
                customerShare=Decimal("0.200000"),
                monetaryShare=Decimal("0.600000"),
            )
        )
        databaseSession.add(
            RfmCustomerSnapshotRecord(
                snapshotDate=date(2011, 1, 2),
                customerId="C001",
                latestPurchaseTs=datetime(2011, 1, 1, 8, 0),
                recencyDays=1,
                frequency=10,
                monetary=Decimal("2000.00"),
                rScore=5,
                fScore=5,
                mScore=5,
                rfmScore="555",
                segmentCode="CHAMPIONS",
                segmentName="重要价值客户",
            )
        )
        databaseSession.add(
            AssociationRuleRecord(
                ruleId="rule000000000001",
                segmentCode="CHAMPIONS",
                segmentName="重要价值客户",
                antecedentCodes="A",
                antecedentNames="Product A",
                consequentCodes="B",
                consequentNames="Product B",
                support=Decimal("0.20"),
                confidence=Decimal("0.80"),
                lift=Decimal("2.50"),
                leverage=Decimal("0.10"),
                conviction=Decimal("3.00"),
                coverageBasketCount=50,
                scopeBasketCount=250,
                rankScore=Decimal("10.00"),
            )
        )
        databaseSession.add(
            TopProductRecord(
                stockCode="A",
                productName="Product A",
                orderCount=100,
                customerCount=80,
                itemQuantity=200,
                salesAmount=Decimal("5000.00"),
            )
        )
        databaseSession.add(
            TopProductRecord(
                stockCode="A",
                productName="Product A (renamed)",
                orderCount=10,
                customerCount=8,
                itemQuantity=20,
                salesAmount=Decimal("500.00"),
            )
        )
        databaseSession.commit()
    return TestClient(createApp(databaseEngine=databaseEngine))


def testHealthAndOverviewUseStandardEnvelope() -> None:
    with buildTestClient() as testClient:
        healthResponse = testClient.get("/api/v1/health/ready")
        overviewResponse = testClient.get("/api/v1/overview")

    assert healthResponse.status_code == 200
    assert healthResponse.json()["data"]["status"] == "READY"
    assert overviewResponse.status_code == 200
    assert overviewResponse.json()["success"] is True
    assert overviewResponse.json()["data"]["salesAmount"] == 50000.0
    assert overviewResponse.headers["X-Request-Id"]


def testRfmCustomerPaginationReturnsMetadata() -> None:
    with buildTestClient() as testClient:
        response = testClient.get(
            "/api/v1/rfm/customers",
            params={"segmentCode": "CHAMPIONS", "page": 1, "pageSize": 20},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"][0]["customerId"] == "C001"
    assert payload["meta"]["totalCount"] == 1
    assert payload["meta"]["snapshotDate"] == "2011-01-02"


def testMarketingRecommendationExplainsMatchedRule() -> None:
    with buildTestClient() as testClient:
        response = testClient.post(
            "/api/v1/marketing-recommendations",
            json={
                "segmentCode": "CHAMPIONS",
                "productCode": "A",
                "minLift": 1.05,
                "limit": 5,
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"][0]["consequentCodes"] == "B"
    assert payload["data"][0]["strategy"] == "组合折扣"
    assert "覆盖50张购物篮" in payload["data"][0]["reason"]


def testValidationFailureUsesStandardErrorEnvelope() -> None:
    with buildTestClient() as testClient:
        response = testClient.get("/api/v1/rfm/customers", params={"pageSize": 1000})

    payload = response.json()
    assert response.status_code == 422
    assert payload["success"] is False
    assert payload["error"]["code"] == "REQUEST_VALIDATION_FAILED"
