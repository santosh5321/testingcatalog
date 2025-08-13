# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "aws-lambda-powertools",
#     "boto3",
#     "dotenv",
#     "fastmcp",
#     "mangum",
#     "pg8000",
# ]
# ///
"""Main entry point for the AWS Lambda function using Mangum."""

import json
import os

from aws_lambda_powertools import Logger
from dotenv import load_dotenv
from mangum import Mangum

load_dotenv()

from v1.server import mcp

# Set the log level based on the DEBUG environment variable
DEBUG = json.loads(os.environ.get("DEBUG", "false").lower())
if DEBUG:
    os.environ["POWERTOOLS_LOG_LEVEL"] = "DEBUG"

# Initialize the logger
logger = Logger()


@logger.inject_lambda_context(log_event=DEBUG, clear_state=True)
def lambda_handler(event, context):
    """Lambda handler for the AWS Lambda function."""
    app = mcp.http_app(stateless_http=True)

    return Mangum(app, lifespan="on")(event, context)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
