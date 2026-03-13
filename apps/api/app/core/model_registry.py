"""
Model Registry — Single source of truth for all featured image, video, and audio models.

Used by both the API (for billing, model selection) and exposed to the UI via /billing/models.
Pricing here is for reference/estimation only — actual cost comes from Runware's `includeCost`
response and is what gets billed to the user.
"""

from typing import Dict, List, Any


# ---------------------------------------------------------------------------
# Featured Image Models (13)
# ---------------------------------------------------------------------------
IMAGE_MODELS: List[Dict[str, Any]] = [
    # ── Premium ────────────────────────────────────────────────
    {
        "id": "gpt-image-1",
        "name": "GPT Image 1",
        "provider": "OpenAI",
        "type": "image",
        "tier": "premium",
        "air_id": "openai:1@1",
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "default", "label": "Standard", "width": 1024, "height": 1024, "est_price_usd": 0.05},
        ],
        "default_config_id": "default",
    },
    {
        "id": "dalle-3",
        "name": "DALL-E 3",
        "provider": "OpenAI",
        "type": "image",
        "tier": "premium",
        "air_id": "openai:2@3",
        "capabilities": ["t2i"],
        "configs": [
            {"id": "1024x1024", "label": "Square (1024x1024)", "width": 1024, "height": 1024, "est_price_usd": 0.08},
            {"id": "1792x1024", "label": "Wide (1792x1024)", "width": 1792, "height": 1024, "est_price_usd": 0.12},
            {"id": "1024x1792", "label": "Tall (1024x1792)", "width": 1024, "height": 1792, "est_price_usd": 0.12},
        ],
        "default_config_id": "1024x1024",
    },
    {
        "id": "flux-2-max",
        "name": "FLUX.2 [max]",
        "provider": "Black Forest Labs",
        "type": "image",
        "tier": "premium",
        "air_id": "bfl:flux-2@max",
        "capabilities": ["t2i", "i2i", "reference"],
        "configs": [
            {"id": "1mp",   "label": "1 MP (1024×1024)", "width": 1024, "height": 1024, "est_price_usd": 0.07},
            {"id": "1.5mp", "label": "1.5 MP (1280×1152)", "width": 1280, "height": 1152, "est_price_usd": 0.10},
            {"id": "1.5mp-alt", "label": "1.5 MP (1152×1280)", "width": 1152, "height": 1280, "est_price_usd": 0.10},
            {"id": "2mp",   "label": "2 MP (1536×1280)",  "width": 1536, "height": 1280, "est_price_usd": 0.13},
            {"id": "2.5mp", "label": "2.5 MP (1792×1408)", "width": 1792, "height": 1408, "est_price_usd": 0.16},
            {"id": "2.5mp-alt", "label": "2.5 MP (1408×1792)", "width": 1408, "height": 1792, "est_price_usd": 0.16},
        ],
        "default_config_id": "1mp",
    },
    {
        "id": "nano-banana-2",
        "name": "Nano Banana 2",
        "provider": "Banana Labs",
        "type": "image",
        "tier": "premium",
        "air_id": "banana:nano@2",
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1mp-sq",   "label": "1 MP (1024×1024)",     "width": 1024, "height": 1024, "est_price_usd": 0.047},
            {"id": "1mp-land", "label": "1 MP (1376×768)",      "width": 1376, "height": 768,  "est_price_usd": 0.047},
            {"id": "1mp-port", "label": "1 MP (768×1376)",      "width": 768,  "height": 1376, "est_price_usd": 0.047},
            {"id": "2mp-sq",   "label": "2 MP (2048×2048)",     "width": 2048, "height": 2048, "est_price_usd": 0.103},
        ],
        "default_config_id": "1mp-sq",
    },

    # ── Mid-Range ──────────────────────────────────────────────
    {
        "id": "kling-image-o3",
        "name": "Kling IMAGE O3",
        "provider": "KlingAI",
        "type": "image",
        "tier": "mid",
        "air_id": "klingai:kling-image@o3",
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1024x1024", "label": "1024×1024", "width": 1024, "height": 1024, "est_price_usd": 0.028},
            {"id": "1360x768",  "label": "1360×768 (16:9)", "width": 1360, "height": 768, "est_price_usd": 0.028},
            {"id": "768x1360",  "label": "768×1360 (9:16)", "width": 768, "height": 1360, "est_price_usd": 0.028},
            {"id": "2048x2048", "label": "2048×2048", "width": 2048, "height": 2048, "est_price_usd": 0.056},
        ],
        "default_config_id": "1024x1024",
    },
    {
        "id": "seedream-5-lite",
        "name": "Seedream 5.0 Lite",
        "provider": "ByteDance",
        "type": "image",
        "tier": "mid",
        "air_id": "bytedance:seedream@5.0-lite",
        "capabilities": ["t2i"],
        "configs": [
            {"id": "default", "label": "Up to 3K res", "width": 1024, "height": 1024, "est_price_usd": 0.035},
        ],
        "default_config_id": "default",
    },
    {
        "id": "recraft-v4",
        "name": "Recraft V4",
        "provider": "Recraft",
        "type": "image",
        "tier": "mid",
        "air_id": "recraft:v4@0",
        "capabilities": ["t2i", "i2i", "vector", "svg"],
        "configs": [
            {"id": "default", "label": "Standard", "width": 1024, "height": 1024, "est_price_usd": 0.04},
        ],
        "default_config_id": "default",
    },
    {
        "id": "recraft-v4-pro",
        "name": "Recraft V4 Pro",
        "provider": "Recraft",
        "type": "image",
        "tier": "premium",
        "air_id": "recraft:v4-pro@0",
        "capabilities": ["t2i", "i2i", "vector", "svg"],
        "configs": [
            {"id": "default", "label": "Standard", "width": 1024, "height": 1024, "est_price_usd": 0.25},
        ],
        "default_config_id": "default",
    },
    {
        "id": "grok-imagine-image",
        "name": "Grok Imagine Image",
        "provider": "xAI",
        "type": "image",
        "tier": "mid",
        "air_id": "xai:grok-imagine@image",
        "capabilities": ["t2i"],
        "configs": [
            {"id": "1024x1024", "label": "1024×1024", "width": 1024, "height": 1024, "est_price_usd": 0.02},
            {"id": "1024x1536", "label": "1024×1536", "width": 1024, "height": 1536, "est_price_usd": 0.022},
        ],
        "default_config_id": "1024x1024",
    },
    {
        "id": "imagen-4-ultra",
        "name": "Imagen 4 Ultra",
        "provider": "Google",
        "type": "image",
        "tier": "mid",
        "air_id": "google:2@2",
        "capabilities": ["t2i"],
        "configs": [
            {"id": "default", "label": "Standard", "width": 1024, "height": 1024, "est_price_usd": 0.06},
        ],
        "default_config_id": "default",
    },
    {
        "id": "imagen-4-preview",
        "name": "Imagen 4 Preview",
        "provider": "Google",
        "type": "image",
        "tier": "mid",
        "air_id": "google:2@1",
        "capabilities": ["t2i"],
        "configs": [
            {"id": "default", "label": "Standard", "width": 1024, "height": 1024, "est_price_usd": 0.04},
        ],
        "default_config_id": "default",
    },

    # ── Budget ─────────────────────────────────────────────────
    {
        "id": "flux-2-dev",
        "name": "FLUX.2 [dev]",
        "provider": "Black Forest Labs",
        "type": "image",
        "tier": "budget",
        "air_id": "bfl:flux-2@dev",
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {"id": "1mp",   "label": "1 MP (1024×1024)",   "width": 1024, "height": 1024, "est_price_usd": 0.005},
            {"id": "2mp",   "label": "2 MP (1536×1280)",   "width": 1536, "height": 1280, "est_price_usd": 0.008},
        ],
        "default_config_id": "1mp",
    },
    {
        "id": "flux-2-flex",
        "name": "FLUX.2 [flex]",
        "provider": "Black Forest Labs",
        "type": "image",
        "tier": "mid",
        "air_id": "bfl:flux-2@flex",
        "capabilities": ["t2i", "i2i", "reference", "fill"],
        "configs": [
            {"id": "default", "label": "Standard", "width": 1024, "height": 1024, "est_price_usd": 0.06},
        ],
        "default_config_id": "default",
    },
    {
        "id": "flux-2-klein-9b",
        "name": "FLUX.2 [klein] 9B",
        "provider": "Black Forest Labs",
        "type": "image",
        "tier": "budget",
        "air_id": "bfl:flux-2@klein-9b",
        "capabilities": ["t2i"],
        "configs": [
            {"id": "default", "label": "Standard", "width": 1024, "height": 1024, "est_price_usd": 0.00078},
        ],
        "default_config_id": "default",
    },
]


