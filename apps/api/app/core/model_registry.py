"""
Model Registry — Single source of truth for featured image, video, and audio models on fal.ai.

Every entry exposes a `model_endpoint_id` (fal endpoint id, e.g. "fal-ai/veo3.1") plus an
`endpoints` map for sub-capabilities (t2v / i2v / t2i / tts / music / sfx / lipsync).
Prices in `fallback_price` are reference-only — live pricing comes from FalPricingService
(cached in MongoDB `fal_pricing` collection) and billing uses the live figure when available.

──────────────────────────────────────────────────────────────────────────────
LINEUP  (16 image/video + 5 audio = 21 fal endpoints)

  Images     Pro                        Cost
  ────────   ─────────────────────────  ─────────────────────────
  Google     nano-banana-pro            nano-banana-2
  OpenAI     gpt-image-1.5              gpt-image-1-mini
  Kling      kling-image/o3             kling-image/v3
  Bytedance  seedream/v4.5              seedream/v5/lite

  Videos     Pro                        Cost
  ────────   ─────────────────────────  ─────────────────────────
  Google     veo3.1                     veo3.1/fast
  OpenAI     sora-2/.../pro             sora-2
  Kling      kling-video/v3/pro         kling-video/v3/standard
  Bytedance  seedance-2.0               seedance-2.0/fast

  Audio
  ─────
  TTS (pro)      elevenlabs/tts/eleven-v3
  TTS (cost)     minimax/speech-2.8-turbo
  Music          elevenlabs/music
  SFX            elevenlabs/sound-effects/v2
  Lipsync        kling-video/lipsync/audio-to-video
──────────────────────────────────────────────────────────────────────────────
"""

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Image models (8)
# ---------------------------------------------------------------------------
IMAGE_MODELS: List[Dict[str, Any]] = [
    # ── Google ─────────────────────────────────────────────────
    {
        "id": "nano-banana-pro",
        "name": "Nano Banana Pro",
        "provider": "Google",
        "type": "image",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/nano-banana-pro",
        "endpoints": {"t2i": "fal-ai/nano-banana-pro", "i2i": "fal-ai/nano-banana-pro/edit"},
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1:1",  "label": "1024×1024 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.08},
            {"id": "16:9", "label": "1408×768 (16:9)",  "aspect_ratio": "16:9", "est_price_usd": 0.08},
            {"id": "9:16", "label": "768×1408 (9:16)",  "aspect_ratio": "9:16", "est_price_usd": 0.08},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.08},
    },
    {
        "id": "nano-banana-2",
        "name": "Nano Banana 2",
        "provider": "Google",
        "type": "image",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/nano-banana-2",
        "endpoints": {"t2i": "fal-ai/nano-banana-2", "i2i": "fal-ai/nano-banana-2/edit"},
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1:1",  "label": "1024×1024 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.04},
            {"id": "16:9", "label": "1408×768 (16:9)",  "aspect_ratio": "16:9", "est_price_usd": 0.04},
            {"id": "9:16", "label": "768×1408 (9:16)",  "aspect_ratio": "9:16", "est_price_usd": 0.04},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.04},
    },
    # ── OpenAI ─────────────────────────────────────────────────
    {
        "id": "gpt-image-1-5",
        "name": "GPT Image 1.5",
        "provider": "OpenAI",
        "type": "image",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/gpt-image-1.5",
        "endpoints": {
            "t2i": "fal-ai/gpt-image-1.5",
            "i2i": "fal-ai/gpt-image-1.5/edit-image",
        },
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1:1",  "label": "1024×1024 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.05},
            {"id": "16:9", "label": "1536×1024 (16:9)", "aspect_ratio": "16:9", "est_price_usd": 0.05},
            {"id": "9:16", "label": "1024×1536 (9:16)", "aspect_ratio": "9:16", "est_price_usd": 0.05},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.05},
    },
    {
        "id": "gpt-image-1-mini",
        "name": "GPT Image 1 Mini",
        "provider": "OpenAI",
        "type": "image",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/gpt-image-1-mini",
        "endpoints": {"t2i": "fal-ai/gpt-image-1-mini"},
        "capabilities": ["t2i"],
        "configs": [
            {"id": "1:1",  "label": "1024×1024 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.012},
            {"id": "16:9", "label": "1536×1024 (16:9)", "aspect_ratio": "16:9", "est_price_usd": 0.012},
            {"id": "9:16", "label": "1024×1536 (9:16)", "aspect_ratio": "9:16", "est_price_usd": 0.012},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.012},
    },
    # ── Kling ──────────────────────────────────────────────────
    {
        "id": "kling-image-o3",
        "name": "Kling Image O3",
        "provider": "KlingAI",
        "type": "image",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/kling-image/o3/text-to-image",
        "endpoints": {
            "t2i": "fal-ai/kling-image/o3/text-to-image",
            "i2i": "fal-ai/kling-image/o3/image-to-image",
        },
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1:1",  "label": "1024×1024 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.028},
            {"id": "16:9", "label": "1360×768 (16:9)",  "aspect_ratio": "16:9", "est_price_usd": 0.028},
            {"id": "9:16", "label": "768×1360 (9:16)",  "aspect_ratio": "9:16", "est_price_usd": 0.028},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.028},
    },
    {
        "id": "kling-image-v3",
        "name": "Kling Image v3",
        "provider": "KlingAI",
        "type": "image",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/kling-image/v3/text-to-image",
        "endpoints": {
            "t2i": "fal-ai/kling-image/v3/text-to-image",
            "i2i": "fal-ai/kling-image/v3/image-to-image",
        },
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1:1",  "label": "1024×1024 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.015},
            {"id": "16:9", "label": "1360×768 (16:9)",  "aspect_ratio": "16:9", "est_price_usd": 0.015},
            {"id": "9:16", "label": "768×1360 (9:16)",  "aspect_ratio": "9:16", "est_price_usd": 0.015},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.015},
    },
    # ── Bytedance ──────────────────────────────────────────────
    {
        "id": "seedream-v4-5",
        "name": "Seedream v4.5",
        "provider": "ByteDance",
        "type": "image",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/bytedance/seedream/v4.5/text-to-image",
        "endpoints": {
            "t2i": "fal-ai/bytedance/seedream/v4.5/text-to-image",
            "i2i": "fal-ai/bytedance/seedream/v4.5/image-to-image",
        },
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1:1",  "label": "2048×2048 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.03},
            {"id": "16:9", "label": "2560×1440 (16:9)", "aspect_ratio": "16:9", "est_price_usd": 0.03},
            {"id": "9:16", "label": "1440×2560 (9:16)", "aspect_ratio": "9:16", "est_price_usd": 0.03},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.03},
    },
    {
        "id": "seedream-v5-lite",
        "name": "Seedream v5 Lite",
        "provider": "ByteDance",
        "type": "image",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/bytedance/seedream/v5/lite/text-to-image",
        "endpoints": {"t2i": "fal-ai/bytedance/seedream/v5/lite/text-to-image"},
        "capabilities": ["t2i"],
        "configs": [
            {"id": "1:1",  "label": "1024×1024 (1:1)",  "aspect_ratio": "1:1",  "est_price_usd": 0.015},
            {"id": "16:9", "label": "1344×768 (16:9)",  "aspect_ratio": "16:9", "est_price_usd": 0.015},
            {"id": "9:16", "label": "768×1344 (9:16)",  "aspect_ratio": "9:16", "est_price_usd": 0.015},
        ],
        "default_config_id": "1:1",
        "fallback_price": {"per_run": 0.015},
    },
]


