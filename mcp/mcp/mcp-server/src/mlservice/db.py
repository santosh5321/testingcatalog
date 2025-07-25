"""PostgreSQL Database Utilities"""

import json
import os
import re
from typing import Annotated, Self

import pg8000
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = Logger()

MUTATING_KEYWORDS = {
    # DML
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "TRUNCATE",
    # DDL
    "CREATE",
    "DROP",
    "ALTER",
    "RENAME",
    # Permissions
    "GRANT",
    "REVOKE",
    # Metadata changes
    "COMMENT ON",
    "SECURITY LABEL",
    # Extensions and functions
    "CREATE EXTENSION",
    "CREATE FUNCTION",
    "INSTALL",
    # Storage-level
    "CLUSTER",
    "REINDEX",
    "VACUUM",
    "ANALYZE",
}

# Compile regex pattern
MUTATING_PATTERN = re.compile(
    r"(?i)\b(" + "|".join(re.escape(k) for k in MUTATING_KEYWORDS) + r")\b"
)

SUSPICIOUS_PATTERNS = [
    r"(?i)\bor\b\s+\d+\s*=\s*\d+",  # numeric tautology e.g. OR 1=1
    r"(?i)\bor\b\s*'[^']+'\s*=\s*'[^']+'",  # string tautology e.g. OR '1'='1'
    r"(?i)\bdrop\b",  # DROP statement
    r"(?i)\btruncate\b",  # TRUNCATE
    r"(?i)\bgrant\b|\brevoke\b",  # GRANT or REVOKE
    r"(?i)\bsleep\s*\(",  # delay-based probes
    r"(?i)\bpg_sleep\s*\(",
    r"(?i)\bload_file\s*\(",
    r"(?i)\binto\s+outfile\b",
]


class Settings(BaseSettings):
    """Settings for PostgreSQL connection."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_file=".env",
        extra="ignore",
    )

    read_only_connection: Annotated[
        bool,
        Field(description="Use read-only connection for the database"),
    ] = True
    debug: Annotated[bool, Field(description="Enable debug mode")] = False

    secret_id: Annotated[str | None, Field(description="Secret ID")] = None

    pg_host: Annotated[str, Field(description="Host")]
    pg_port: Annotated[int, Field(description="Port", default=5432)] = 5432
    pg_password: Annotated[str, Field(description="Password")]
    pg_user: Annotated[str, Field(description="User")]
    pg_dbname: Annotated[str, Field(description="Database name")]

    @model_validator(mode="before")
    def evaluate(self: dict) -> dict:
        """Get information from secrets manager if secret_id is set."""
        if self.get("secret_id"):
            cnxn_details: dict = parameters.get_secret(
                self["secret_id"], transform="json"
            )
            try:
                self["pg_host"] = str(cnxn_details["host"])
                self["pg_port"] = int(cnxn_details.get("port", 5432))
                self["pg_password"] = str(cnxn_details["password"])
                user_name_attribute = (
                    "username" if "username" in cnxn_details else "user"
                )
                self["pg_user"] = str(cnxn_details[user_name_attribute])
                self["pg_dbname"] = str(cnxn_details["dbname"])
            except KeyError as key_error:
                logger.error('Parameter "%s" is missing.', key_error.args[0])
                raise key_error

        return self


def get_cnxn(settings: Settings) -> pg8000.Connection:
    """Get a PostgreSQL connection object.
    This function creates a connection to a PostgreSQL database using the provided
    connection details.
    Args:
        settings (Settings): Settings object containing PostgreSQL connection details.

    Returns:
        pg8000.Connection: PostgreSQL Connection object
    """
    logger.info(settings)

    config = {
        "host": settings.pg_host,
        "port": settings.pg_port,
        "user": settings.pg_user,
        "password": settings.pg_password,
        "database": settings.pg_dbname,
        "ssl_context": True,
    }

    return pg8000.connect(**config)


def detect_mutating_keywords(sql_text: str) -> list[str]:
    """Return a list of mutating keywords found in the SQL (excluding comments)."""
    matches = MUTATING_PATTERN.findall(sql_text)
    return list(
        {m.upper() for m in matches}
    )  # Deduplicated and normalized to uppercase


def check_sql_injection_risk(sql: str) -> list[dict]:
    """Check for potential SQL injection risks in sql query.

    Args:
        sql: query string

    Returns:
        dictionaries containing detected security issue
    """
    issues = []
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, sql):
            issues.append(
                {
                    "type": "sql",
                    "message": f"Suspicious pattern in query: {sql}",
                    "severity": "high",
                }
            )
            break
    return issues
