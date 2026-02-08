"""LLM Service - Unified interface for text generation with streaming support."""

import os
from typing import Optional, AsyncGenerator, List, Dict, Any

from google import genai
from openai import AsyncOpenAI

from app.core.config import settings


class LLMService:
    """Unified LLM service supporting OpenAI, Anthropic (Claude), and Gemini."""

    MODELS = {
        "openai": "gpt-4o",
        "claude": "claude-sonnet-4-20250514",
        "gemini": "gemini-2.5-flash",
    }

    def __init__(self, provider: str = "openai"):
        """
        Initialize LLM service.
        
        Args:
            provider: "openai", "claude", or "gemini"
        """
        self.provider = provider
        self.model = self.MODELS.get(provider, self.MODELS["openai"])
        
        if provider == "openai":
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        elif provider == "claude":
            # Lazy import anthropic to avoid dependency issues if not installed
            try:
                import anthropic
                self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        else:  # gemini
            if settings.gemini_api_key:
                os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
            self.client = genai.Client()

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_response: bool = False,
    ) -> str:
        """
        Generate text completion (non-streaming).
        
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
        elif self.provider == "claude":
            return await self._generate_claude(prompt, system_prompt, temperature, json_response)
        else:
            return await self._generate_gemini(prompt, system_prompt, temperature, json_response)

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream text generation for real-time output.
        
        Yields:
            Text chunks as they are generated
        """
        if self.provider == "openai":
            async for chunk in self._stream_openai(prompt, system_prompt, temperature):
                yield chunk
        elif self.provider == "claude":
            async for chunk in self._stream_claude(prompt, system_prompt, temperature):
                yield chunk
        else:
            async for chunk in self._stream_gemini(prompt, system_prompt, temperature):
                yield chunk

    # ============================================
    # OpenAI Implementation
    # ============================================

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
        
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if json_response:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def _stream_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using OpenAI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # ============================================
    # Claude (Anthropic) Implementation
    # ============================================

    async def _generate_claude(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        json_response: bool,
    ) -> str:
        """Generate using Claude."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 8192,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        response = await self.client.messages.create(**kwargs)
        return response.content[0].text if response.content else ""

    async def _stream_claude(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using Claude."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 8192,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    # ============================================
    # Gemini Implementation
    # ============================================

    async def _generate_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        json_response: bool,
    ) -> str:
        """Generate using Gemini."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        config: Dict[str, Any] = {"temperature": temperature}
        if json_response:
            config["response_mime_type"] = "application/json"
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=config,
        )
        return response.text or ""

    async def _stream_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using Gemini."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Gemini SDK streaming
        response = self.client.models.generate_content_stream(
            model=self.model,
            contents=full_prompt,
            config={"temperature": temperature},
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text


def get_llm(provider: str = "openai") -> LLMService:
    """Get LLM service instance."""
    return LLMService(provider=provider)