# ---------------------------------------------------------------------------
# Featured Video Models (14)
# ---------------------------------------------------------------------------
VIDEO_MODELS: List[Dict[str, Any]] = [
    # ── Premium ────────────────────────────────────────────────
    {
        "id": "veo-3-1",
        "name": "Google Veo 3.1",
        "provider": "Google",
        "type": "video",
        "tier": "premium",
        "air_id": "google:3@2",
        "capabilities": ["t2v", "audio"],
        "configs": [
            {"id": "720p-4s-audio",  "label": "720p · 4s · Audio",   "resolution": "720p",  "duration": 4,  "audio": True,  "est_price_usd": 0.80},
            {"id": "720p-8s-audio",  "label": "720p · 8s · Audio",   "resolution": "720p",  "duration": 8,  "audio": True,  "est_price_usd": 1.60},
            {"id": "4k-4s-audio",    "label": "4K · 4s · Audio",     "resolution": "4k",    "duration": 4,  "audio": True,  "est_price_usd": 1.60},
            {"id": "4k-8s-audio",    "label": "4K · 8s · Audio",     "resolution": "4k",    "duration": 8,  "audio": True,  "est_price_usd": 3.20},
            {"id": "4k-4s-noaudio",  "label": "4K · 4s · No Audio",  "resolution": "4k",    "duration": 4,  "audio": False, "est_price_usd": 3.20},
            {"id": "4k-8s-noaudio",  "label": "4K · 8s · No Audio",  "resolution": "4k",    "duration": 8,  "audio": False, "est_price_usd": 4.80},
        ],
        "default_config_id": "720p-8s-audio",
    },
    {
        "id": "veo-3-1-fast",
        "name": "Google Veo 3.1 Fast",
        "provider": "Google",
        "type": "video",
        "tier": "premium",
        "air_id": "google:3@3",
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-4s",  "label": "720p · 4s",  "resolution": "720p", "duration": 4, "audio": True, "est_price_usd": 0.80},
            {"id": "720p-8s",  "label": "720p · 8s",  "resolution": "720p", "duration": 8, "audio": True, "est_price_usd": 1.20},
            {"id": "4k-4s",    "label": "4K · 4s",    "resolution": "4k",   "duration": 4, "audio": True, "est_price_usd": 2.40},
            {"id": "4k-8s",    "label": "4K · 8s",    "resolution": "4k",   "duration": 8, "audio": True, "est_price_usd": 2.80},
        ],
        "default_config_id": "720p-8s",
    },
    {
        "id": "sora-2-pro",
        "name": "Sora 2 Pro",
        "provider": "OpenAI",
        "type": "video",
        "tier": "premium",
        "air_id": "openai:sora@2-pro",
        "capabilities": ["t2v", "i2v", "audio"],
        "configs": [
            {"id": "720p-8s",  "label": "720p · 8s",  "resolution": "720p", "duration": 8, "audio": True, "est_price_usd": 2.40},
            {"id": "1080p-8s", "label": "1080p · 8s", "resolution": "1080p", "duration": 8, "audio": True, "est_price_usd": 4.00},
        ],
        "default_config_id": "720p-8s",
    },
    {
        "id": "sora-2",
        "name": "Sora 2",
        "provider": "OpenAI",
        "type": "video",
        "tier": "premium",
        "air_id": "openai:sora@2",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-5s",  "label": "720p · 5s",  "resolution": "720p", "duration": 5, "est_price_usd": 0.80},
        ],
        "default_config_id": "720p-5s",
    },

    # ── Mid-Range ──────────────────────────────────────────────
    {
        "id": "kling-video-3-pro",
        "name": "Kling VIDEO 3.0 Pro",
        "provider": "KlingAI",
        "type": "video",
        "tier": "mid",
        "air_id": "klingai:kling-video@3-pro",
        "capabilities": ["t2v", "i2v", "v2v"],
        "configs": [
            {"id": "720p-5s",  "label": "720p · 5s",  "resolution": "720p",  "duration": 5,  "est_price_usd": 0.56},
            {"id": "1080p-5s", "label": "1080p · 5s", "resolution": "1080p", "duration": 5,  "est_price_usd": 0.84},
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "kling-video-3-standard",
        "name": "Kling VIDEO 3.0 Standard",
        "provider": "KlingAI",
        "type": "video",
        "tier": "mid",
        "air_id": "klingai:kling-video@3-standard",
        "capabilities": ["t2v", "i2v", "v2v"],
        "configs": [
            {"id": "720p-5s",  "label": "720p · 5s",  "resolution": "720p",  "duration": 5,  "est_price_usd": 0.42},
            {"id": "1080p-5s", "label": "1080p · 5s", "resolution": "1080p", "duration": 5,  "est_price_usd": 0.63},
        ],
        "default_config_id": "720p-5s",
    },

    # ── Budget ─────────────────────────────────────────────────
    {
        "id": "ltx-2-3",
        "name": "LTX 2.3",
        "provider": "Lightricks",
        "type": "video",
        "tier": "budget",
        "air_id": "lightricks:ltx@2.3",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-5s",  "label": "720p · 5s",   "resolution": "720p", "duration": 5,  "est_price_usd": 0.30},
            {"id": "480p-5s",  "label": "480p · 5s",   "resolution": "480p", "duration": 5,  "est_price_usd": 0.20},
            {"id": "720p-9s",  "label": "720p · 9s",   "resolution": "720p", "duration": 9,  "est_price_usd": 0.54},
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "ltx-2-3-fast",
        "name": "LTX 2.3 Fast",
        "provider": "Lightricks",
        "type": "video",
        "tier": "budget",
        "air_id": "lightricks:ltx@2.3-fast",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-5s",  "label": "720p · 5s",  "resolution": "720p", "duration": 5, "est_price_usd": 0.20},
            {"id": "480p-5s",  "label": "480p · 5s",  "resolution": "480p", "duration": 5, "est_price_usd": 0.13},
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "seedance-1-5-pro",
        "name": "Seedance 1.5 Pro",
        "provider": "ByteDance",
        "type": "video",
        "tier": "mid",
        "air_id": "bytedance:seedance@1.5-pro",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-5s",   "label": "720p · 5s",   "resolution": "720p", "duration": 5,  "est_price_usd": 0.06},
            {"id": "720p-10s",  "label": "720p · 10s",  "resolution": "720p", "duration": 10, "est_price_usd": 0.12},
            {"id": "1080p-5s",  "label": "1080p · 5s",  "resolution": "1080p", "duration": 5,  "est_price_usd": 0.12},
            {"id": "1080p-10s", "label": "1080p · 10s", "resolution": "1080p", "duration": 10, "est_price_usd": 0.24},
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "grok-imagine-video",
        "name": "Grok Imagine Video",
        "provider": "xAI",
        "type": "video",
        "tier": "mid",
        "air_id": "xai:grok-imagine@video",
        "capabilities": ["t2v"],
        "configs": [
            {"id": "720p-5s",  "label": "720p · 5s",  "resolution": "720p", "duration": 5, "est_price_usd": 0.30},
            {"id": "720p-10s", "label": "720p · 10s", "resolution": "720p", "duration": 10, "est_price_usd": 0.48},
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "hailuo-2-3",
        "name": "MiniMax Hailuo 2.3",
        "provider": "MiniMax",
        "type": "video",
        "tier": "mid",
        "air_id": "minimax:4@1",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-6s",  "label": "720p · 6s",  "resolution": "720p", "duration": 6, "est_price_usd": 0.28},
            {"id": "720p-10s", "label": "720p · 10s", "resolution": "720p", "duration": 10, "est_price_usd": 0.49},
        ],
        "default_config_id": "720p-6s",
    },
    {
        "id": "pixverse-v5-6",
        "name": "PixVerse v5.6",
        "provider": "PixVerse",
        "type": "video",
        "tier": "mid",
        "air_id": "pixverse:1@7",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-5s",  "label": "720p · 5s",  "resolution": "720p", "duration": 5, "est_price_usd": 0.10},
            {"id": "720p-8s",  "label": "720p · 8s",  "resolution": "720p", "duration": 8, "est_price_usd": 0.20},
            {"id": "1080p-5s", "label": "1080p · 5s", "resolution": "1080p", "duration": 5, "est_price_usd": 0.25},
            {"id": "1080p-8s", "label": "1080p · 8s", "resolution": "1080p", "duration": 8, "est_price_usd": 0.35},
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "vidu-q3",
        "name": "Vidu Q3",
        "provider": "Vidu",
        "type": "video",
        "tier": "budget",
        "air_id": "vidu:q@3",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-4s",  "label": "720p · 4s",  "resolution": "720p", "duration": 4, "est_price_usd": 0.23},
            {"id": "720p-8s",  "label": "720p · 8s",  "resolution": "720p", "duration": 8, "est_price_usd": 0.46},
        ],
        "default_config_id": "720p-4s",
    },
    {
        "id": "vidu-q3-turbo",
        "name": "Vidu Q3 Turbo",
        "provider": "Vidu",
        "type": "video",
        "tier": "budget",
        "air_id": "vidu:q@3-turbo",
        "capabilities": ["t2v", "i2v"],
        "configs": [
            {"id": "720p-4s",  "label": "720p · 4s",  "resolution": "720p", "duration": 4, "est_price_usd": 0.13},
            {"id": "720p-8s",  "label": "720p · 8s",  "resolution": "720p", "duration": 8, "est_price_usd": 0.26},
        ],
        "default_config_id": "720p-4s",
    },
]


