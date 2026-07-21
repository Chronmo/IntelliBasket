"""Project configuration shared by command-line, analytics, and API modules."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolveProjectPath(rawPath: str) -> Path:
    """Resolve a configured path relative to the project root."""
    candidatePath = Path(rawPath).expanduser()
    if candidatePath.is_absolute():
        return candidatePath.resolve()
    return (PROJECT_ROOT / candidatePath).resolve()


@dataclass(frozen=True, slots=True)
class ProjectSettings:
    """Runtime settings loaded from environment variables."""

    sourceWorkbook: Path
    preparedCsv: Path
    profileJson: Path
    hdfsSourceDir: str
    hiveDatabase: str
    mysqlUrl: str
    apiHost: str
    apiPort: int
    allowedOrigins: tuple[str, ...]

    @classmethod
    def fromEnvironment(cls) -> ProjectSettings:
        """Build settings using safe local-development defaults."""
        allowedOriginsRaw = os.getenv("INTELLIBASKET_ALLOWED_ORIGINS", "http://localhost:5173")
        return cls(
            sourceWorkbook=resolveProjectPath(
                os.getenv(
                    "INTELLIBASKET_SOURCE_WORKBOOK",
                    "../online+retail+ii/online_retail_II.xlsx",
                )
            ),
            preparedCsv=resolveProjectPath(
                os.getenv(
                    "INTELLIBASKET_PREPARED_CSV",
                    "data/processed/online_retail_ii.csv",
                )
            ),
            profileJson=resolveProjectPath(
                os.getenv("INTELLIBASKET_PROFILE_JSON", "outputs/source_profile.json")
            ),
            hdfsSourceDir=os.getenv(
                "INTELLIBASKET_HDFS_SOURCE_DIR",
                "/data/intellibasket/ods/online_retail_ii",
            ),
            hiveDatabase=os.getenv("INTELLIBASKET_HIVE_DATABASE", "intellibasket"),
            mysqlUrl=os.getenv(
                "INTELLIBASKET_MYSQL_URL",
                "mysql+pymysql://intellibasket:intellibasket@localhost:3307/intellibasket",
            ),
            apiHost=os.getenv("INTELLIBASKET_API_HOST", "127.0.0.1"),
            apiPort=int(os.getenv("INTELLIBASKET_API_PORT", "8000")),
            allowedOrigins=tuple(
                origin.strip() for origin in allowedOriginsRaw.split(",") if origin.strip()
            ),
        )

    def ensureLocalDirectories(self) -> None:
        """Create generated-output directories required by local jobs."""
        self.preparedCsv.parent.mkdir(parents=True, exist_ok=True)
        self.profileJson.parent.mkdir(parents=True, exist_ok=True)
