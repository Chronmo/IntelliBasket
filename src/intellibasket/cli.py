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
    argumentParser.error(f"Unsupported command: {arguments.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
