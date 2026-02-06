import os
import json
from typing import Optional, Literal
from pydantic import BaseModel
from openai import AsyncOpenAI
# import google.generativeai as genai 
# from anthropic import AsyncAnthropic

from app.core.config import settings
from app.models.graph import GraphPlan, Node, Edge

ModelProvider = Literal["openai", "anthropic", "gemini"]

class LLMFactory:
    """Factory to create LLM clients based on provider choice."""
    
    @staticmethod
    async def generate_plan(
        provider: ModelProvider,
        system_prompt: str,
        messages: list[dict],
        response_model: type[BaseModel]
    ) -> BaseModel:
        
        # Prepend system prompt to the conversation history
        full_history = [{"role": "system", "content": system_prompt}] + messages

        if provider == "openai":
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=full_history,
                response_format={"type": "json_object"},
                temperature=0.2
            )
            data = json.loads(response.choices[0].message.content)
            return response_model(**data)

        elif provider == "gemini":
            print("Gemini selected but utilizing OpenAI fallback for Graph consistency for now.")
            return await LLMFactory.generate_plan("openai", system_prompt, messages, response_model)
            
        elif provider == "anthropic":
            print("Anthropic selected but utilizing OpenAI fallback for Graph consistency for now.")
            return await LLMFactory.generate_plan("openai", system_prompt, messages, response_model)

        else:
            raise ValueError(f"Unknown provider: {provider}")


class DirectorAgent:
    """The AI Architect that converts user intent into a Node Graph."""

    SYSTEM_PROMPT = """You are the AI Director for a Video Creation Studio.
    Your goal is to architect a workflow (a Graph of Nodes) to solve the user's request.

    AVAILABLE NODE TYPES (Strictly use these keys):

    **SPECIALIZED WORKFLOW NODES (Use these for high-quality Brand Video production):**
    1. `brand`: Brand Identity Selector.
    2. `trend`: Trend Research & Analysis Agent.
    3. `inspiration`: Visual Style & Reference Manager.
    4. `strategy`: Story Strategy Engine (Hook/Angle/CTA).
    5. `story`: Scriptwriting & Narrative Agent.
    6. `beat`: Story Beat Manager (Splits script into scenes).
       - connects to -> `beatImage` (Image Gen for this beat)
       - connects to -> `beatVideo` (Video Gen for this beat)
    7. `composition`: Final Video Assembler (Stitches clips + Audio).
    8. `render`: Export & Rendering Unit.

    **ATOMIC NODES (Use these for generic/custom tasks):**
    9. `atomic_input`: For URL/Text/File input.
       - data: { "inputType": "url" | "text", "label": "Source" }
    10. `atomic_llm`: For any AI text processing (Summary, Script, Strategy).
       - data: { "role": "Summarizer", "systemPrompt": "Summarize this..." }
    11. `atomic_video`: For video generation.
       - data: { "aspectRatio": "9:16", "duration": 15 }

    RULES:
    - If the user asks for a "Brand Video", "Promo", or "Social Media Ad", PREFER the Specialized Nodes sequence:
      `brand` -> `trend` -> `inspiration` -> `strategy` -> `story` -> `beat` -> [`beatImage` -> `beatVideo`] (for each beat) -> `composition` -> `render`.
    - Use `atomic_llm` for intermediate steps if the specialized nodes don't fit.
    - Connect nodes logically (Edge source -> target).
    - ADAPT to the user's latest message while keeping previous context in mind.

    RETURN JSON format matching the GraphPlan schema:
    {
      "nodes": [...],
      "edges": [...],
      "narrative": "Explanation..."
    }
    """

    def __init__(self):
        pass

    async def create_plan(self, messages: list[dict], model_provider: ModelProvider = "openai") -> GraphPlan:
        """Generates a workflow graph based on the chat history."""
        
        print(f"[Director] Processing {len(messages)} messages using {model_provider}...")
        
        try:
            plan = await LLMFactory.generate_plan(
                provider=model_provider,
                system_prompt=self.SYSTEM_PROMPT,
                messages=messages,
                response_model=GraphPlan
            )
            return plan
        except Exception as e:
            print(f"[Director] Error: {e}")
            return GraphPlan(
                nodes=[], 
                edges=[], 
                narrative=f"Failed to generate plan: {str(e)}"
            )
