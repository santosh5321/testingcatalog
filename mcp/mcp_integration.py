"""
Production MCP Integration Client for sample-mcp-server

This module provides a robust interface to connect your ML service 
to the production postgres MCP server from bayer-int/mcp-servers.

Uses the FastMCP framework with streamable HTTP transport for production deployment.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Union
from contextlib import asynccontextmanager

try:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
except ImportError:
    raise ImportError(
        "FastMCP not installed. Install with: pip install fastmcp"
    )

import yaml
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class MCPClient:
    """Production MCP client for postgres server integration."""
    
    def __init__(
        self, 
        mcp_url: str = None,
        config_file: str = None,
        auth_token: str = None
    ):
        """
        Initialize MCP client.
        
        Args:
            mcp_url: MCP server URL (defaults to config or localhost)
            config_file: Path to configuration file
            auth_token: Authorization token for secure deployment
        """
        self.config = self._load_config(config_file)
        self.mcp_url = mcp_url or self.config.get("mcp_url", "http://localhost:8000/mcp")
        self.auth_token = auth_token or self.config.get("auth_token")
        
        # Transport configuration
        self.headers = {}
        if self.auth_token:
            self.headers["Authorization"] = f"Bearer {self.auth_token}"
            
    def _load_config(self, config_file: str = None) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not config_file:
            config_file = Path(__file__).parent / "mcp_config.yaml"
            
        try:
            with open(config_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file {config_file} not found, using defaults")
            return {}
    
    @asynccontextmanager
    async def _client(self):
        """Create async MCP client context manager."""
        transport = StreamableHttpTransport(
            url=self.mcp_url,
            headers=self.headers
        )
        
        async with Client(transport=transport) as client:
            yield client
    
    async def _call_tool_async(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call MCP tool asynchronously."""
        async with self._client() as client:
            result = await client.call_tool(tool_name, arguments)
            return result
    
    async def _read_resource_async(self, resource_uri: str) -> Any:
        """Read MCP resource asynchronously."""
        async with self._client() as client:
            result = await client.read_resource(resource_uri)
            return result
    
    def _run_async(self, coro):
        """Run async function in sync context."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    # Synchronous wrapper methods for ML service integration
    
    def execute_sql(self, query: str) -> Union[str, Dict[str, Any]]:
        """
        Execute SQL query on postgres database.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Query results as CSV string or error message
        """
        return self._run_async(
            self._call_tool_async("execute_sql", {"query": query})
        )
    
    
    def get_tables(self, schema_name: str = "public") -> List[Dict[str, Any]]:
        """
        Get PostgreSQL tables and views.
        
        Args:
            schema_name: Schema name (default: "public")
            
        Returns:
            List of table information dictionaries
        """
        return self._run_async(
            self._call_tool_async("get_tables", {"schema_name": schema_name})
        )
    
    def get_table_schemas(
        self, 
        tables: List[str], 
        schema_name: str = "public"
    ) -> List[Dict[str, Any]]:
        """
        Get detailed PostgreSQL table schema information.
        
        Args:
            tables: List of table names
            schema_name: Schema name (default: "public")
            
        Returns:
            Detailed schema information including columns and foreign keys
        """
        return self._run_async(
            self._call_tool_async("get_table_schemas", {
                "tables": tables,
                "schema_name": schema_name
            })
        )
    
    def get_table_data(
        self, 
        table_name: str, 
        schema_name: str = "public", 
        max_rows: int = 100
    ) -> str:
        """
        Get sample data from PostgreSQL table.
        
        Args:
            table_name: Name of the table
            schema_name: Schema name (default: "public")
            max_rows: Maximum rows to return (default: 100)
            
        Returns:
            Table data as formatted string
        """
        resource_uri = f"postgresql://{table_name}/data"
        return self._run_async(self._read_resource_async(resource_uri))
    
    
    
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools."""
        async with self._client() as client:
            return await client.list_tools()
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available MCP resources."""
        async with self._client() as client:
            return await client.list_resources()
    
    def ping(self, message: str = "ping") -> str:
        """Test MCP server connectivity."""
        try:
            # Most MCP servers have a ping or health check tool
            return self._run_async(
                self._call_tool_async("ping", {"message": message})
            )
        except Exception as e:
            return f"MCP server not reachable: {str(e)}"


class MLServiceMCPIntegration:
    """High-level integration wrapper for ML service use cases."""
    
    def __init__(self, config_file: str = None):
        """Initialize ML service MCP integration."""
        self.mcp = MCPClient(config_file=config_file)
        
    
    def get_training_data(
        self, 
        table_name: str = "training_data",
        where_clause: str = "active = true",
        schema_name: str = "public"
    ) -> Dict[str, Any]:
        """Get training data for ML model."""
        query = f"SELECT * FROM {schema_name}.{table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        return self.mcp.execute_sql(query)
    
    def get_feature_metadata(self, schema_name: str = "public") -> Dict[str, Any]:
        """Get feature metadata for ML pipeline."""
        tables = self.mcp.get_tables(schema_name=schema_name)
        if tables:
            table_names = [t.get("name") for t in tables if t.get("name")]
            return self.mcp.get_table_schemas(table_names[:10], schema_name)
        return {}
    
    
    
    
    def validate_data_schema(self, expected_columns: List[str]) -> Dict[str, Any]:
        """Validate that expected columns exist in the database."""
        try:
            
            tables = self.mcp.get_tables(schema_name="public")
            
            
            
            validation_results = {"valid": True, "missing_columns": [], "tables_checked": []}
            
            for table in tables[:5]:  # Check first 5 tables
                table_name = table.get("name")
                if table_name:
                    
                    schema = self.mcp.get_table_schemas([table_name], "public")
                    
                    
                    
                    if schema:
                        columns = [col.get("name") for col in schema[0].get("columns", [])]
                        missing = [col for col in expected_columns if col not in columns]
                        
                        validation_results["tables_checked"].append({
                            "table": table_name,
                            "columns": columns,
                            "missing": missing
                        })
                        
                        if missing:
                            validation_results["valid"] = False
                            validation_results["missing_columns"].extend(missing)
            
            return validation_results
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for MCP integration."""
        try:
            # Test basic connectivity
            ping_result = self.mcp.ping("health_check")
            
            # Test database connectivity  
            
            test_query = "SELECT 1 as health_check"
            
            
            
            query_result = self.mcp.execute_sql(test_query)
            
            # Test tools availability
            tools = asyncio.run(self.mcp.list_tools())
            
            return {
                "status": "healthy",
                "ping": ping_result,
                "database_query": "success" if query_result else "failed",
                "available_tools": len(tools) if tools else 0,
                "mcp_server_type": "postgres"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "mcp_server_type": "postgres"
            }


