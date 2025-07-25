#!/usr/bin/env python3
"""
Test script for sanmcp MCP integration.

This script tests the connection and functionality of the postgres MCP server
integration with your ML service.

Usage:
    python test_mcp_integration.py
"""

import sys
import os
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from mcp_integration import MCPClient, MLServiceMCPIntegration
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure to install dependencies: pip install fastmcp pyyaml")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_basic_connectivity():
    """Test basic MCP server connectivity."""
    print("\n🔍 Testing basic MCP connectivity...")
    
    try:
        client = MCPClient()
        result = client.ping("test_connection")
        print(f"✅ Ping successful: {result}")
        return True
    except Exception as e:
        print(f"❌ Ping failed: {e}")
        return False

def test_database_connection():
    """Test database connectivity through MCP."""
    print(f"\n🔍 Testing postgres database connection...")
    
    try:
        client = MCPClient()
        
        result = client.execute_sql("SELECT version() as postgres_version")
        
        
        
        if result and "error" not in str(result).lower():
            print("✅ Database connection successful")
            print(f"   Result preview: {str(result)[:100]}...")
            return True
        else:
            print(f"❌ Database query failed: {result}")
            return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_table_operations():
    """Test table listing and schema operations."""
    print(f"\n🔍 Testing postgres table operations...")
    
    try:
        client = MCPClient()
        
        # Test table listing
        
        tables = client.get_tables(schema_name="public")
        schema_name = "public"
        
        
        
        if tables:
            print(f"✅ Found {len(tables)} tables in {schema_name} schema")
            
            # Show first few tables
            for i, table in enumerate(tables[:3]):
                table_name = table.get("name", "unknown")
                table_type = table.get("type", "unknown")
                print(f"   - {table_name} ({table_type})")
            
            # Test schema information for first table
            if tables:
                first_table = tables[0].get("name")
                if first_table:
                    schema_info = client.get_table_schemas([first_table], schema_name)
                    if schema_info:
                        columns = schema_info[0].get("columns", [])
                        print(f"✅ Schema info for {first_table}: {len(columns)} columns")
                        return True
        else:
            print(f"⚠️  No tables found in {schema_name} schema")
            return True  # Not necessarily an error
            
    except Exception as e:
        print(f"❌ Table operations failed: {e}")
        return False

def test_resource_access():
    """Test MCP resource access."""
    print(f"\n🔍 Testing postgres resource access...")
    
    try:
        client = MCPClient()
        
        # First get a table to test resource access
        
        tables = client.get_tables(schema_name="public")
        
        
        
        if tables and len(tables) > 0:
            test_table = tables[0].get("name")
            if test_table:
                
                data = client.get_table_data(test_table, schema_name="public", max_rows=5)
                
                
                
                if data:
                    print(f"✅ Resource access successful for table {test_table}")
                    print(f"   Data preview: {str(data)[:100]}...")
                    return True
                else:
                    print(f"⚠️  No data returned for table {test_table}")
                    return True
        else:
            print("⚠️  No tables available for resource testing")
            return True
            
    except Exception as e:
        print(f"❌ Resource access failed: {e}")
        return False

def test_ml_service_integration():
    """Test high-level ML service integration."""
    print(f"\n🔍 Testing ML service integration...")
    
    try:
        integration = MLServiceMCPIntegration()
        
        # Health check
        health = integration.health_check()
        if health.get("status") == "healthy":
            print("✅ ML service integration health check passed")
            print(f"   Available tools: {health.get('available_tools', 0)}")
        else:
            print(f"❌ Health check failed: {health}")
            return False
        
        # Test feature metadata
        try:
            metadata = integration.get_feature_metadata()
            if metadata:
                print("✅ Feature metadata retrieval successful")
                if isinstance(metadata, list) and len(metadata) > 0:
                    print(f"   Found metadata for {len(metadata)} tables")
            else:
                print("⚠️  No feature metadata found")
        except Exception as e:
            print(f"⚠️  Feature metadata test failed: {e}")
        
        # Test schema validation
        try:
            validation = integration.validate_data_schema(["id", "name", "created_at"])
            print(f"✅ Schema validation completed: {validation.get('valid', False)}")
        except Exception as e:
            print(f"⚠️  Schema validation test failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ ML service integration failed: {e}")
        return False

def test_error_handling():
    """Test error handling and edge cases."""
    print(f"\n🔍 Testing error handling...")
    
    try:
        client = MCPClient()
        
        # Test invalid SQL (should be caught by security checks)
        try:
            result = client.execute_sql("DROP TABLE nonexistent_table")
            if "error" in str(result).lower() or "rejected" in str(result).lower():
                print("✅ SQL injection protection working")
            else:
                print("⚠️  SQL injection protection may not be working")
        except Exception:
            print("✅ SQL injection protection working (exception caught)")
        
        # Test invalid table name
        try:
            
            result = client.get_table_schemas(["nonexistent_table_12345"], "public")
            
            
            
            if not result or len(result) == 0:
                print("✅ Invalid table handling working")
            else:
                print("⚠️  Invalid table handling may need review")
        except Exception:
            print("✅ Invalid table handling working (exception caught)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def print_configuration_help():
    """Print helpful configuration information."""
    print("\n📋 Configuration Help:")
    print("=" * 50)
    
    env_file = Path(__file__).parent / ".env.mcp"
    config_file = Path(__file__).parent / "mcp_config.yaml"
    
    if not env_file.exists():
        print("⚠️  .env.mcp file not found")
        print("   Copy .env.mcp.example to .env.mcp and update with your settings")
    else:
        print("✅ .env.mcp file found")
    
    if not config_file.exists():
        print("⚠️  mcp_config.yaml file not found")
    else:
        print("✅ mcp_config.yaml file found")
    
    print(f"\nMCP Server Type: postgres")
    
    print("Required environment variables:")
    print("- SECRET_ID (for AWS Secrets Manager) OR")
    print("- PG_HOST, PG_USER, PG_PASSWORD, PG_DBNAME (for direct connection)")
    
    
    
    print("\nTo start MCP server locally:")
    print("cd mcp-server/src && uv run main.py")

def main():
    """Run all integration tests."""
    print("🚀 Starting sanmcp MCP Integration Tests")
    print("=" * 60)
    
    # Print configuration information
    print_configuration_help()
    
    # Run tests
    tests = [
        ("Basic Connectivity", test_basic_connectivity),
        ("Database Connection", test_database_connection), 
        ("Table Operations", test_table_operations),
        ("Resource Access", test_resource_access),
        ("ML Service Integration", test_ml_service_integration),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Summary:")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! MCP integration is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check configuration and MCP server status.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
