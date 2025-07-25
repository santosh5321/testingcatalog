# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "certifi",
#     "fastmcp",
# ]
# ///
import asyncio

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def example():
    shttp = StreamableHttpTransport(
        # The URL of the server
        url="http://localhost:8000/mcp",
        headers={
            # leave empty if no authentication is needed
            # "Authorization": "Bearer <YOUR TOKEN HERE>"  # or
            # "Authorization": "<YOUR API KEY HERE>"
        },
    )

    async with Client(transport=shttp) as client:
        tools = await client.list_tools()
        print(f"Available tools: {tools}")

        result = await client.call_tool(
            "execute_sql", {"query": "SELECT * FROM my_table WHERE id = 5"}
        )
        print(f"Result: {result.data}")


if __name__ == "__main__":
    asyncio.run(example())
