import asyncio
from app.services.agent_service import AgentService

async def main():
    service = AgentService()
    prompt = "I want to build the full workflow. 6 scenes, 10 clips total, 16:9 cinematic format. Multiple video clips per scene. Make it huge."
    result = await service.generate_workflow(prompt=prompt, model="Claude 4.6 Opus (High)")
    nodes = result.get('nodes', [])
    print(f"Nodes generated: {len(nodes)}")
    if nodes:
        print(f"First node: {nodes[0]}")
    print(f"Tool calls: {result.get('tool_calls')}")
        
asyncio.run(main())
