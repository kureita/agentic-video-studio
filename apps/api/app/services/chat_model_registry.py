"""Shared chat model registry for OpenRouter-backed assistants."""

from typing import Any, Dict, List, Optional


CHAT_MODELS: List[Dict[str, Any]] = [
    {
        "display_name": "Gemini 3.1 Pro Preview (High)",
        "openrouter_model": "google/gemini-3.1-pro-preview",
        "fallback_input_modalities": ["text", "image"],
    },
    {
        "display_name": "Gemini 3.1 Flash Lite Preview (Low)",
        "openrouter_model": "google/gemini-3.1-flash-lite-preview",
        "fallback_input_modalities": ["text", "image"],
    },
    {
        "display_name": "Claude 4.6 Opus (High)",
        "openrouter_model": "anthropic/claude-opus-4.6",
        "fallback_input_modalities": ["text", "image"],
    },
    {
        "display_name": "Claude 4.6 Sonnet (Medium)",
        "openrouter_model": "anthropic/claude-sonnet-4.6",
        "fallback_input_modalities": ["text", "image"],
    },
    {
        "display_name": "Claude 4.5 Haiku (Low)",
        "openrouter_model": "anthropic/claude-haiku-4.5",
        "fallback_input_modalities": ["text", "image"],
    },
    {
        "display_name": "GPT-5.4 Pro (High)",
        "openrouter_model": "openai/gpt-5.4-pro",
        "fallback_input_modalities": ["text", "image"],
    },
    {
        "display_name": "GPT-5 Mini (Medium)",
        "openrouter_model": "openai/gpt-5-mini",
        "fallback_input_modalities": ["text", "image", "audio"],
    },
    {
        "display_name": "GPT-5 Nano (Low)",
        "openrouter_model": "openai/gpt-5-nano",
        "fallback_input_modalities": ["text", "image"],
    },
]


def get_chat_model_by_display_name(display_name: str) -> Optional[Dict[str, Any]]:
    for model in CHAT_MODELS:
        if model.get("display_name") == display_name:
            return model
    return None


def get_chat_model_by_openrouter_id(model_id: str) -> Optional[Dict[str, Any]]:
    for model in CHAT_MODELS:
        if model.get("openrouter_model") == model_id:
            return model
    return None
