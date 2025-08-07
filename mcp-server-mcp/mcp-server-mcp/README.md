# PostgreSQL MCP Server

A Model Context Protocol (MCP) server for PostgreSQL that provides secure database connectivity with built-in SQL injection protection and read-only connection options.

> [!NOTE]  
> This MCP server uses pg8000, a pure Python PostgreSQL driver for connecting to a postgres database (e.g., hosted in AWS RDS). If you are using AWS *Aurora* PostgreSQL, consider leveraging the data api and using the open source [Aurora Postgres MCP Server by AWS](https://github.com/awslabs/mcp/tree/main/src/postgres-mcp-server) instead. You can extend the AWS provided MCP server with the tools provided by this inner source MCP server to get the best from both worlds.

- [PostgreSQL MCP Server](#postgresql-mcp-server)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
    - [Environment Variables](#environment-variables)
      - [Option 1: AWS Secrets Manager (Recommended)](#option-1-aws-secrets-manager-recommended)
      - [Option 2: Direct Environment Variables](#option-2-direct-environment-variables)
      - [Optional Configuration](#optional-configuration)
  - [Usage](#usage)
    - [Running Locally](#running-locally)
    - [Deployment via ML Service](#deployment-via-ml-service)
  - [MCP Resources](#mcp-resources)
    - [Available Resources](#available-resources)
    - [MCP Tools](#mcp-tools)
    - [Example Tool Usage](#example-tool-usage)
  - [MCP Tools](#mcp-tools-1)
    - [execute\_sql](#execute_sql)
    - [get\_tables](#get_tables)
    - [get\_table\_schemas](#get_table_schemas)
  - [Security Features](#security-features)
    - [SQL Injection Protection](#sql-injection-protection)
    - [Read-Only Mode](#read-only-mode)
    - [Detected Mutating Keywords](#detected-mutating-keywords)
  - [Database Schema Support](#database-schema-support)
  - [PostgreSQL-Specific Features](#postgresql-specific-features)
  - [Testing](#testing)
  - [Development](#development)
    - [Project Structure](#project-structure)
  - [Contributing](#contributing)


## Features

- **Database Access**: Built-in SQL injection detection and prevention
- **Read-Only Mode**: Configurable read-only connection to prevent accidental data modification
- **AWS Integration**: Supports AWS Secrets Manager for secure credential management
- **ML Service & Lambda Ready**: Optimized for AWS Lambda deployment using the [ML Service serverless MCP terraform module](https://github.com/bayer-int/ph-ds-ml-serverless-api-mcp)
- **Schema Discovery**: Automatic table and column schema detection with descriptions
- **Resource-Based API**: MCP resources for tables, schemas, and data exploration (can be easily switched to model-controlled tools)

## Prerequisites

- Python 3.12+
- `uv` package manager (for local development & deployment)
- PostgreSQL database
- pg8000 PostgreSQL driver (pure Python driver)
- AWS credentials and AWS CLI (if using Secrets Manager)

## Configuration

1. Make sure prerequisites are installed.
2. Configure environment variables.

### Environment Variables

The server supports two configuration methods:

#### Option 1: AWS Secrets Manager (Recommended)

Either use a .env file or set environment variables directly.
```bash
SECRET_ID=your-secret-id  # AWS Secrets Manager secret ID
```

The secret should contain:
```json
{
  "host": "your-postgresql-host",
  "port": 5432,
  "username": "your-username", 
  "password": "your-password",
  "dbname": "your-database-name"
}
```

#### Option 2: Direct Environment Variables
```bash
PG_HOST=your-postgresql-host
PG_PORT=5432  # Optional, defaults to 5432
PG_USER=your-username
PG_PASSWORD=your-password
PG_DBNAME=your-database-name
```

#### Optional Configuration
```bash
READ_ONLY_CONNECTION=true    # Default: true - prevents mutating queries
DEBUG=false                  # Default: false - enables debug logging
```

## Usage

### Running Locally

```bash
cd postgres/src
# Run the MCP server directly (packages will be installed on-the-fly)
uv run main.py
```

### Deployment via ML Service 

The server is designed to run on AWS Lambda using Mangum in stateless mode. You can use the exemplary configuration of the ML Service serverless MCP terraform module in the [/terraform](./terraform/) folder as starting point. 

## MCP Resources

The server exposes several MCP resources for database exploration:

### Available Resources

- `postgresql://{table_name}/data` - Get sample data from a table (limited to 100 rows by default)

### MCP Tools

The server provides several tools for database interaction:

- `execute_sql` - Execute SQL queries with built-in security checks  
- `get_tables` - List PostgreSQL tables and (materialized) views with descriptions from a specific schema
- `get_table_schemas` - Get detailed schema information for tables including column details and foreign key relationships

### Example Tool Usage

```python
import asyncio
import pprint

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def example():
    shttp = StreamableHttpTransport(
        # The URL of the server
        url="http://127.0.0.1:8000/mcp",
        headers={
            # leave empty if no authentication is needed
            # "Authorization": "Bearer "  # or
            # "Authorization": "API KEY"
        },
    )

    async with Client(transport=shttp) as client:
        # List available tools
        tools = await client.list_tools()
        pprint.pp(f"Available tools: {tools}")

        # Get tables from public schema
        tables = await client.call_tool("get_tables", {"schema_name": "public"})
        pprint.pp(f"Tables: {tables}")
        
        # Get schema for specific tables
        if tables:
            table_names = [table['name'] for table in tables[0].text if isinstance(tables[0].text, list)]
            schemas = await client.call_tool("get_table_schemas", {
                "tables": table_names[:3],  # Get schema for first 3 tables
                "schema_name": "public"
            })
            pprint.pp(f"Table schemas: {schemas}")

        # Execute a sample query
        result = await client.call_tool(
            "execute_sql",
            {"query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 5"},
        )
        pprint.pp(result[0].text)

        # Get sample data from a table (using resource)
        data = await client.read_resource("postgresql://your_table_name/data")
        pprint.pp(data)



if __name__ == "__main__":
    asyncio.run(example())
```

## MCP Tools

### execute_sql

Execute SQL queries with built-in security checks.

**Parameters:**
- `query` (string): SQL query to execute

**Security Features:**
- SQL injection pattern detection
- Read-only mode enforcement (blocks INSERT, UPDATE, DELETE, etc.)
- Suspicious pattern filtering

**Returns:**
- For SELECT queries: CSV-formatted results with column headers
- For non-SELECT queries: Success message with affected row count

### get_tables

List PostgreSQL tables and views with their descriptions from a specific schema.

**Parameters:**
- `schema_name` (string, optional): Schema name (defaults to "public")

**Returns:**
- List of dictionaries containing table information:
  - `name`: Table name
  - `type`: Table type (BASE TABLE, VIEW, MATERIALIZED VIEW)
  - `description`: Table description from PostgreSQL comments

### get_table_schemas

Get detailed schema information for tables including column details and foreign key relationships.

**Parameters:**
- `tables` (list[str]): Names of the tables to get schema information for
- `schema_name` (string, optional): Schema name (defaults to "public")

**Returns:**
- List of dictionaries containing detailed table schema:
  - `name`: Table name
  - `schema`: Schema name
  - `description`: Table description
  - `columns`: List of column information including:
    - `name`: Column name
    - `type`: Data type
    - `max_length`: Maximum character length (for text types)
    - `nullable`: Whether column allows NULL values
    - `default`: Default value
    - `description`: Column description from PostgreSQL comments
    - `foreign_key`: Foreign key relationship information (if applicable)

## Security Features

### SQL Injection Protection

The server includes comprehensive SQL injection protection:

- **Pattern Detection**: Identifies suspicious patterns like SQL comments, UNION injections, and tautologies
- **Keyword Filtering**: Blocks dangerous functions and PostgreSQL-specific risky patterns
- **Input Validation**: Validates query structure and content

### Read-Only Mode

When `READ_ONLY_CONNECTION=true` (default), the server blocks:
- INSERT, UPDATE, DELETE operations
- DDL operations (CREATE, DROP, ALTER)
- Administrative commands and functions
- Permission changes (GRANT, REVOKE)
- PostgreSQL extensions and function creation

### Detected Mutating Keywords

```
INSERT, UPDATE, DELETE, MERGE, TRUNCATE,
CREATE, DROP, ALTER, RENAME, GRANT, REVOKE,
COMMENT ON, SECURITY LABEL, CREATE EXTENSION, CREATE FUNCTION,
INSTALL, CLUSTER, REINDEX, VACUUM, ANALYZE
```

## Database Schema Support

The server automatically discovers and exposes:

- **Table Names**: From `information_schema.tables`
- **Column Information**: Data types, nullable status, defaults, character limits
- **Descriptions**: Table and column descriptions from PostgreSQL comments (`pg_description`)
- **Schema Organization**: Support for multiple database schemas (default: "public")
- **Foreign Key Relationships**: Automatic detection of foreign key constraints
- **View and Materialized View Support**: Includes regular views and materialized views

## PostgreSQL-Specific Features

The server supports PostgreSQL-specific features and capabilities:

- **Schema Support**: Works with any PostgreSQL schema (defaults to "public")
- **Views and Materialized Views**: Full support for both regular and materialized views
- **Extended Properties**: Reads table and column descriptions from PostgreSQL comment system
- **Foreign Key Detection**: Automatically discovers foreign key relationships
- **SSL Support**: Built-in SSL/TLS support for secure connections

## Testing

Run the test suite:

```bash
cd postgres/src
pytest .
```

## Development

### Project Structure

```
postgres/
├── src/
│   ├── main.py          # (Lambda) entry point
│   ├── v1/
│   │   └── server.py    # MCP server implementation
│   ├── mlservice/
│   │   ├── db.py        # Database connection and security
│   │   └── utils.py     # AWS utilities
│   └── tests/
│       ├── test_db.py   # Database tests
│       └── test_utils.py # Utility tests
├── terraform/           # ML Service module Terraform config 
├── README.md            # This file
```

## Contributing

Please refer to the main repository's `CONTRIBUTING.md` and `DEVELOPER_GUIDE.md` for contribution guidelines.
