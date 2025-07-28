locals {
  # Define the prefix for the resources
  prefix = "my-pgsql-mcp"

  # Networking
  subnet_ids_private = ["subnet-***", "subnet-***"] # Replace with your actual private subnet IDs
  vpc_id = "vpc-***" # Replace with your actual VPC ID

  # AWS Secrets Manager
  rds_secret_arn = "arn:aws:secretsmanager:***" # Replace with your actual RDS secret ARN. If not used, remove references below

  # Route 53 configuration
  r53_public_hosted_zone = "YOUR_ACCOUNT_ID.cloud.bayer.com" # Replace with your actual Route 53 public hosted zone ID
  subdomain = "mcp" # Replace with your desired subdomain
}

# Check if newer version of the module is available
module "mlservice_api_mcp" {
  source = "github.com/bayer-int/ph-ds-ml-serverless-api-mcp?ref=v2.1.0"

  # Required basic configuration
  prefix      = local.prefix
  environment = "dev"

  # Route configuration for Streamable HTTP transport endpoint
  # Two HTTP methods are supported by the streamable HTTP transport: GET and POST
  routes = {
    "GET /mcp" = {
      authorize = false
    }
    "POST /mcp" = {
      authorize = false
    }
  }

  # Required API Lambda configuration - using the example MCP server code
  lambda_api = {
    source_path = [
      "../src/main.py",
      {
        path          = "../src/v1",
        prefix_in_zip = "v1"
      },
      {
        path          = "../src/mlservice",
        prefix_in_zip = "mlservice"
      }
    ] # Path to exemplary MCP code

    vpc = {
      subnet_ids_private = local.subnet_ids_private # Private subnets for the Lambda function
      security_group_ids = [aws_security_group.this.id] # Security group for the Lambda function
    }

    environment_variables = {
      # Required environment variables for the Lambda function
      SECRET_ID = local.rds_secret_arn # ARN of the RDS secret in AWS Secrets Manager
    }

    # Optional, if using AWS Secrets Manager for RDS credentials 
    policy_statements = {
      s3_access = {
        effect    = "Allow"
        actions   = ["secretsmanager:GetSecretValue"]
        resources = [local.rds_secret_arn] 
      }
    }

    layers = {
      # AWS managed layer that includes pg8000. Alternatively, you can use a custom layer with pg8000 installed.
      custom = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:3"] # for pg8000
    }
  }

  # Required API Gateway configuration
  api_gateway = {
    custom_domain = {
      r53_public_hosted_zone = local.r53_public_hosted_zone
      subdomain              = local.subdomain
    }
  }
}

resource "aws_security_group" "this" {
  # Set the security group name using a combination of the prefix, use case, and user profile
  name = "${local.prefix}-lambda-sg"

  # Set the description for the security group
  description = "${local.prefix}-lambda"

  # Set the VPC ID for the security group
  vpc_id = local.vpc_id

  # Define egress rule to allow all outbound traffic to postgres DBs
  dynamic "egress" {
    for_each = [443, 5432]
    content {
      from_port   = egress.value
      to_port     = egress.value
      protocol    = "TCP"
      cidr_blocks = ["0.0.0.0/0"] # Adjust outbound CIDR blocks as needed, e.g., to VPC CIDR of your RDS instance
      description = "Allow outbound traffic."
    }
  }

  # Define tags for the security group
  tags = {
    Name = "${local.prefix}-lambda-sg"
  }
}
