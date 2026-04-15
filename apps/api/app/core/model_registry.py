"""
Model Registry — Single source of truth for all featured image, video, and audio models.

Used by both the API (for billing, model selection) and exposed to the UI via /billing/models.
Pricing here is for reference/estimation only — actual cost comes from Runware's `includeCost`
response and is what gets billed to the user.

══════════════════════════════════════════════════════════════════════════════
IMAGE MODEL DIMENSION & REFERENCE-IMAGE SUPPORT CHEAT SHEET  (March 2026)
══════════════════════════════════════════════════════════════════════════════

This table documents the EXACT constraints each image model has on Runware.
If you add/update a model, UPDATE BOTH this table AND the _MODEL_DIMENSIONS
dict in runware_service.py.  Mismatched dimensions cause "unsupportedDimensions"
400 errors that are reported by customers.

Model ID            Final AIR (after override)   Dims source           Supports i2i?  Ref mechanism
──────────────────  ───────────────────────────  ────────────────────  ─────────────  ──────────────
gpt-image-1-5       openai:4@1                   _MODEL_DIMENSIONS     ✅ yes          referenceImages
dalle-3             openai:2@3                   _MODEL_DIMENSIONS     ❌ no           —
flux-2-max          bfl:7@1                      _IMAGE_DEFAULT_DIMS   ✅ yes          inputs.referenceImages
nano-banana-2       google:4@3     (override)    _MODEL_DIMENSIONS     ✅ yes          referenceImages
kling-image-o3      klingai:kling-image@o3       _MODEL_DIMENSIONS     ✅ yes          inputs.referenceImages
seedream-5-lite     bytedance:seedream@5.0-lite  _MODEL_DIMENSIONS     ❌ no           —
recraft-v4          recraft:v4@0                 _MODEL_DIMENSIONS     ✅ yes          referenceImages
recraft-v4-pro      recraft:v4-pro@0             _MODEL_DIMENSIONS     ✅ yes          referenceImages
grok-imagine-image  xai:grok-imagine@image       _MODEL_DIMENSIONS     ❌ no           —
imagen-4-ultra      google:2@2                   _MODEL_DIMENSIONS     ❌ no           —
imagen-4-preview    google:2@1                   _MODEL_DIMENSIONS     ❌ no           —
flux-2-dev          runware:400@1                _IMAGE_DEFAULT_DIMS   ✅ yes          referenceImages
flux-2-flex         bfl:6@1                      _IMAGE_DEFAULT_DIMS   ✅ yes          inputs.referenceImages
flux-2-klein-9b     runware:400@3                _IMAGE_DEFAULT_DIMS   ❌ no           —

Key:
  "Final AIR"     = the Runware model ID after _VALID_RUNWARE_OVERRIDES
  "Dims source"   = which dimension table in runware_service.py resolves the (w,h)
  "Ref mechanism"  = which JSON field in the Runware payload carries the ref image

⚠️  When the "Final AIR" column says "(override)", the dimension lookup uses
    the OVERRIDDEN model ID, not the original air_id.  If you change an
    override mapping, verify that the new target has a matching dimension
    entry or falls to safe defaults.
══════════════════════════════════════════════════════════════════════════════
"""

from typing import Dict, List, Any


