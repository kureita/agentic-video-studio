import asyncio
import json
import logging
from app.services.agent_service import AgentService

logging.basicConfig(level=logging.DEBUG)

async def main():
    service = AgentService()
    print("Testing Claude Opus 4 6")
    res = await service.generate_workflow(
        prompt="Make a funny cat video",
        model="Claude (High)",
    )
    print("Result:")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
