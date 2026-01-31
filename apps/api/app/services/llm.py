"""LLM Service - Unified interface for text generation."""

import os
from typing import Optional

from google import genai
from openai import AsyncOpenAI

from app.core.config import settings


class LLMService:
    """Unified LLM service supporting both OpenAI and Gemini."""

    def __init__(self, provider: str = "openai"):
        """
        Initialize LLM service.
        
        Args:
            provider: "openai" or "gemini"
        """
        self.provider = provider
        
        if provider == "openai":
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4o"
        else:
            # Set API key for Gemini SDK
            if settings.gemini_api_key:
                os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
            self.client = genai.Client()
            self.model = "gemini-2.5-flash"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_response: bool = False,
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            temperature: Creativity level (0-1)
            json_response: Whether to request JSON output
            
        Returns:
            Generated text
        """
        if self.provider == "openai":
            return await self._generate_openai(prompt, system_prompt, temperature, json_response)
        else:
            return await self._generate_gemini(prompt, system_prompt, temperature)

    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        json_response: bool,
    ) -> str:
        """Generate using OpenAI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if json_response:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def _generate_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
    ) -> str:
        """Generate using Gemini."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config={
                "temperature": temperature,
            },
        )
        return response.text


def get_llm(provider: str = "openai") -> LLMService:
    """Get LLM service instance."""
    return LLMService(provider=provider)