# ---------------------------------------------------------------------------
# Featured Image Models (13)
# ---------------------------------------------------------------------------
IMAGE_MODELS: List[Dict[str, Any]] = [
    # ── Premium ────────────────────────────────────────────────
    {
        "id": "gpt-image-1-5",
        "name": "GPT Image 1.5",
        "provider": "OpenAI",
        "type": "image",
        "tier": "premium",
        "air_id": "openai:4@1",
        # i2i: uses referenceImages array.  Only 3 ratios supported (1:1, 16:9, 9:16).
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {
                "id": "default",
                "label": "Standard",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.05,
            },
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
        # NO i2i support — text-to-image only.  Only 3 ratios (1:1, 16:9, 9:16).
        "capabilities": ["t2i"],
        "configs": [
            {
                "id": "1024x1024",
                "label": "Square (1024x1024)",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.08,
            },
            {
                "id": "1792x1024",
                "label": "Wide (1792x1024)",
                "width": 1792,
                "height": 1024,
                "est_price_usd": 0.12,
            },
            {
                "id": "1024x1792",
                "label": "Tall (1024x1792)",
                "width": 1024,
                "height": 1792,
                "est_price_usd": 0.12,
            },
        ],
        "default_config_id": "1024x1024",
    },
    {
        "id": "flux-2-max",
        "name": "FLUX.2 [max]",
        "provider": "Black Forest Labs",
        "type": "image",
        "tier": "premium",
        "air_id": "bfl:7@1",
        # Uses seedImage for i2i.
        # Accepts any dims that are multiples of 64 → uses _IMAGE_DEFAULT_DIMENSIONS.
        "capabilities": ["t2i", "i2i", "reference"],
        "configs": [
            {
                "id": "1mp",
                "label": "1 MP (1024×1024)",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.07,
            },
            {
                "id": "1.5mp",
                "label": "1.5 MP (1280×1152)",
                "width": 1280,
                "height": 1152,
                "est_price_usd": 0.10,
            },
            {
                "id": "1.5mp-alt",
                "label": "1.5 MP (1152×1280)",
                "width": 1152,
                "height": 1280,
                "est_price_usd": 0.10,
            },
            {
                "id": "2mp",
                "label": "2 MP (1536×1280)",
                "width": 1536,
                "height": 1280,
                "est_price_usd": 0.13,
            },
            {
                "id": "2.5mp",
                "label": "2.5 MP (1792×1408)",
                "width": 1792,
                "height": 1408,
                "est_price_usd": 0.16,
            },
            {
                "id": "2.5mp-alt",
                "label": "2.5 MP (1408×1792)",
                "width": 1408,
                "height": 1792,
                "est_price_usd": 0.16,
            },
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
        # Overridden to google:4@3 (Gemini Flash 3.1 Image).
        # ⚠️ Uses NON-STANDARD dimensions — see _MODEL_DIMENSIONS["google:4@3"]
        # in runware_service.py.  Common dims like 1024x576 are NOT supported.
        # i2i: uses referenceImages array (Google provider path).
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {
                "id": "1mp-sq",
                "label": "1 MP (1024×1024)",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.047,
            },
            {
                "id": "1mp-land",
                "label": "1 MP (1376×768)",
                "width": 1376,
                "height": 768,
                "est_price_usd": 0.047,
            },
            {
                "id": "1mp-port",
                "label": "1 MP (768×1376)",
                "width": 768,
                "height": 1376,
                "est_price_usd": 0.047,
            },
            {
                "id": "2mp-sq",
                "label": "2 MP (2048×2048)",
                "width": 2048,
                "height": 2048,
                "est_price_usd": 0.103,
            },
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
        # i2i: uses inputs.referenceImages (nested).
        # Dimensions are non-standard — see _MODEL_DIMENSIONS["klingai:kling-image"].
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {
                "id": "1024x1024",
                "label": "1024×1024",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.028,
            },
            {
                "id": "1360x768",
                "label": "1360×768 (16:9)",
                "width": 1360,
                "height": 768,
                "est_price_usd": 0.028,
            },
            {
                "id": "768x1360",
                "label": "768×1360 (9:16)",
                "width": 768,
                "height": 1360,
                "est_price_usd": 0.028,
            },
            {
                "id": "2048x2048",
                "label": "2048×2048",
                "width": 2048,
                "height": 2048,
                "est_price_usd": 0.056,
            },
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
        # NO i2i support — text-to-image only.
        "capabilities": ["t2i"],
        "configs": [
            {
                "id": "default",
                "label": "Up to 3K res",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.035,
            },
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
        # i2i: uses referenceImages array.  Noted as INCONSISTENT on Runware REST
        # (may return 400 for some image formats).
        "capabilities": ["t2i", "i2i", "vector", "svg"],
        "configs": [
            {
                "id": "default",
                "label": "Standard",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.04,
            },
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
        # Same i2i behavior as Recraft V4.
        "capabilities": ["t2i", "i2i", "vector", "svg"],
        "configs": [
            {
                "id": "default",
                "label": "Standard",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.25,
            },
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
        # NO i2i support in our flow.  Runware docs say the model CAN accept
        # seedImage, but our testing showed inconsistent results.  Keeping t2i-only
        # until we can validate i2i reliability.
        # Dimensions are non-standard — see _MODEL_DIMENSIONS["xai:grok-imagine"].
        "capabilities": ["t2i"],
        "configs": [
            {
                "id": "1024x1024",
                "label": "1024×1024",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.02,
            },
            {
                "id": "1024x1536",
                "label": "1024×1536",
                "width": 1024,
                "height": 1536,
                "est_price_usd": 0.022,
            },
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
        # NO i2i support — text-to-image only.
        # ⚠️ Uses NON-STANDARD dimensions — see _MODEL_DIMENSIONS["google:2@"].
        # A previous bug used the "google:" video prefix for Imagen, causing 400s.
        "capabilities": ["t2i"],
        "configs": [
            {
                "id": "default",
                "label": "Standard",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.06,
            },
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
        # Same constraints as Imagen 4 Ultra above.
        "capabilities": ["t2i"],
        "configs": [
            {
                "id": "default",
                "label": "Standard",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.04,
            },
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
        "air_id": "runware:400@1",
        # Uses referenceImages for i2i on Runware backend.
        # Accepts multiples of 64 → _IMAGE_DEFAULT_DIMENSIONS.
        "capabilities": ["t2i", "i2i"],
        "configs": [
            {
                "id": "1mp",
                "label": "1 MP (1024x1024)",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.005,
            },
            {
                "id": "2mp",
                "label": "2 MP (1536x1280)",
                "width": 1536,
                "height": 1280,
                "est_price_usd": 0.008,
            },
        ],
        "default_config_id": "1mp",
    },
    {
        "id": "flux-2-flex",
        "name": "FLUX.2 [flex]",
        "provider": "Black Forest Labs",
        "type": "image",
        "tier": "mid",
        "air_id": "bfl:6@1",
        # Uses seedImage for i2i.
        "capabilities": ["t2i", "i2i", "reference", "fill"],
        "configs": [
            {
                "id": "default",
                "label": "Standard",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.06,
            },
        ],
        "default_config_id": "default",
    },
    {
        "id": "flux-2-klein-9b",
        "name": "FLUX.2 [klein] 9B",
        "provider": "Black Forest Labs",
        "type": "image",
        "tier": "budget",
        "air_id": "runware:400@3",
        # NO i2i support — text-to-image only.
        # Uses _IMAGE_DEFAULT_DIMENSIONS.
        "capabilities": ["t2i"],
        "configs": [
            {
                "id": "default",
                "label": "Standard",
                "width": 1024,
                "height": 1024,
                "est_price_usd": 0.00078,
            },
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
        "capabilities": ["t2v", "i2v", "v2v", "reference", "audio"],
        "input_modes": ["t2v", "reference", "i2v", "v2v"],
        "reference_images_min": 1,
        "reference_images_max": 3,
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "720p-4s-audio",
                "label": "720p · 4s · Audio",
                "resolution": "720p",
                "duration": 4,
                "audio": True,
                "est_price_usd": 0.80,
            },
            {
                "id": "720p-6s-audio",
                "label": "720p · 6s · Audio",
                "resolution": "720p",
                "duration": 6,
                "audio": True,
                "est_price_usd": 1.20,
            },
            {
                "id": "720p-8s-audio",
                "label": "720p · 8s · Audio",
                "resolution": "720p",
                "duration": 8,
                "audio": True,
                "est_price_usd": 1.60,
            },
            {
                "id": "4k-4s-audio",
                "label": "4K · 4s · Audio",
                "resolution": "4k",
                "duration": 4,
                "audio": True,
                "est_price_usd": 1.60,
            },
            {
                "id": "4k-6s-audio",
                "label": "4K · 6s · Audio",
                "resolution": "4k",
                "duration": 6,
                "audio": True,
                "est_price_usd": 2.40,
            },
            {
                "id": "4k-8s-audio",
                "label": "4K · 8s · Audio",
                "resolution": "4k",
                "duration": 8,
                "audio": True,
                "est_price_usd": 3.20,
            },
            {
                "id": "4k-4s-noaudio",
                "label": "4K · 4s · No Audio",
                "resolution": "4k",
                "duration": 4,
                "audio": False,
                "est_price_usd": 3.20,
            },
            {
                "id": "4k-6s-noaudio",
                "label": "4K · 6s · No Audio",
                "resolution": "4k",
                "duration": 6,
                "audio": False,
                "est_price_usd": 4.00,
            },
            {
                "id": "4k-8s-noaudio",
                "label": "4K · 8s · No Audio",
                "resolution": "4k",
                "duration": 8,
                "audio": False,
                "est_price_usd": 4.80,
            },
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
        "capabilities": ["t2v", "i2v", "v2v", "audio"],
        "input_modes": ["t2v", "i2v", "v2v"],
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "720p-4s",
                "label": "720p · 4s",
                "resolution": "720p",
                "duration": 4,
                "audio": True,
                "est_price_usd": 0.80,
            },
            {
                "id": "720p-6s",
                "label": "720p · 6s",
                "resolution": "720p",
                "duration": 6,
                "audio": True,
                "est_price_usd": 1.00,
            },
            {
                "id": "720p-8s",
                "label": "720p · 8s",
                "resolution": "720p",
                "duration": 8,
                "audio": True,
                "est_price_usd": 1.20,
            },
            {
                "id": "4k-4s",
                "label": "4K · 4s",
                "resolution": "4k",
                "duration": 4,
                "audio": True,
                "est_price_usd": 2.40,
            },
            {
                "id": "4k-6s",
                "label": "4K · 6s",
                "resolution": "4k",
                "duration": 6,
                "audio": True,
                "est_price_usd": 2.60,
            },
            {
                "id": "4k-8s",
                "label": "4K · 8s",
                "resolution": "4k",
                "duration": 8,
                "audio": True,
                "est_price_usd": 2.80,
            },
        ],
        "default_config_id": "720p-8s",
    },
    {
        "id": "sora-2-pro",
        "name": "Sora 2 Pro",
        "provider": "OpenAI",
        "type": "video",
        "tier": "premium",
        "air_id": "openai:3@2",
        "capabilities": ["t2v", "i2v"],
        "input_modes": ["t2v", "i2v"],
        "duration_min": 4,
        "duration_max": 20,
        "duration_step": 4,
        "frame_images_min": 1,
        "frame_images_max": 1,
        "configs": [
            {
                "id": "720p-8s",
                "label": "720p · 8s",
                "resolution": "720p",
                "duration": 8,
                "est_price_usd": 2.40,
            },
            {
                "id": "1080p-8s",
                "label": "1080p · 8s",
                "resolution": "1080p",
                "duration": 8,
                "est_price_usd": 4.00,
            },
        ],
        "default_config_id": "720p-8s",
    },
    {
        "id": "sora-2",
        "name": "Sora 2",
        "provider": "OpenAI",
        "type": "video",
        "tier": "premium",
        "air_id": "openai:3@1",
        "capabilities": ["t2v", "i2v"],
        "input_modes": ["t2v", "i2v"],
        "duration_min": 4,
        "duration_max": 20,
        "duration_step": 4,
        "frame_images_min": 1,
        "frame_images_max": 1,
        "configs": [
            {
                "id": "720p-8s",
                "label": "720p · 8s",
                "resolution": "720p",
                "duration": 8,
                "est_price_usd": 0.80,
            },
        ],
        "default_config_id": "720p-8s",
    },
    # ── Mid-Range ──────────────────────────────────────────────
    {
        "id": "kling-video-3-pro",
        "name": "Kling VIDEO 3.0 Pro",
        "provider": "KlingAI",
        "type": "video",
        "tier": "mid",
        "air_id": "klingai:kling-video@3-pro",
        "capabilities": ["t2v", "i2v", "v2v", "reference", "elements", "audio"],
        "input_modes": ["t2v", "i2v", "reference", "elements", "v2v"],
        "duration_min": 3,
        "duration_max": 15,
        "duration_step": 1,
        "reference_images_min": 1,
        "reference_images_max": 1,
        "elements_min": 1,
        "elements_max": 3,
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "720p-5s",
                "label": "720p · 5s",
                "resolution": "720p",
                "duration": 5,
                "est_price_usd": 0.56,
            },
            {
                "id": "1080p-5s",
                "label": "1080p · 5s",
                "resolution": "1080p",
                "duration": 5,
                "est_price_usd": 0.84,
            },
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
        "capabilities": ["t2v", "i2v", "v2v", "reference", "elements", "audio"],
        "input_modes": ["t2v", "i2v", "reference", "elements", "v2v"],
        "duration_min": 3,
        "duration_max": 15,
        "duration_step": 1,
        "reference_images_min": 1,
        "reference_images_max": 1,
        "elements_min": 1,
        "elements_max": 3,
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "720p-5s",
                "label": "720p · 5s",
                "resolution": "720p",
                "duration": 5,
                "est_price_usd": 0.42,
            },
            {
                "id": "1080p-5s",
                "label": "1080p · 5s",
                "resolution": "1080p",
                "duration": 5,
                "est_price_usd": 0.63,
            },
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
        "capabilities": ["t2v", "i2v", "audio"],
        "input_modes": ["t2v", "i2v"],
        "duration_min": 6,
        "duration_max": 10,
        "duration_step": 2,
        "frame_images_min": 1,
        "frame_images_max": 1,
        "native_audio_default": True,
        "configs": [
            {
                "id": "1080p-6s",
                "label": "1080p · 6s",
                "resolution": "1080p",
                "duration": 6,
                "est_price_usd": 0.30,
            },
            {
                "id": "1440p-6s",
                "label": "1440p · 6s",
                "resolution": "1440p",
                "duration": 6,
            },
            {
                "id": "4k-6s",
                "label": "4K · 6s",
                "resolution": "4k",
                "duration": 6,
            },
        ],
        "default_config_id": "1080p-6s",
    },
    {
        "id": "ltx-2-3-fast",
        "name": "LTX 2.3 Fast",
        "provider": "Lightricks",
        "type": "video",
        "tier": "budget",
        "air_id": "lightricks:ltx@2.3-fast",
        "capabilities": ["t2v", "i2v", "audio"],
        "input_modes": ["t2v", "i2v"],
        "frame_images_min": 1,
        "frame_images_max": 1,
        "native_audio_default": True,
        "configs": [
            {
                "id": "1080p-6s",
                "label": "1080p · 6s",
                "resolution": "1080p",
                "duration": 6,
                "est_price_usd": 0.20,
            },
            {
                "id": "1080p-8s",
                "label": "1080p · 8s",
                "resolution": "1080p",
                "duration": 8,
            },
            {
                "id": "1080p-10s",
                "label": "1080p · 10s",
                "resolution": "1080p",
                "duration": 10,
            },
            {
                "id": "1080p-12s",
                "label": "1080p · 12s",
                "resolution": "1080p",
                "duration": 12,
            },
            {
                "id": "1080p-14s",
                "label": "1080p · 14s",
                "resolution": "1080p",
                "duration": 14,
            },
            {
                "id": "1080p-16s",
                "label": "1080p · 16s",
                "resolution": "1080p",
                "duration": 16,
            },
            {
                "id": "1080p-18s",
                "label": "1080p · 18s",
                "resolution": "1080p",
                "duration": 18,
            },
            {
                "id": "1080p-20s",
                "label": "1080p · 20s",
                "resolution": "1080p",
                "duration": 20,
            },
            {
                "id": "1440p-6s",
                "label": "1440p · 6s",
                "resolution": "1440p",
                "duration": 6,
            },
            {
                "id": "1440p-8s",
                "label": "1440p · 8s",
                "resolution": "1440p",
                "duration": 8,
            },
            {
                "id": "1440p-10s",
                "label": "1440p · 10s",
                "resolution": "1440p",
                "duration": 10,
            },
            {
                "id": "4k-6s",
                "label": "4K · 6s",
                "resolution": "4k",
                "duration": 6,
            },
            {
                "id": "4k-8s",
                "label": "4K · 8s",
                "resolution": "4k",
                "duration": 8,
            },
            {
                "id": "4k-10s",
                "label": "4K · 10s",
                "resolution": "4k",
                "duration": 10,
            },
        ],
        "default_config_id": "1080p-8s",
    },
    {
        "id": "seedance-1-5-pro",
        "name": "Seedance 1.5 Pro",
        "provider": "ByteDance",
        "type": "video",
        "tier": "mid",
        "air_id": "bytedance:seedance@1.5-pro",
        "capabilities": ["t2v", "i2v", "audio"],
        "input_modes": ["t2v", "i2v"],
        "duration_min": 4,
        "duration_max": 12,
        "duration_step": 1,
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "720p-5s",
                "label": "720p · 5s",
                "resolution": "720p",
                "duration": 5,
                "est_price_usd": 0.06,
            },
            {
                "id": "720p-10s",
                "label": "720p · 10s",
                "resolution": "720p",
                "duration": 10,
                "est_price_usd": 0.12,
            },
            {
                "id": "1080p-5s",
                "label": "1080p · 5s",
                "resolution": "1080p",
                "duration": 5,
                "est_price_usd": 0.12,
            },
            {
                "id": "1080p-10s",
                "label": "1080p · 10s",
                "resolution": "1080p",
                "duration": 10,
                "est_price_usd": 0.24,
            },
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
        "capabilities": ["t2v", "i2v", "reference", "v2v"],
        "input_modes": ["t2v", "i2v", "reference", "v2v"],
        "duration_min": 1,
        "duration_max": 15,
        "duration_step": 1,
        "reference_images_min": 1,
        "reference_images_max": 7,
        "frame_images_min": 1,
        "frame_images_max": 1,
        "configs": [
            {
                "id": "480p-6s",
                "label": "480p · 6s",
                "resolution": "480p",
                "duration": 6,
                "est_price_usd": 0.30,
            },
            {
                "id": "720p-6s",
                "label": "720p · 6s",
                "resolution": "720p",
                "duration": 6,
                "est_price_usd": 0.48,
            },
        ],
        "default_config_id": "720p-6s",
    },
    {
        "id": "hailuo-2-3",
        "name": "MiniMax Hailuo 2.3",
        "provider": "MiniMax",
        "type": "video",
        "tier": "mid",
        "air_id": "minimax:4@1",
        "capabilities": ["t2v", "i2v"],
        "input_modes": ["t2v", "i2v"],
        "frame_images_min": 1,
        "frame_images_max": 1,
        "native_audio_default": False,
        "configs": [
            {
                "id": "720p-6s",
                "label": "720p · 6s",
                "resolution": "720p",
                "duration": 6,
                "est_price_usd": 0.28,
            },
            {
                "id": "720p-10s",
                "label": "720p · 10s",
                "resolution": "720p",
                "duration": 10,
                "est_price_usd": 0.49,
            },
            {
                "id": "1080p-6s",
                "label": "1080p · 6s",
                "resolution": "1080p",
                "duration": 6,
            },
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
        "capabilities": ["t2v", "i2v", "audio"],
        "input_modes": ["t2v", "i2v"],
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "360p-5s",
                "label": "360p · 5s",
                "resolution": "360p",
                "duration": 5,
                "est_price_usd": 0.10,
            },
            {
                "id": "360p-8s",
                "label": "360p · 8s",
                "resolution": "360p",
                "duration": 8,
                "est_price_usd": 0.20,
            },
            {
                "id": "360p-10s",
                "label": "360p · 10s",
                "resolution": "360p",
                "duration": 10,
            },
            {
                "id": "540p-5s",
                "label": "540p · 5s",
                "resolution": "540p",
                "duration": 5,
            },
            {
                "id": "540p-8s",
                "label": "540p · 8s",
                "resolution": "540p",
                "duration": 8,
            },
            {
                "id": "540p-10s",
                "label": "540p · 10s",
                "resolution": "540p",
                "duration": 10,
            },
            {
                "id": "720p-5s",
                "label": "720p · 5s",
                "resolution": "720p",
                "duration": 5,
                "est_price_usd": 0.25,
            },
            {
                "id": "720p-8s",
                "label": "720p · 8s",
                "resolution": "720p",
                "duration": 8,
                "est_price_usd": 0.35,
            },
            {
                "id": "1080p-5s",
                "label": "1080p · 5s",
                "resolution": "1080p",
                "duration": 5,
            },
            {
                "id": "1080p-8s",
                "label": "1080p · 8s",
                "resolution": "1080p",
                "duration": 8,
                "est_price_usd": 0.35,
            },
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "vidu-q3",
        "name": "Vidu Q3",
        "provider": "Vidu",
        "type": "video",
        "tier": "budget",
        "air_id": "vidu:4@1",
        "capabilities": ["t2v", "i2v", "audio"],
        "input_modes": ["t2v", "i2v"],
        "duration_min": 1,
        "duration_max": 16,
        "duration_step": 1,
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "360p-5s",
                "label": "360p · 5s",
                "resolution": "360p",
                "duration": 5,
                "est_price_usd": 0.23,
            },
            {
                "id": "540p-5s",
                "label": "540p · 5s",
                "resolution": "540p",
                "duration": 5,
            },
            {
                "id": "720p-5s",
                "label": "720p · 5s",
                "resolution": "720p",
                "duration": 5,
            },
            {
                "id": "1080p-5s",
                "label": "1080p · 5s",
                "resolution": "1080p",
                "duration": 5,
                "est_price_usd": 0.46,
            },
        ],
        "default_config_id": "720p-5s",
    },
    {
        "id": "vidu-q3-turbo",
        "name": "Vidu Q3 Turbo",
        "provider": "Vidu",
        "type": "video",
        "tier": "budget",
        "air_id": "vidu:4@2",
        "capabilities": ["t2v", "i2v", "audio"],
        "input_modes": ["t2v", "i2v"],
        "duration_min": 1,
        "duration_max": 16,
        "duration_step": 1,
        "frame_images_min": 1,
        "frame_images_max": 2,
        "native_audio_default": True,
        "configs": [
            {
                "id": "360p-5s",
                "label": "360p · 5s",
                "resolution": "360p",
                "duration": 5,
                "est_price_usd": 0.13,
            },
            {
                "id": "540p-5s",
                "label": "540p · 5s",
                "resolution": "540p",
                "duration": 5,
            },
            {
                "id": "720p-5s",
                "label": "720p · 5s",
                "resolution": "720p",
                "duration": 5,
            },
            {
                "id": "1080p-5s",
                "label": "1080p · 5s",
                "resolution": "1080p",
                "duration": 5,
                "est_price_usd": 0.26,
            },
        ],
        "default_config_id": "720p-5s",
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
            {
                "id": "default",
                "label": "Per minute",
                "pricing_note": "$0.40/min",
                "est_price_usd_per_min": 0.40,
            },
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
            {
                "id": "default",
                "label": "Per 1K chars",
                "pricing_note": "$0.06/1K chars",
                "est_price_usd_per_1k_chars": 0.06,
            },
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
            {
                "id": "default",
                "label": "HD Quality",
                "pricing_note": "$0.10/1K chars",
                "est_price_usd_per_1k_chars": 0.10,
            },
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
            {
                "id": "default",
                "label": "Fast",
                "pricing_note": "$0.06/1K chars",
                "est_price_usd_per_1k_chars": 0.06,
            },
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
            {
                "id": "default",
                "label": "Multilingual",
                "pricing_note": "$0.10/1K chars",
                "est_price_usd_per_1k_chars": 0.10,
            },
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
            {
                "id": "default",
                "label": "Turbo",
                "pricing_note": "$0.06/1K chars",
                "est_price_usd_per_1k_chars": 0.06,
            },
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
    "openai:4@1": "openai:4@1",
    "openai:2@3": "openai:2@3",
    "openai:2@2": "openai:2@2",
    "banana:nano@2": "google:4@3",
    "bytedance:seedream@5.0-lite": "bytedance:seedream@5.0-lite",  # Native support
    "recraft:recraft@4": "recraft:v4@0",
    "recraft:recraft@4-pro": "recraft:v4-pro@0",
    "google:imagen@4-ultra": "google:2@2",
    "google:imagen@4": "google:2@1",
    # Video (map to Kling AI and Bytedance which are fully valid)
    # google:3@3 (Veo 3.1 Fast) — natively supported on Runware, no override needed
    # Backward-compatible aliases for older stored AIR IDs.
    "openai:sora@2-pro": "openai:3@2",
    "openai:sora@2": "openai:3@1",
    "vidu:q@3": "vidu:4@1",
    "vidu:q@3-turbo": "vidu:4@2",
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
            if (
                entry
                and "air_id" in entry
                and (model_type is None or entry.get("type") == model_type)
            ):
                resolved_id = entry["air_id"]

    if not resolved_id:
        print(
            f"[ModelRegistry] ⚠️ Could not resolve '{model_input}' → AIR ID; using fallback '{fallback_air_id}'"
        )
        resolved_id = fallback_air_id

    # Final step: Transparently remap fake/mock AIR identifiers to real Runware models
    if resolved_id in _VALID_RUNWARE_OVERRIDES:
        mapped_id = _VALID_RUNWARE_OVERRIDES[resolved_id]
        print(
            f"[ModelRegistry] Transformed fake model '{resolved_id}' → valid Runware model '{mapped_id}'"
        )
        return mapped_id

    return resolved_id


def get_models_for_api() -> List[Dict[str, Any]]:
    """Return the full model registry formatted for the /billing/models API endpoint."""
    return FEATURED_MODELS