# ---------------------------------------------------------------------------
# Video models (8 — each with t2v + i2v endpoints)
# ---------------------------------------------------------------------------
VIDEO_MODELS: List[Dict[str, Any]] = [
    # ── Google ─────────────────────────────────────────────────
    {
        "id": "veo-3-1",
        "name": "Veo 3.1",
        "provider": "Google",
        "type": "video",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/veo3.1",
        "endpoints": {
            "t2v": "fal-ai/veo3.1",
            "i2v": "fal-ai/veo3.1/image-to-video",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-8s",  "label": "720p / 8s",  "resolution": "720p",  "duration": 8, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 3.20},
            {"id": "1080p-8s", "label": "1080p / 8s", "resolution": "1080p", "duration": 8, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 4.00},
        ],
        "default_config_id": "720p-8s",
        "fallback_price": {"per_run": 3.20},
    },
    {
        "id": "veo-3-1-fast",
        "name": "Veo 3.1 Fast",
        "provider": "Google",
        "type": "video",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/veo3.1/fast",
        "endpoints": {
            "t2v": "fal-ai/veo3.1/fast",
            "i2v": "fal-ai/veo3.1/fast/image-to-video",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-8s", "label": "720p / 8s", "resolution": "720p", "duration": 8, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 1.60},
            {"id": "720p-4s", "label": "720p / 4s", "resolution": "720p", "duration": 4, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 0.80},
        ],
        "default_config_id": "720p-8s",
        "fallback_price": {"per_run": 1.60},
    },
    # ── OpenAI (Sora) ──────────────────────────────────────────
    {
        "id": "sora-2-pro",
        "name": "Sora 2 Pro",
        "provider": "OpenAI",
        "type": "video",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/sora-2/text-to-video/pro",
        "endpoints": {
            "t2v": "fal-ai/sora-2/text-to-video/pro",
            "i2v": "fal-ai/sora-2/image-to-video/pro",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-8s",  "label": "720p / 8s",  "resolution": "720p",  "duration": 8,  "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 2.40},
            {"id": "1080p-8s", "label": "1080p / 8s", "resolution": "1080p", "duration": 8,  "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 4.00},
        ],
        "default_config_id": "720p-8s",
        "fallback_price": {"per_run": 2.40},
    },
    {
        "id": "sora-2",
        "name": "Sora 2",
        "provider": "OpenAI",
        "type": "video",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/sora-2/text-to-video",
        "endpoints": {
            "t2v": "fal-ai/sora-2/text-to-video",
            "i2v": "fal-ai/sora-2/image-to-video",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-8s",  "label": "720p / 8s",  "resolution": "720p",  "duration": 8, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 1.20},
            {"id": "720p-4s",  "label": "720p / 4s",  "resolution": "720p",  "duration": 4, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 0.60},
        ],
        "default_config_id": "720p-8s",
        "fallback_price": {"per_run": 1.20},
    },
    # ── Kling ──────────────────────────────────────────────────
    {
        "id": "kling-video-v3-pro",
        "name": "Kling Video v3 Pro",
        "provider": "KlingAI",
        "type": "video",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/kling-video/v3/pro/text-to-video",
        "endpoints": {
            "t2v": "fal-ai/kling-video/v3/pro/text-to-video",
            "i2v": "fal-ai/kling-video/v3/pro/image-to-video",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "1080p-5s",  "label": "1080p / 5s",  "resolution": "1080p", "duration": 5,  "aspect_ratios": ["16:9", "9:16", "1:1"], "est_price_usd": 1.40},
            {"id": "1080p-10s", "label": "1080p / 10s", "resolution": "1080p", "duration": 10, "aspect_ratios": ["16:9", "9:16", "1:1"], "est_price_usd": 2.80},
        ],
        "default_config_id": "1080p-5s",
        "fallback_price": {"per_run": 1.40},
    },
    {
        "id": "kling-video-v3-standard",
        "name": "Kling Video v3 Standard",
        "provider": "KlingAI",
        "type": "video",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/kling-video/v3/standard/text-to-video",
        "endpoints": {
            "t2v": "fal-ai/kling-video/v3/standard/text-to-video",
            "i2v": "fal-ai/kling-video/v3/standard/image-to-video",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-5s",  "label": "720p / 5s",  "resolution": "720p", "duration": 5,  "aspect_ratios": ["16:9", "9:16", "1:1"], "est_price_usd": 0.35},
            {"id": "720p-10s", "label": "720p / 10s", "resolution": "720p", "duration": 10, "aspect_ratios": ["16:9", "9:16", "1:1"], "est_price_usd": 0.70},
        ],
        "default_config_id": "720p-5s",
        "fallback_price": {"per_run": 0.35},
    },
    # ── ByteDance Seedance ─────────────────────────────────────
    {
        "id": "seedance-2-0",
        "name": "Seedance 2.0",
        "provider": "ByteDance",
        "type": "video",
        "tier": "pro",
        "model_endpoint_id": "bytedance/seedance-2.0/text-to-video",
        "endpoints": {
            "t2v": "bytedance/seedance-2.0/text-to-video",
            "i2v": "bytedance/seedance-2.0/image-to-video",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "1080p-5s",  "label": "1080p / 5s",  "resolution": "1080p", "duration": 5,  "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 1.00},
            {"id": "1080p-10s", "label": "1080p / 10s", "resolution": "1080p", "duration": 10, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 2.00},
        ],
        "default_config_id": "1080p-5s",
        "fallback_price": {"per_run": 1.00},
    },
    {
        "id": "seedance-2-0-fast",
        "name": "Seedance 2.0 Fast",
        "provider": "ByteDance",
        "type": "video",
        "tier": "cost",
        "model_endpoint_id": "bytedance/seedance-2.0/fast/text-to-video",
        "endpoints": {
            "t2v": "bytedance/seedance-2.0/fast/text-to-video",
            "i2v": "bytedance/seedance-2.0/fast/image-to-video",
        },
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-5s",  "label": "720p / 5s",  "resolution": "720p", "duration": 5,  "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 0.35},
            {"id": "720p-10s", "label": "720p / 10s", "resolution": "720p", "duration": 10, "aspect_ratios": ["16:9", "9:16"], "est_price_usd": 0.70},
        ],
        "default_config_id": "720p-5s",
        "fallback_price": {"per_run": 0.35},
    },
]


