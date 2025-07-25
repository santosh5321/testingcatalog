# MCP Integration for sample-mcp-server

This integration adds the **postgres** MCP server from [bayer-int/mcp-servers](https://github.com/bayer-int/mcp-servers) to your ML service.

## What Was Added

### 🏗️ MCP Server Implementation
- **Location**: `mcp/mcp-server/`
- **Source**: Production MCP server from `bayer-int/mcp-servers/src/postgres`
- **Framework**: FastMCP with AWS Lambda optimization
- **Features**: SQL injection protection, read-only mode, AWS Secrets Manager support

### 🔌 ML Service Integration
- **Client Code**: `mcp/mcp_integration.py`
- **Configuration**: `mcp/mcp_config.yaml`
- **Environment**: `mcp/.env.mcp`
- **Deployment**: `mcp/terraform/` (if using ML Service module)

## Quick Start

### 1. Install Dependencies
```bash
cd mcp/mcp-server
# Install MCP server dependencies (will auto-install)
uv run src/main.py --help
```

### 2. Configure Environment
```bash
cp mcp/.env.mcp.example mcp/.env.mcp
# Edit with your specific configuration:
# - Database credentials (or AWS Secrets Manager secret ID)
# - AWS region and credentials
# - Debug settings
```

### 3. Test MCP Server Locally
```bash
cd mcp/mcp-server/src
uv run main.py
# Server will start on http://localhost:8000/mcp
```

### 4. Test Integration
```bash
cd mcp
python test_mcp_integration.py
```

## Production Deployment

### Option 1: AWS Lambda (Recommended)
The MCP server includes Terraform configuration for AWS Lambda deployment using the ML Service module:

```bash
cd mcp/terraform
# Update variables in main.tf
terraform init
terraform plan
terraform apply
```

### Option 2: Container Deployment
```bash
cd mcp/mcp-server
docker build -t sample-mcp-server-mcp .
docker run -p 8000:8000 --env-file ../.env.mcp sample-mcp-server-mcp
```

### Option 3: Local Process
```bash
cd mcp/mcp-server/src
uv run main.py
```

## Integration Examples

### Python ML Service Integration

```python
# In your existing ML service code
from mcp_integration import MCPClient

class YourMLService:
    def __init__(self):
        self.mcp = MCPClient("postgres")
        
    def get_training_data(self):
        
        # Use PostgreSQL MCP server
        return self.mcp.execute_sql(
            "SELECT features, labels FROM training_data WHERE active = true"
        )
        
        
    
    def get_feature_metadata(self):
        
        tables = self.mcp.get_tables(schema_name="public")
        return self.mcp.get_table_schemas(
            tables=[t["name"] for t in tables[:5]], 
            schema_name="public"
        )
        
        
```

### FastAPI/Flask Integration

```python
from fastapi import FastAPI
from mcp_integration import MCPClient

app = FastAPI()
mcp = MCPClient("postgres")

@app.get("/data/{table_name}")
async def get_data(table_name: str):
    
    return mcp.get_table_data(table_name=table_name, schema_name="public")
    
    

@app.post("/query")
async def execute_query(query: str):
    return mcp.execute_sql(query)
```

## MCP Server Capabilities

### Postgres MCP Server Features:


**Resources:**
- `postgresql://{table_name}/data` - Get sample data from tables

**Tools:**
- `execute_sql` - Execute PostgreSQL queries with security checks
- `get_tables` - List tables and views with descriptions  
- `get_table_schemas` - Get detailed schema information

**Security:**
- SQL injection detection and prevention
- Read-only mode (configurable)
- Pattern-based query filtering
- PostgreSQL-specific security checks




## Configuration

### Environment Variables
```bash
# Required for postgres

# Option 1: AWS Secrets Manager (Recommended)
SECRET_ID=your-rds-secret-id

# Option 2: Direct connection
PG_HOST=your-postgresql-host
PG_PORT=5432
PG_USER=your-username
PG_PASSWORD=your-password
PG_DBNAME=your-database




# Security and Debugging
READ_ONLY_CONNECTION=true  # Default: true
DEBUG=false               # Default: false
```

## Troubleshooting

### Common Issues

1. **Connection Errors**
   
   - Verify PostgreSQL server is accessible
   - Check pg8000 driver compatibility
   
   
   - Validate AWS Secrets Manager permissions

2. **Query Errors**
   - Check read-only mode settings
   - Review SQL injection detection logs
   - Verify table/schema permissions

3. **AWS Lambda Issues**
   - Check VPC configuration
   - Verify security group rules
   - Review CloudWatch logs

### Debug Mode
```bash
DEBUG=true uv run src/main.py
```

## Integration with ML Workflows

### Data Pipeline Integration
```python
# ETL Pipeline with MCP
def extract_features():
    data = mcp.execute_sql("SELECT * FROM feature_store WHERE updated_at > NOW() - INTERVAL '1 hour'")
    return process_features(data)

def validate_model_data():
    schema = mcp.get_table_schemas(["training_data"], schema_name="public")
    return validate_schema_compatibility(schema)
```

### Model Training Integration
```python
# Model training with MCP data
def train_model():
    # Get fresh training data
    training_data = mcp.get_table_data("training_data", max_rows=10000)
    
    # Get feature metadata
    metadata = mcp.get_table_schemas(["training_data"])
    
    # Train model with context
    model = train_with_metadata(training_data, metadata)
    return model
```

## Next Steps

1. **Review MCP Server Code**: Check `mcp/mcp-server/` implementation
2. **Customize Integration**: Modify `mcp_integration.py` for your use case
3. **Configure Environment**: Set up database credentials and AWS access
4. **Test Locally**: Run integration tests
5. **Deploy to AWS**: Use Terraform configuration for Lambda deployment
6. **Monitor**: Set up CloudWatch logging and monitoring

## Support

- **MCP Server Source**: [bayer-int/mcp-servers/postgres](https://github.com/bayer-int/mcp-servers/tree/main/src/postgres)
- **ML Service Module**: [ph-ds-ml-serverless-api-mcp](https://github.com/bayer-int/ph-ds-ml-serverless-api-mcp)
- **FastMCP Framework**: [fastmcp documentation](https://pypi.org/project/fastmcp/)
- **Service Owner**: user:default/santosh5321