# Example usage for your ML service
class Sample-mcp-serverWithMCP:
    """Example ML service enhanced with MCP capabilities."""
    
    def __init__(self):
        self.mcp_integration = MLServiceMCPIntegration()
        # Your existing ML service initialization
        
    def enhanced_training_pipeline(self):
        """Example: ML training pipeline with MCP data."""
        # Health check first
        health = self.mcp_integration.health_check()
        if health.get("status") != "healthy":
            raise Exception(f"MCP not healthy: {health}")
        
        # Get training data via MCP
        training_data = self.mcp_integration.get_training_data()
        
        # Get feature metadata
        metadata = self.mcp_integration.get_feature_metadata()
        
        # Your existing ML training logic
        # model = train_model(training_data, metadata)
        # return model
        
        return {"training_data": training_data, "metadata": metadata}
    
    def enhanced_prediction(self, input_data: Dict[str, Any]):
        """Example: ML prediction with MCP context."""
        # Validate input schema
        expected_columns = ["feature1", "feature2", "feature3"]  # Your features
        validation = self.mcp_integration.validate_data_schema(expected_columns)
        
        if not validation.get("valid"):
            logger.warning(f"Schema validation failed: {validation}")
        
        # Your existing prediction logic with MCP context
        # prediction = your_model.predict(input_data)
        # return prediction
        
        return {"input": input_data, "validation": validation}


if __name__ == "__main__":
    # Test the MCP integration
    integration = MLServiceMCPIntegration()
    
    print("Testing MCP Integration...")
    
    # Health check
    health = integration.health_check()
    print(f"Health Check: {health}")
    
    if health.get("status") == "healthy":
        try:
            # Test data access
            
            tables = integration.mcp.get_tables("public")
            print(f"Available tables: {len(tables) if tables else 0}")
            
            
            
            # Test schema validation
            validation = integration.validate_data_schema(["id", "name", "value"])
            print(f"Schema validation: {validation.get('valid')}")
            
        except Exception as e:
            print(f"Integration test failed: {e}")
    else:
        print("MCP server not healthy - check configuration and server status")