# ---------------------------------------------------------------------------
# Audio models (5)
# ---------------------------------------------------------------------------
AUDIO_MODELS: List[Dict[str, Any]] = [
    # ── Text-to-Speech ─────────────────────────────────────────
    {
        "id": "eleven-v3",
        "name": "Eleven v3",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "tts",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/elevenlabs/tts/eleven-v3",
        "endpoints": {"tts": "fal-ai/elevenlabs/tts/eleven-v3"},
        "capabilities": ["tts"],
        "configs": [
            {"id": "default", "label": "HD Quality", "pricing_note": "$0.10/1K chars",
             "est_price_usd_per_1k_chars": 0.10},
        ],
        "default_config_id": "default",
        "fallback_price": {"per_1k_chars": 0.10},
    },
    {
        "id": "minimax-speech-2-8-turbo",
        "name": "MiniMax Speech 2.8 Turbo",
        "provider": "MiniMax",
        "type": "audio",
        "category": "tts",
        "tier": "cost",
        "model_endpoint_id": "fal-ai/minimax/speech-2.8-turbo",
        "endpoints": {"tts": "fal-ai/minimax/speech-2.8-turbo"},
        "capabilities": ["tts"],
        "configs": [
            {"id": "default", "label": "Per 1K chars", "pricing_note": "$0.04/1K chars",
             "est_price_usd_per_1k_chars": 0.04},
        ],
        "default_config_id": "default",
        "fallback_price": {"per_1k_chars": 0.04},
    },
    # ── Music ──────────────────────────────────────────────────
    {
        "id": "eleven-music",
        "name": "ElevenLabs Music",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "music",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/elevenlabs/music",
        "endpoints": {"music": "fal-ai/elevenlabs/music"},
        "capabilities": ["t2m"],
        "configs": [
            {"id": "default", "label": "Per minute", "pricing_note": "$0.40/min",
             "est_price_usd_per_min": 0.40},
        ],
        "default_config_id": "default",
        "fallback_price": {"per_min": 0.40},
    },
    # ── Sound Effects ──────────────────────────────────────────
    {
        "id": "eleven-sfx-v2",
        "name": "ElevenLabs Sound Effects v2",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "sfx",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/elevenlabs/sound-effects/v2",
        "endpoints": {"sfx": "fal-ai/elevenlabs/sound-effects/v2"},
        "capabilities": ["t2sfx"],
        "configs": [
            {"id": "default", "label": "Per generation", "est_price_usd": 0.08},
        ],
        "default_config_id": "default",
        "fallback_price": {"per_run": 0.08},
    },
    # ── Lipsync ────────────────────────────────────────────────
    {
        "id": "kling-lipsync",
        "name": "Kling LipSync",
        "provider": "KlingAI",
        "type": "audio",
        "category": "lipsync",
        "tier": "pro",
        "model_endpoint_id": "fal-ai/kling-video/lipsync/audio-to-video",
        "endpoints": {"lipsync": "fal-ai/kling-video/lipsync/audio-to-video"},
        "capabilities": ["lipsync"],
        "configs": [
            {"id": "default", "label": "Per generation", "est_price_usd": 0.60},
        ],
        "default_config_id": "default",
        "fallback_price": {"per_run": 0.60},
    },
]


