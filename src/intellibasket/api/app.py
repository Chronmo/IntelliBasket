"""FastAPI application factory and versioned dashboard endpoints."""

from __future__ import annotations

import math
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from intellibasket.api.repository import AnalyticsRepository
from intellibasket.api.schemas import (
    MarketingRecommendationRequest,
    buildSuccessResponse,
    serializeRecord,
)
from intellibasket.config import ProjectSettings
from intellibasket.serving.database import (
    buildEngine,
    buildSessionFactory,
    initializeDatabase,
)

OVERVIEW_FIELDS = [
    "customerCount",
    "orderCount",
    "productCount",
    "itemQuantity",
    "salesAmount",
    "averageBasketAmount",
    "minInvoiceTs",
    "maxInvoiceTs",
]
MONTHLY_FIELDS = [
    "invoiceMonth",
    "customerCount",
    "orderCount",
    "productCount",
    "itemQuantity",
    "salesAmount",
    "averageBasketAmount",
]
SEGMENT_FIELDS = [
    "snapshotDate",
    "segmentCode",
    "segmentName",
    "customerCount",
    "totalMonetary",
    "averageRecencyDays",
    "averageFrequency",
    "averageMonetary",
    "customerShare",
    "monetaryShare",
]
CUSTOMER_FIELDS = [
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
RULE_FIELDS = [
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
    "coverageBasketCount",
    "scopeBasketCount",
    "rankScore",
]


def getDatabaseSession(request: Request) -> Iterator[Session]:
    """Provide one database session per request."""
    databaseSession = request.app.state.sessionFactory()
    try:
        yield databaseSession
    finally:
        databaseSession.close()


DatabaseSession = Annotated[Session, Depends(getDatabaseSession)]


def buildErrorResponse(
    request: Request,
    statusCode: int,
    errorCode: str,
    message: str,
    details: list[Any] | None = None,
) -> JSONResponse:
    """Build the standard Problem Details-inspired error envelope."""
    return JSONResponse(
        status_code=statusCode,
        content={
            "success": False,
            "error": {
                "code": errorCode,
                "message": message,
                "details": details or [],
            },
            "meta": {"requestId": request.state.requestId},
        },
    )


def createApp(
    settings: ProjectSettings | None = None,
    databaseEngine: Engine | None = None,
) -> FastAPI:
    """Create an IntelliBasket API instance for production or tests."""
    effectiveSettings = settings or ProjectSettings.fromEnvironment()
    engine = databaseEngine or buildEngine(effectiveSettings.mysqlUrl)
    sessionFactory = buildSessionFactory(engine)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        initializeDatabase(engine)
        application.state.engine = engine
        application.state.sessionFactory = sessionFactory
        yield

    application = FastAPI(
        title="IntelliBasket API",
        version="1.0.0",
        description="RFM customer intelligence and segmented market basket API",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(effectiveSettings.allowedOrigins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-Id"],
    )

    @application.middleware("http")
    async def addRequestId(request: Request, callNext: Any) -> Any:
        request.state.requestId = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        response = await callNext(request)
        response.headers["X-Request-Id"] = request.state.requestId
        return response

    @application.exception_handler(RequestValidationError)
    async def handleValidationError(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return buildErrorResponse(
            request,
            422,
            "REQUEST_VALIDATION_FAILED",
            "Request parameters are invalid",
            error.errors(),
        )

    @application.get("/api/v1/health/live")
    def getLiveness(request: Request) -> dict[str, Any]:
        return buildSuccessResponse(request, {"status": "UP"})

    @application.get("/api/v1/health/ready")
    def getReadiness(request: Request, databaseSession: DatabaseSession) -> Any:
        try:
            databaseSession.execute(text("SELECT 1"))
        except Exception:
            return buildErrorResponse(
                request, 503, "DATABASE_UNAVAILABLE", "Serving database is unavailable"
            )
        return buildSuccessResponse(request, {"status": "READY"})

    @application.get("/api/v1/overview")
    def getOverview(request: Request, databaseSession: DatabaseSession) -> Any:
        overview = AnalyticsRepository(databaseSession).getOverview()
        if overview is None:
            return buildErrorResponse(
                request, 404, "OVERVIEW_NOT_FOUND", "Business overview has not been loaded"
            )
        return buildSuccessResponse(request, serializeRecord(overview, OVERVIEW_FIELDS))

    @application.get("/api/v1/sales/monthly")
    def getMonthlySales(request: Request, databaseSession: DatabaseSession) -> Any:
        records = AnalyticsRepository(databaseSession).getMonthlySales()
        return buildSuccessResponse(
            request, [serializeRecord(record, MONTHLY_FIELDS) for record in records]
        )

    @application.get("/api/v1/rfm/segments")
    def getRfmSegments(
        request: Request,
        databaseSession: DatabaseSession,
        snapshotDate: date | None = None,
    ) -> Any:
        records = AnalyticsRepository(databaseSession).getSegments(snapshotDate)
        return buildSuccessResponse(
            request, [serializeRecord(record, SEGMENT_FIELDS) for record in records]
        )

    @application.get("/api/v1/rfm/customers")
    def getRfmCustomers(
        request: Request,
        databaseSession: DatabaseSession,
        snapshotDate: date | None = None,
        segmentCode: str | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> Any:
        records, totalCount, effectiveDate = AnalyticsRepository(databaseSession).getCustomers(
            snapshotDate, segmentCode, page, pageSize
        )
        return buildSuccessResponse(
            request,
            [serializeRecord(record, CUSTOMER_FIELDS) for record in records],
            page=page,
            pageSize=pageSize,
            totalCount=totalCount,
            totalPages=math.ceil(totalCount / pageSize) if totalCount else 0,
            snapshotDate=effectiveDate.isoformat() if effectiveDate else None,
        )

    @application.get("/api/v1/rfm/migrations")
    def getRfmMigrations(
        request: Request,
        databaseSession: DatabaseSession,
        fromSnapshotDate: date | None = None,
        toSnapshotDate: date | None = None,
    ) -> Any:
        fields = [
            "fromSegmentCode",
            "fromSegmentName",
            "toSegmentCode",
            "toSegmentName",
            "customerCount",
            "fromSnapshotDate",
            "toSnapshotDate",
        ]
        records = AnalyticsRepository(databaseSession).getMigrations(
            fromSnapshotDate, toSnapshotDate
        )
        return buildSuccessResponse(
            request, [serializeRecord(record, fields) for record in records]
        )

    @application.get("/api/v1/association-rules")
    def getAssociationRules(
        request: Request,
        databaseSession: DatabaseSession,
        segmentCode: str = "ALL",
        minLift: Annotated[float, Query(ge=0)] = 1.05,
        minConfidence: Annotated[float, Query(ge=0, le=1)] = 0.25,
        productCode: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> Any:
        records = AnalyticsRepository(databaseSession).getRules(
            segmentCode, minLift, minConfidence, productCode, limit
        )
        return buildSuccessResponse(
            request, [serializeRecord(record, RULE_FIELDS) for record in records]
        )

    @application.get("/api/v1/rule-drift")
    def getRuleDrift(
        request: Request,
        databaseSession: DatabaseSession,
        driftStatus: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
    ) -> Any:
        fields = [
            "segmentCode",
            "segmentName",
            "antecedentCodes",
            "antecedentNames",
            "consequentCodes",
            "consequentNames",
            "previousSupport",
            "previousConfidence",
            "previousLift",
            "currentSupport",
            "currentConfidence",
            "currentLift",
            "liftDelta",
            "supportDelta",
            "driftStatus",
        ]
        records = AnalyticsRepository(databaseSession).getRuleDrift(driftStatus, limit)
        return buildSuccessResponse(
            request, [serializeRecord(record, fields) for record in records]
        )

    @application.get("/api/v1/products/top")
    def getTopProducts(
        request: Request,
        databaseSession: DatabaseSession,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> Any:
        fields = [
            "stockCode",
            "productName",
            "orderCount",
            "customerCount",
            "itemQuantity",
            "salesAmount",
        ]
        records = AnalyticsRepository(databaseSession).getTopProducts(limit)
        return buildSuccessResponse(
            request, [serializeRecord(record, fields) for record in records]
        )

    @application.get("/api/v1/data-augmentation/summary")
    def getAugmentationSummary(
        request: Request,
        databaseSession: DatabaseSession,
    ) -> Any:
        summary = AnalyticsRepository(databaseSession).getAugmentationSummary()
        return buildSuccessResponse(request, summary)

    @application.post("/api/v1/marketing-recommendations")
    def getMarketingRecommendations(
        request: Request,
        recommendationRequest: MarketingRecommendationRequest,
        databaseSession: DatabaseSession,
    ) -> Any:
        candidateRules = AnalyticsRepository(databaseSession).getRules(
            recommendationRequest.segmentCode,
            recommendationRequest.minLift,
            0,
            recommendationRequest.productCode,
            200,
        )
        matchedRules = [
            rule
            for rule in candidateRules
            if recommendationRequest.productCode in rule.antecedentCodes.split("|")
        ][: recommendationRequest.limit]
        recommendations = [
            {
                **serializeRecord(rule, RULE_FIELDS),
                "strategy": "组合折扣" if float(rule.lift) >= 2 else "交叉销售",
                "reason": (
                    f"历史置信度{float(rule.confidence):.1%}，"
                    f"提升度{float(rule.lift):.2f}，覆盖{rule.coverageBasketCount}张购物篮"
                ),
                "dataBasis": "REAL_AND_MODEL_AUGMENTED",
            }
            for rule in matchedRules
        ]
        return buildSuccessResponse(request, recommendations)

    return application


app = createApp()