# ---------------------------------------------------------------------------
# Featured Audio Models (9)
# ---------------------------------------------------------------------------
AUDIO_MODELS: List[Dict[str, Any]] = [
    # ── Music ──────────────────────────────────────────────────
    {
        "id": "eleven-music-v1",
        "name": "Eleven Music v1",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "music",
        "tier": "premium",
        "air_id": "elevenlabs:1@1",
        "capabilities": ["t2m"],
        "configs": [
            {"id": "default", "label": "Per minute", "pricing_note": "$0.40/min", "est_price_usd_per_min": 0.40},
        ],
        "default_config_id": "default",
    },

    # ── SFX / Sound Design ─────────────────────────────────────
    {
        "id": "kling-v2a",
        "name": "KlingAI Video to Audio",
        "provider": "KlingAI",
        "type": "audio",
        "category": "sfx",
        "tier": "mid",
        "air_id": "klingai:v2a@1",
        "capabilities": ["v2a"],
        "configs": [
            {"id": "default", "label": "Per generation", "est_price_usd": 0.05},
        ],
        "default_config_id": "default",
    },
    {
        "id": "ovi",
        "name": "Ovi",
        "provider": "Ovi Audio",
        "type": "audio",
        "category": "sfx",
        "tier": "budget",
        "air_id": "ovi:sfx@1",
        "capabilities": ["t2sfx"],
        "configs": [
            {"id": "default", "label": "Per generation", "est_price_usd": 0.02},
        ],
        "default_config_id": "default",
    },
    {
        "id": "mirelo-sfx-1-5",
        "name": "Mirelo SFX 1.5",
        "provider": "Mirelo",
        "type": "audio",
        "category": "sfx",
        "tier": "mid",
        "air_id": "mirelo:sfx@1.5",
        "capabilities": ["t2sfx"],
        "coming_soon": True,
        "configs": [
            {"id": "default", "label": "Coming Soon", "est_price_usd": 0.0},
        ],
        "default_config_id": "default",
    },

    # ── Text-to-Speech ─────────────────────────────────────────
    {
        "id": "minimax-speech-2-8",
        "name": "MiniMax Speech 2.8",
        "provider": "MiniMax",
        "type": "audio",
        "category": "tts",
        "tier": "budget",
        "air_id": "minimax:speech@2.8",
        "capabilities": ["tts"],
        "configs": [
            {"id": "default", "label": "Per 1K chars", "pricing_note": "$0.06/1K chars", "est_price_usd_per_1k_chars": 0.06},
        ],
        "default_config_id": "default",
    },
    {
        "id": "eleven-v3",
        "name": "Eleven v3",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "tts",
        "tier": "premium",
        "air_id": "elevenlabs:tts@v3",
        "capabilities": ["tts"],
        "configs": [
            {"id": "default", "label": "HD Quality", "pricing_note": "$0.10/1K chars", "est_price_usd_per_1k_chars": 0.10},
        ],
        "default_config_id": "default",
    },
    {
        "id": "eleven-flash-v2-5",
        "name": "Eleven Flash v2.5",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "tts",
        "tier": "budget",
        "air_id": "elevenlabs:tts@flash-v2.5",
        "capabilities": ["tts"],
        "configs": [
            {"id": "default", "label": "Fast", "pricing_note": "$0.06/1K chars", "est_price_usd_per_1k_chars": 0.06},
        ],
        "default_config_id": "default",
    },
    {
        "id": "eleven-multilingual-v2",
        "name": "Eleven Multilingual v2",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "tts",
        "tier": "mid",
        "air_id": "elevenlabs:tts@multilingual-v2",
        "capabilities": ["tts", "multilingual"],
        "configs": [
            {"id": "default", "label": "Multilingual", "pricing_note": "$0.10/1K chars", "est_price_usd_per_1k_chars": 0.10},
        ],
        "default_config_id": "default",
    },
    {
        "id": "eleven-turbo-v2-5",
        "name": "Eleven Turbo v2.5",
        "provider": "ElevenLabs",
        "type": "audio",
        "category": "tts",
        "tier": "budget",
        "air_id": "elevenlabs:tts@turbo-v2.5",
        "capabilities": ["tts"],
        "configs": [
            {"id": "default", "label": "Turbo", "pricing_note": "$0.06/1K chars", "est_price_usd_per_1k_chars": 0.06},
        ],
        "default_config_id": "default",
    },
]