# ---------------------------------------------------------------------------
# LLM Models (OpenRouter) — for billing tracking only
# ---------------------------------------------------------------------------
LLM_MODELS: List[Dict[str, Any]] = [
    {
        "id": "gemini-3-1-pro",
        "name": "Gemini 3.1 Pro Preview",
        "provider": "Google",
        "type": "llm",
        "tier": "premium",
        "openrouter_id": "google/gemini-3.1-pro-preview",
        "display_name": "Gemini 3.1 Pro Preview (High)",
    },
    {
        "id": "gemini-3-1-flash-lite",
        "name": "Gemini 3.1 Flash Lite Preview",
        "provider": "Google",
        "type": "llm",
        "tier": "budget",
        "openrouter_id": "google/gemini-3.1-flash-lite-preview",
        "display_name": "Gemini 3.1 Flash Lite Preview (Low)",
    },
    {
        "id": "claude-opus-4-6",
        "name": "Claude 4.6 Opus",
        "provider": "Anthropic",
        "type": "llm",
        "tier": "premium",
        "openrouter_id": "anthropic/claude-opus-4.6",
        "display_name": "Claude 4.6 Opus (High)",
    },
    {
        "id": "claude-sonnet-4-6",
        "name": "Claude 4.6 Sonnet",
        "provider": "Anthropic",
        "type": "llm",
        "tier": "mid",
        "openrouter_id": "anthropic/claude-sonnet-4.6",
        "display_name": "Claude 4.6 Sonnet (Medium)",
    },
    {
        "id": "claude-haiku-4-5",
        "name": "Claude 4.5 Haiku",
        "provider": "Anthropic",
        "type": "llm",
        "tier": "budget",
        "openrouter_id": "anthropic/claude-haiku-4.5",
        "display_name": "Claude 4.5 Haiku (Low)",
    },
    {
        "id": "gpt-5-4-pro",
        "name": "GPT-5.4 Pro",
        "provider": "OpenAI",
        "type": "llm",
        "tier": "premium",
        "openrouter_id": "openai/gpt-5.4-pro",
        "display_name": "GPT-5.4 Pro (High)",
    },
    {
        "id": "gpt-5-mini",
        "name": "GPT-5 Mini",
        "provider": "OpenAI",
        "type": "llm",
        "tier": "mid",
        "openrouter_id": "openai/gpt-5-mini",
        "display_name": "GPT-5 Mini (Medium)",
    },
    {
        "id": "gpt-5-nano",
        "name": "GPT-5 Nano",
        "provider": "OpenAI",
        "type": "llm",
        "tier": "budget",
        "openrouter_id": "openai/gpt-5-nano",
        "display_name": "GPT-5 Nano (Low)",
    },
]


