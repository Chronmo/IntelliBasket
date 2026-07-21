"""Command-line entry points for repeatable project jobs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from intellibasket.config import ProjectSettings
from intellibasket.data.ingestion import convertWorkbook, writeIngestionProfile


def buildParser() -> argparse.ArgumentParser:
    """Create the root command parser."""
    argumentParser = argparse.ArgumentParser(
        prog="intellibasket",
        description="IntelliBasket data and analytics command line",
    )
    subparsers = argumentParser.add_subparsers(dest="command", required=True)

    prepareParser = subparsers.add_parser(
        "prepare-data", help="Convert Online Retail II into standardized CSV"
    )
    prepareParser.add_argument("--source", type=Path)
    prepareParser.add_argument("--output", type=Path)
    prepareParser.add_argument("--profile", type=Path)
    prepareParser.add_argument("--batch-id")

    analyticsParser = subparsers.add_parser(
        "run-analytics", help="Run dynamic RFM and segmented basket analytics"
    )
    analyticsParser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/hive/basket_items.tsv"),
    )
    analyticsParser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics"),
    )
    analyticsParser.add_argument("--config", type=Path)

    augmentationParser = subparsers.add_parser(
        "augment-data",
        help="Generate traceable customer-product-amount scenario transactions",
    )
    augmentationParser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/hive/basket_items.tsv"),
    )
    augmentationParser.add_argument(
        "--segments",
        type=Path,
        default=Path("outputs/analytics/rfmCustomers.csv"),
    )
    augmentationParser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/hive/basket_items_augmented.tsv"),
    )
    augmentationParser.add_argument(
        "--synthetic-output",
        type=Path,
        default=Path("outputs/augmentation/syntheticTransactions.csv"),
    )
    augmentationParser.add_argument(
        "--manifest",
        type=Path,
        default=Path("outputs/augmentation/manifest.json"),
    )
    augmentationParser.add_argument("--target-rows", type=int, default=60_000)
    augmentationParser.add_argument("--synthetic-customers", type=int, default=600)
    augmentationParser.add_argument("--seed", type=int, default=20_260_721)
    augmentationParser.add_argument(
        "--batch-id",
        default="AUG-20260721-01",
    )

    loadParser = subparsers.add_parser(
        "load-serving-data", help="Load analytical outputs into MySQL"
    )
    loadParser.add_argument(
        "--input",
        type=Path,
        default=Path("outputs/analytics"),
    )
    loadParser.add_argument("--database-url")
    loadParser.add_argument(
        "--augmentation-input",
        type=Path,
        default=Path("outputs/augmentation"),
    )

    serveParser = subparsers.add_parser("serve", help="Run the IntelliBasket API")
    serveParser.add_argument("--host")
    serveParser.add_argument("--port", type=int)
    return argumentParser


def runPrepareData(arguments: argparse.Namespace) -> int:
    """Execute the source conversion command."""
    projectSettings = ProjectSettings.fromEnvironment()
    sourcePath = (arguments.source or projectSettings.sourceWorkbook).resolve()
    outputPath = (arguments.output or projectSettings.preparedCsv).resolve()
    profilePath = (arguments.profile or projectSettings.profileJson).resolve()
    ingestionStats = convertWorkbook(
        sourcePath=sourcePath,
        outputPath=outputPath,
        ingestBatchId=arguments.batch_id,
    )
    writeIngestionProfile(profilePath, ingestionStats)
    print(ingestionStats.toJson())
    return 0


def main(rawArguments: Sequence[str] | None = None) -> int:
    """Dispatch the selected IntelliBasket command."""
    argumentParser = buildParser()
    arguments = argumentParser.parse_args(rawArguments)
    if arguments.command == "prepare-data":
        return runPrepareData(arguments)
    if arguments.command == "run-analytics":
        from intellibasket.analytics.models import AnalyticsConfig
        from intellibasket.analytics.pipeline import AnalyticsPipeline

        analyticsConfig = AnalyticsConfig.fromToml(arguments.config)
        manifest = AnalyticsPipeline(analyticsConfig).run(
            inputPath=arguments.input.resolve(),
            outputDirectory=arguments.output.resolve(),
        )
        import json

        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    if arguments.command == "augment-data":
        import json

        import pandas as pd

        from intellibasket.analytics.augmentation import (
            AugmentationConfig,
            runAugmentation,
        )
        from intellibasket.analytics.pipeline import loadHiveBasketItems

        sourceTransactions = loadHiveBasketItems(arguments.input.resolve())
        customerSegments = pd.read_csv(
            arguments.segments.resolve(),
            dtype={"customerId": "string"},
        )
        manifest = runAugmentation(
            sourceTransactions=sourceTransactions,
            customerSegments=customerSegments,
            outputPath=arguments.output.resolve(),
            syntheticOutputPath=arguments.synthetic_output.resolve(),
            manifestPath=arguments.manifest.resolve(),
            config=AugmentationConfig(
                targetRowCount=arguments.target_rows,
                syntheticCustomerCount=arguments.synthetic_customers,
                randomSeed=arguments.seed,
                generationBatchId=arguments.batch_id,
            ),
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    if arguments.command == "load-serving-data":
        import json

        from intellibasket.serving.database import (
            buildEngine,
            buildSessionFactory,
            initializeDatabase,
        )
        from intellibasket.serving.import_service import ServingDataImporter

        projectSettings = ProjectSettings.fromEnvironment()
        databaseUrl = arguments.database_url or projectSettings.mysqlUrl
        databaseEngine = buildEngine(databaseUrl)
        initializeDatabase(databaseEngine)
        importedCounts = ServingDataImporter(buildSessionFactory(databaseEngine)).importDirectory(
            arguments.input.resolve(),
            arguments.augmentation_input.resolve(),
        )
        print(json.dumps(importedCounts, ensure_ascii=False, indent=2))
        return 0
    if arguments.command == "serve":
        import uvicorn

        projectSettings = ProjectSettings.fromEnvironment()
        uvicorn.run(
            "intellibasket.api.app:app",
            host=arguments.host or projectSettings.apiHost,
            port=arguments.port or projectSettings.apiPort,
            reload=False,
        )
        return 0
    argumentParser.error(f"Unsupported command: {arguments.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