# ---------------------------------------------------------------------------
# LLM Models (OpenRouter) — for billing tracking, not for Runware
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
# Combined Registry + Lookup Helpers
# ---------------------------------------------------------------------------
FEATURED_MODELS: List[Dict[str, Any]] = IMAGE_MODELS + VIDEO_MODELS + AUDIO_MODELS + LLM_MODELS

# Lookup by model ID
_MODELS_BY_ID: Dict[str, Dict[str, Any]] = {m["id"]: m for m in FEATURED_MODELS}

# Lookup by AIR ID (Runware identifier) — only for image/video/audio
_MODELS_BY_AIR_ID: Dict[str, Dict[str, Any]] = {}
for _m in FEATURED_MODELS:
    if "air_id" in _m:
        _MODELS_BY_AIR_ID[_m["air_id"]] = _m

# Lookup by OpenRouter ID — only for LLM models
_MODELS_BY_OPENROUTER_ID: Dict[str, Dict[str, Any]] = {}
for _m in LLM_MODELS:
    if "openrouter_id" in _m:
        _MODELS_BY_OPENROUTER_ID[_m["openrouter_id"]] = _m

# Reverse lookup: display name → model entry (for backward compat with _MODEL_MAP)
_MODELS_BY_DISPLAY_NAME: Dict[str, Dict[str, Any]] = {}
for _m in FEATURED_MODELS:
    _MODELS_BY_DISPLAY_NAME[_m["name"]] = _m
    if "display_name" in _m:
        _MODELS_BY_DISPLAY_NAME[_m["display_name"]] = _m