# ---------------------------------------------------------------------------
# Combined registry + lookup helpers
# ---------------------------------------------------------------------------
FEATURED_MODELS: List[Dict[str, Any]] = IMAGE_MODELS + VIDEO_MODELS + AUDIO_MODELS + LLM_MODELS

_MODELS_BY_ID: Dict[str, Dict[str, Any]] = {m["id"]: m for m in FEATURED_MODELS}

# Lookup by fal endpoint id (including every sub-endpoint in `endpoints`)
_MODELS_BY_ENDPOINT_ID: Dict[str, Dict[str, Any]] = {}
for _m in FEATURED_MODELS:
    primary = _m.get("model_endpoint_id")
    if primary:
        _MODELS_BY_ENDPOINT_ID[primary] = _m
    for _ep in (_m.get("endpoints") or {}).values():
        if _ep:
            _MODELS_BY_ENDPOINT_ID.setdefault(_ep, _m)

_MODELS_BY_OPENROUTER_ID: Dict[str, Dict[str, Any]] = {
    m["openrouter_id"]: m for m in LLM_MODELS if "openrouter_id" in m
}

_MODELS_BY_DISPLAY_NAME: Dict[str, Dict[str, Any]] = {}
for _m in FEATURED_MODELS:
    _MODELS_BY_DISPLAY_NAME[_m["name"]] = _m
    if "display_name" in _m:
        _MODELS_BY_DISPLAY_NAME[_m["display_name"]] = _m


