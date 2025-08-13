"""PostgreSQL MCP Server implementation."""

import json
import os
from typing import Annotated, Any, Dict

from aws_lambda_powertools import Logger
from fastmcp import FastMCP
from mlservice.db import (
    Settings,
    check_sql_injection_risk,
    detect_mutating_keywords,
    get_cnxn,
)
from pydantic import Field

settings = Settings()
if settings.debug:
    os.environ["LOG_LEVEL"] = "DEBUG"

logger = Logger()


mcp = FastMCP("Postgresql MCP Server")

#####################################
### Resource Definitions
#####################################


@mcp.resource("postgresql://{table_name}/data")
def get_table_data(
    table_name: Annotated[str, Field(description="Name of the table")],
    schema_name: Annotated[str, Field(description="Schema name")] = "public",
    max_rows: Annotated[
        int, Field(description="Maximum number of rows to return")
    ] = 100,
) -> str:
    """Get data for a table."""
    query = f"SELECT * FROM {schema_name}.{table_name} LIMIT {max_rows}"

    return execute_sql.fn(query=query)


#####################################
### Tool Definitions
#####################################


@mcp.tool
def get_tables(
    schema_name: Annotated[str, Field(description="Schema name")] = "public",
) -> list[dict]:
    """List PostgreSQL tables and views with their descriptions."""

    with get_cnxn(settings) as cnxn:
        cursor = cnxn.cursor()
        try:
            # Query to get user tables and views with descriptions from PostgreSQL
            cursor.execute(
                """
                SELECT 
                    t.table_name,
                    t.table_type,
                    obj_description(pgc.oid) AS table_description
                FROM information_schema.tables t
                LEFT JOIN pg_catalog.pg_class pgc ON pgc.relname = t.table_name
                LEFT JOIN pg_catalog.pg_namespace pgn ON pgn.oid = pgc.relnamespace 
                    AND pgn.nspname = t.table_schema
                WHERE t.table_schema = %s
                    AND t.table_type IN ('BASE TABLE','VIEW') AND obj_description(pgc.oid) is not null

                UNION ALL

                SELECT 
                    pgc.relname AS table_name,
                    'MATERIALIZED VIEW' AS table_type,
                    obj_description(pgc.oid) AS table_description
                FROM pg_catalog.pg_class pgc
                JOIN pg_catalog.pg_namespace pgn ON pgn.oid = pgc.relnamespace
                WHERE pgn.nspname = %s
                    AND pgc.relkind = 'm' AND obj_description(pgc.oid) is not null

                ORDER BY table_name
                """,
                (schema_name, schema_name),
            )
            tables = cursor.fetchall()
            logger.info(f"Found tables and (materialized) views: {tables}")

            tables_output = []
            for table in tables:
                table_info = {
                    "name": table[0],
                    "type": table[1],  # 'VIEW' or 'MATERIALIZED VIEW'
                    "description": table[2] if table[2] else None,
                }
                tables_output.append(table_info)

            return tables_output
        except Exception as e:
            logger.error(f"Failed to list resources: {str(e)}")
            return []
        finally:
            cursor.close()