def get_model_by_id(model_id: str) -> Dict[str, Any] | None:
    """Look up a model by its stable ID (e.g. 'gpt-image-1-5')."""
    return _MODELS_BY_ID.get(model_id)


def get_model_by_air_id(air_id: str) -> Dict[str, Any] | None:
    """Look up a model by its Runware AIR identifier (e.g. 'openai:gpt-image@1.5')."""
    return _MODELS_BY_AIR_ID.get(air_id)


def get_model_by_openrouter_id(openrouter_id: str) -> Dict[str, Any] | None:
    """Look up a model by its OpenRouter ID (e.g. 'google/gemini-3.1-pro-preview')."""
    return _MODELS_BY_OPENROUTER_ID.get(openrouter_id)


def get_model_by_name(display_name: str) -> Dict[str, Any] | None:
    """Look up a model by its display name (e.g. 'GPT Image 1.5')."""
    if not display_name:
        return None
        
    # 1. Exact match fast path
    res = _MODELS_BY_DISPLAY_NAME.get(display_name)
    if res:
        return res
        
    # 2. Case-insensitive and fuzzy match
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


# Fallback maps for AIR identifiers that are not natively supported by Runware
# We map mock/fake models displayed in the UI to valid alternatives
_VALID_RUNWARE_OVERRIDES = {
    # Images (map to FLUX and Kling, which are natively supported)
    # OpenAI models
    "openai:1@1": "openai:1@1",
    "openai:2@3": "openai:2@3",
    "openai:2@2": "openai:2@2",
    "bfl:flux-2@max": "runware:101@1",
    "banana:nano@2": "google:4@3",
    "bfl:flux-2@dev": "runware:101@1",
    "bfl:flux-2@flex": "runware:100@1",
    "bfl:flux-2@klein-9b": "runware:100@1",
    "bytedance:seedream@5.0-lite": "bytedance:seedream@5.0-lite", # Native support
    "recraft:recraft@4": "recraft:v4@0",
    "recraft:recraft@4-pro": "recraft:v4-pro@0",
    "google:imagen@4-ultra": "google:2@2",
    "google:imagen@4": "google:2@1",
    
    # Video (map to Kling AI and Bytedance which are fully valid)
    "google:3@3": "google:3@2", # Veo 3.1 Fast -> Veo 3.1
    "openai:sora@2-pro": "klingai:kling-video@3-standard",
    "openai:sora@2": "xai:grok-imagine@video",
    "klingai:kling-video@3-pro": "klingai:kling-video@3-standard",
    "lightricks:ltx@2.3": "klingai:kling-video@3-standard",
    "lightricks:ltx@2.3-fast": "klingai:kling-video@3-standard",
    "vidu:q@3": "bytedance:seedance@1.5-pro",
    "vidu:q@3-turbo": "bytedance:seedance@1.5-pro",
    
    # Audio SFX
    "klingai:v2a@1": "elevenlabs:1@1",
    "ovi:sfx@1": "elevenlabs:1@1",
    "mirelo:sfx@1.5": "elevenlabs:1@1",
    
    # Audio TTS
    "elevenlabs:tts@v3": "minimax:speech@2.8",
    "elevenlabs:tts@flash-v2.5": "minimax:speech@2.8",
    "elevenlabs:tts@multilingual-v2": "minimax:speech@2.8",
    "elevenlabs:tts@turbo-v2.5": "minimax:speech@2.8",
}