def get_model_by_id(model_id: str) -> Dict[str, Any] | None:
    """Look up a model by its stable ID (e.g. 'veo-3-1')."""
    return _MODELS_BY_ID.get(model_id)


def get_model_by_endpoint_id(endpoint_id: str) -> Dict[str, Any] | None:
    """Look up a model by any of its fal endpoint ids (primary or sub-capability)."""
    return _MODELS_BY_ENDPOINT_ID.get(endpoint_id)


def get_model_by_openrouter_id(openrouter_id: str) -> Dict[str, Any] | None:
    """Look up an LLM by its OpenRouter ID."""
    return _MODELS_BY_OPENROUTER_ID.get(openrouter_id)


def get_model_by_name(display_name: str) -> Dict[str, Any] | None:
    """Case-insensitive, fuzzy lookup by name / display_name / id."""
    if not display_name:
        return None

    res = _MODELS_BY_DISPLAY_NAME.get(display_name)
    if res:
        return res

    lower_target = display_name.lower().strip()
    for m in FEATURED_MODELS:
        name_lower = m.get("name", "").lower()
        if lower_target == name_lower:
            return m
        disp_lower = m.get("display_name", "").lower()
        if disp_lower and lower_target == disp_lower:
            return m
        id_lower = m.get("id", "").lower()
        if lower_target == id_lower or lower_target.replace(" ", "-") == id_lower:
            return m
        if lower_target.replace("-", " ") == name_lower.replace("-", " "):
            return m
    return None


def resolve_endpoint_id(
    model_input: str | None,
    fallback_endpoint_id: str,
    model_type: str | None = None,
    capability: str | None = None,
) -> str:
    """Resolve any model identifier to a fal endpoint id.

    Accepts:
      - Stable id       (e.g. "veo-3-1")
      - Display name    (e.g. "Veo 3.1")
      - fal endpoint id (e.g. "fal-ai/veo3.1") — returned as-is after validation

    When *capability* is provided (e.g. "i2v"), returns the endpoint id for that
    sub-capability from the matched model's `endpoints` map, falling back to the
    primary `model_endpoint_id`.

    Returns *fallback_endpoint_id* if nothing matches.
    """
    if not model_input:
        return fallback_endpoint_id

    entry: Dict[str, Any] | None = None

    # Direct fal endpoint id match
    if model_input.startswith("fal-ai/") or "/" in model_input:
        entry = _MODELS_BY_ENDPOINT_ID.get(model_input)
        if not entry:
            # Unknown but looks like a fal endpoint — return as-is
            return model_input

    # Stable-ID match
    if entry is None:
        candidate = _MODELS_BY_ID.get(model_input)
        if candidate and (model_type is None or candidate.get("type") == model_type):
            entry = candidate

    # Display-name fuzzy match
    if entry is None:
        candidate = get_model_by_name(model_input)
        if candidate and (model_type is None or candidate.get("type") == model_type):
            entry = candidate

    if entry is None:
        print(
            f"[ModelRegistry] ⚠️ Could not resolve '{model_input}' → fal endpoint; "
            f"using fallback '{fallback_endpoint_id}'"
        )
        return fallback_endpoint_id

    if capability:
        ep = (entry.get("endpoints") or {}).get(capability)
        if ep:
            return ep
    return entry.get("model_endpoint_id") or fallback_endpoint_id


def get_models_for_api() -> List[Dict[str, Any]]:
    """Return the full model registry formatted for the /billing/models API endpoint."""
    return FEATURED_MODELS