@mcp.tool
def get_table_schemas(
    tables: Annotated[list[str], Field(description="Names of the tables")],
    schema_name: Annotated[str, Field(description="Schema name")] = "public",
) -> list[Dict[str, Any]]:
    """Get schema information for tables including column details and foreign key relationships."""

    query = """
        WITH all_columns AS (
            SELECT 
                a.attname AS column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                CASE 
                    WHEN a.atttypmod > 0 AND t.typname IN ('varchar', 'char', 'bpchar') 
                    THEN a.atttypmod - 4
                    ELSE NULL
                END AS character_maximum_length,
                CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS is_nullable,
                pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS column_default,
                c.relname AS table_name,
                n.nspname AS table_schema,
                a.attnum AS ordinal_position,
                c.oid AS table_oid
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
            JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
            LEFT JOIN pg_catalog.pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
            WHERE c.relkind IN ('r', 'v', 'm')  -- tables, views, materialized views
            AND n.nspname = %s
            AND c.relname = ANY(%s)
            AND a.attnum > 0
            AND NOT a.attisdropped
        )
        SELECT
            ac.column_name,
            ac.data_type,
            ac.character_maximum_length,
            ac.is_nullable,
            ac.column_default,
            col_desc.description AS column_description,
            tbl_desc.description AS table_description,
            ac.table_name,
            tc.constraint_name AS fk_constraint_name,
            ccu.table_schema AS fk_referenced_schema,
            ccu.table_name AS fk_referenced_table,
            ccu.column_name AS fk_referenced_column
        FROM all_columns ac
        -- Column descriptions
        LEFT JOIN pg_catalog.pg_description col_desc ON col_desc.objoid = ac.table_oid
            AND col_desc.objsubid = ac.ordinal_position
        -- Table descriptions  
        LEFT JOIN pg_catalog.pg_description tbl_desc ON tbl_desc.objoid = ac.table_oid
            AND tbl_desc.objsubid = 0
        -- Foreign key information (simplified)
        LEFT JOIN information_schema.key_column_usage kcu ON kcu.table_schema = ac.table_schema
            AND kcu.table_name = ac.table_name
            AND kcu.column_name = ac.column_name
        LEFT JOIN information_schema.table_constraints tc ON tc.constraint_name = kcu.constraint_name
            AND tc.constraint_type = 'FOREIGN KEY'
        LEFT JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
        ORDER BY ac.table_name, ac.ordinal_position;
        """
    with get_cnxn(settings) as cnxn:
        cursor = cnxn.cursor()
        try:
            cursor.execute(query, (schema_name, tables))
            columns = cursor.fetchall()
            # Group columns by table name
            tables_schemas = {}
            for col in columns:
                table_name = col[7]  # table_name is now the 8th column (index 7)

                if table_name not in tables_schemas:
                    tables_schemas[table_name] = {
                        "name": table_name,
                        "schema": schema_name,
                        "description": col[6] if col[6] else None,  # table description
                        "columns": [],
                    }

                # Build foreign key info if it exists
                foreign_key = None
                if col[8]:  # fk_constraint_name exists
                    foreign_key = {
                        "referenced_schema": col[9],
                        "referenced_table": col[10],
                        "referenced_column": col[11],
                    }

                tables_schemas[table_name]["columns"].append(
                    {
                        "name": col[0],
                        "type": col[1],
                        "max_length": col[2],
                        "nullable": col[3],
                        "default": col[4],
                        "description": col[5] if col[5] else None,
                        "foreign_key": foreign_key,
                    }
                )

            return list(tables_schemas.values())
        except Exception as e:
            logger.error(f"Error getting table schemas: {str(e)}")
            return []
        finally:
            cursor.close()


@mcp.tool()
def execute_sql(
    query: Annotated[str, Field(description="SQL query to execute")],
) -> str:
    """Execute a SQL query and return the result."""

    if settings.read_only_connection:
        matches = detect_mutating_keywords(query)
        if matches:
            logger.info(
                f"Query is rejected because current setting only allows readonly query. \
                    Detected keywords: {matches}, SQL query: {query}"
            )
            return "Error: Your MCP tool only allows readonly query. \
                If you want to write, change the MCP configuration"

    issues = check_sql_injection_risk(query)
    if issues:
        logger.info(
            f"query is rejected because it contains risky SQL pattern, \
                SQL query: {query}, reasons: {issues}"
        )
        return f"Query parameter contains suspicious pattern with following issues: {issues}"

    with get_cnxn(settings) as cnxn:
        cursor = cnxn.cursor()
        try:
            logger.info(f"Executing SQL query: {query}")
            cursor.execute(query)
            # Regular SELECT queries
            if query.strip().upper().startswith(("SELECT", "WITH")):
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                result = [",".join(map(str, row)) for row in rows]
                return "\n".join([",".join(columns)] + result)

            # Non-SELECT queries
            cnxn.commit()
            affected_rows = cursor.rowcount
            return f"Query executed successfully. Rows affected: {affected_rows}"

        except Exception as e:
            logger.error(f"Error executing SQL '{query}': {e}")
            return f"Error executing query: {str(e)}"

        finally:
            cursor.close()