def resolve_air_id(
    model_input: str,
    fallback_air_id: str,
    model_type: str | None = None,
) -> str:
    """Resolve any model identifier to a valid Runware AIR ID.

    Accepts:
      - Display name  (e.g. "GPT Image 1.5")
      - Stable ID     (e.g. "gpt-image-1-5")
      - AIR ID        (e.g. "openai:gpt-image@1.5")

    Returns the AIR ID for the matched model, or *fallback_air_id* if nothing
    matches.  The caller should always supply a known-good AIR ID as fallback.
    """
    resolved_id = None
    
    if not model_input:
        resolved_id = fallback_air_id
    elif ":" in model_input:
        resolved_id = model_input
    else:
        # Exact stable-ID match
        entry = _MODELS_BY_ID.get(model_input)
        if entry and "air_id" in entry and (model_type is None or entry.get("type") == model_type):
            resolved_id = entry["air_id"]
        else:
            # Display-name lookup (case-insensitive, fuzzy)
            entry = get_model_by_name(model_input)
            if entry and "air_id" in entry and (model_type is None or entry.get("type") == model_type):
                resolved_id = entry["air_id"]
    
    if not resolved_id:
        print(f"[ModelRegistry] ⚠️ Could not resolve '{model_input}' → AIR ID; using fallback '{fallback_air_id}'")
        resolved_id = fallback_air_id
        
    # Final step: Transparently remap fake/mock AIR identifiers to real Runware models
    if resolved_id in _VALID_RUNWARE_OVERRIDES:
        mapped_id = _VALID_RUNWARE_OVERRIDES[resolved_id]
        print(f"[ModelRegistry] Transformed fake model '{resolved_id}' → valid Runware model '{mapped_id}'")
        return mapped_id
        
    return resolved_id


def get_models_for_api() -> List[Dict[str, Any]]:
    """Return the full model registry formatted for the /billing/models API endpoint."""
    return FEATURED_MODELS
