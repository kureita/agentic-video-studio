import asyncio
from app.services.agent_service import AgentService

async def main():
    service = AgentService()
    # Mock chat history and prompt simulating the user's issue
    prompt = "I want to build the full workflow. 6 scenes, ~38 seconds total, 16:9 cinematic format. Fast-paced with rhythm — user wants MULTIPLE video clips per scene where appropriate to create energy. Continuous feel — I'll chain end frames to start frames for scene transitions. Character consistency needed — same marketer in Scenes 1, 2, and 5."
    result = await service.generate_workflow(prompt=prompt, model="Claude 4.6 Opus (High)")
    nodes = result.get('nodes', [])
    print(f"Nodes generated: {len(nodes)}")
    if nodes:
        print(f"First node: {nodes[0]}")
    # Print the tool execution if any
    print(f"Tool calls: {result.get('tool_calls')}")
        
asyncio.run(main())
