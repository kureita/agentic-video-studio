import json
import os
import time
from typing import Dict, Any, List, Optional
from copy import deepcopy
from pydantic import BaseModel
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.model_registry import (
    AUDIO_MODELS,
    IMAGE_MODELS,
    VIDEO_MODELS,
    get_model_by_air_id,
    get_model_by_id,
    get_model_by_name,
    resolve_air_id,
)
from app.services.firecrawl_service import FirecrawlService

class AgentService:
    def __init__(self):
        self.openrouter_api_key = settings.openrouter_api_key
        
        self.openrouter_client = None
        if self.openrouter_api_key:
            self.openrouter_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": settings.api_base_url,
                    "X-Title": "Kureita"
                }
            )
            
        self.firecrawl_service = FirecrawlService()
        self._default_video_model_id = "kling-video-3-standard"
        self._default_video_air_id = "klingai:kling-video@3-standard"

    def _resolve_video_model_entry(self, model_input: str) -> Optional[Dict[str, Any]]:
        if not model_input:
            return get_model_by_id(self._default_video_model_id)

        by_id = get_model_by_id(model_input)
        if by_id and by_id.get("type") == "video":
            return by_id

        by_name = get_model_by_name(model_input)
        if by_name and by_name.get("type") == "video":
            return by_name

        air_id = resolve_air_id(
            model_input=model_input,
            fallback_air_id=self._default_video_air_id,
            model_type="video",
        )
        by_air = get_model_by_air_id(air_id)
        if by_air and by_air.get("type") == "video":
            return by_air

        return get_model_by_air_id(self._default_video_air_id)

    def _pick_best_video_model(self, need_i2v: bool, need_audio: bool) -> Dict[str, Any]:
        def has_caps(entry: Dict[str, Any]) -> bool:
            caps = {c.lower() for c in entry.get("capabilities", [])}
            return (not need_i2v or "i2v" in caps) and (not need_audio or "audio" in caps)

        candidates = [m for m in VIDEO_MODELS if has_caps(m)]
        if not candidates:
            return get_model_by_id(self._default_video_model_id) or VIDEO_MODELS[0]

        def rank(entry: Dict[str, Any]) -> int:
            tier = str(entry.get("tier", "budget")).lower()
            return {"premium": 0, "mid": 1, "budget": 2}.get(tier, 3)

        candidates.sort(key=rank)
        return candidates[0]

    def _resolve_audio_model_entry(self, model_input: str) -> Optional[Dict[str, Any]]:
        if not model_input:
            return None

        by_id = get_model_by_id(model_input)
        if by_id and by_id.get("type") == "audio":
            return by_id

        by_name = get_model_by_name(model_input)
        if by_name and by_name.get("type") == "audio":
            return by_name

        air_id = resolve_air_id(model_input=model_input, fallback_air_id="minimax:speech@2.8", model_type="audio")
        by_air = get_model_by_air_id(air_id)
        if by_air and by_air.get("type") == "audio":
            return by_air
        return None

    def _pick_best_audio_model(self, category: str) -> Optional[Dict[str, Any]]:
        candidates = [
            m for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == category.lower() and not bool(m.get("coming_soon", False))
        ]
        if not candidates:
            return None

        def rank(entry: Dict[str, Any]) -> int:
            tier = str(entry.get("tier", "budget")).lower()
            return {"premium": 0, "mid": 1, "budget": 2}.get(tier, 3)

        candidates.sort(key=rank)
        return candidates[0]

    def _normalize_audio_nodes_for_category(self, nodes: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
        """Ensure audioGen model category matches audioType (speech/music/sfx)."""
        normalized_nodes = deepcopy(nodes)
        warnings: List[str] = []
        type_to_category = {"speech": "tts", "music": "music", "sfx": "sfx"}

        for node in normalized_nodes:
            if node.get("type") != "audioGen":
                continue

            node_data = node.get("data", {})
            if not isinstance(node_data, dict):
                continue

            audio_type = str(node_data.get("audioType", "speech")).lower()
            expected_category = type_to_category.get(audio_type, "tts")
            selected_model = str(node_data.get("model") or "")
            entry = self._resolve_audio_model_entry(selected_model) if selected_model else None
            selected_category = str((entry or {}).get("category", "")).lower()

            if (not entry) or selected_category != expected_category or bool((entry or {}).get("coming_soon", False)):
                replacement = self._pick_best_audio_model(expected_category)
                if replacement:
                    replacement_name = str(replacement.get("name") or replacement.get("id") or "")
                    node_data["model"] = replacement_name
                    warnings.append(
                        f"Node '{node.get('id', 'unknown')}' audio model adjusted to '{replacement_name}' for audioType '{audio_type}'."
                    )
            node["data"] = node_data

        return normalized_nodes, warnings

    def _normalize_video_nodes_for_capabilities(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """Ensure assistant-selected video model/audio combos match registry capabilities."""
        normalized_nodes = deepcopy(nodes)
        warnings: List[str] = []

        has_start_image_by_target: Dict[str, bool] = {}
        for e in edges or []:
            target = e.get("target")
            if not target:
                continue
            target_handle = e.get("targetHandle") or e.get("target_handle") or ""
            if isinstance(target_handle, str) and target_handle.endswith("start_image"):
                has_start_image_by_target[target] = True

        for node in normalized_nodes:
            if node.get("type") != "videoGen":
                continue

            node_data = node.get("data", {})
            if not isinstance(node_data, dict):
                continue

            requested_model = str(node_data.get("model") or self._default_video_model_id)
            entry = self._resolve_video_model_entry(requested_model)
            if not entry:
                continue

            caps = {c.lower() for c in entry.get("capabilities", [])}
            need_i2v = bool(has_start_image_by_target.get(str(node.get("id"))))
            wants_audio = bool(node_data.get("generateAudio", False))

            supports_i2v = "i2v" in caps
            supports_audio = "audio" in caps

            if (need_i2v and not supports_i2v) or (wants_audio and not supports_audio):
                replacement = self._pick_best_video_model(need_i2v=need_i2v, need_audio=wants_audio)
                replacement_name = str(replacement.get("name") or replacement.get("id") or self._default_video_model_id)
                node_data["model"] = replacement_name
                warnings.append(
                    f"Node '{node.get('id', 'unknown')}' model adjusted to '{replacement_name}' for capability compatibility."
                )

            # If a replacement still cannot satisfy audio, force-disable generateAudio.
            final_entry = self._resolve_video_model_entry(str(node_data.get("model", requested_model)))
            final_caps = {c.lower() for c in (final_entry or {}).get("capabilities", [])}
            if bool(node_data.get("generateAudio", False)) and "audio" not in final_caps:
                node_data["generateAudio"] = False
                warnings.append(
                    f"Node '{node.get('id', 'unknown')}' had generateAudio disabled because selected model lacks native audio."
                )

            node["data"] = node_data

        return normalized_nodes, warnings
        
    async def generate_workflow(self, prompt: str, model: str = "Gemini 3.1 Flash Lite Preview (Low)", current_nodes: List[Dict] = [], current_edges: List[Dict] = [], chat_history: List[Dict] = []) -> Dict[str, Any]:
        """
        Generate a workflow based on a user prompt using the selected model.
        """
        # Define default API failure response
        failure_response = {
            "success": False,
            "message": "The selected model's API key is not configured.",
            "thinking": None,
            "thinking_duration_ms": None,
            "tool_calls": [],
            "nodes": [],
            "edges": []
        }
        
        # Define OpenRouter mapping
        MODEL_MAPPING = {
            "Gemini 3.1 Pro Preview (High)": "google/gemini-3.1-pro-preview",
            "Gemini 3.1 Flash Lite Preview (Low)": "google/gemini-3.1-flash-lite-preview",
            "Claude 4.6 Opus (High)": "anthropic/claude-opus-4.6",
            "Claude 4.6 Sonnet (Medium)": "anthropic/claude-sonnet-4.6",
            "Claude 4.5 Haiku (Low)": "anthropic/claude-haiku-4.5",
            "GPT-5.4 Pro (High)": "openai/gpt-5.4-pro",
            "GPT-5 Mini (Medium)": "openai/gpt-5-mini",
            "GPT-5 Nano (Low)": "openai/gpt-5-nano"
        }
        
        # Verify Key Availability
        if not self.openrouter_client:
             return failure_response
             
        mapped_model = MODEL_MAPPING.get(model, "google/gemini-3.1-flash-lite-preview")

        # Build capability-accurate model guidance from registry (single source of truth).
        # Image models: include ID, name, and ref image (i2i) support for the LLM.
        image_model_parts = []
        i2i_image_models = []
        t2i_only_image_models = []
        for m in IMAGE_MODELS:
            mid = m.get("id", "unknown")
            mname = m.get("name", mid)
            caps = {c.lower() for c in m.get("capabilities", [])}
            has_i2i = "i2i" in caps
            tag = " [REF]" if has_i2i else ""
            image_model_parts.append(f'"{mname}" (id: "{mid}"){tag}')
            if has_i2i:
                i2i_image_models.append(f'"{mname}" (id: "{mid}")')
            else:
                t2i_only_image_models.append(f'"{mname}" (id: "{mid}")')
        image_model_names = ", ".join(image_model_parts)
        i2i_image_model_names = ", ".join(i2i_image_models) or "none"
        t2i_only_image_model_names = ", ".join(t2i_only_image_models) or "none"
        video_model_names = ", ".join(f'"{m.get("name", m.get("id", "Unknown"))}"' for m in VIDEO_MODELS)
        tts_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}"'
            for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == "tts"
        )
        music_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}"'
            for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == "music"
        )
        sfx_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}"'
            for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == "sfx"
        )
        i2v_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}"'
            for m in VIDEO_MODELS
            if "i2v" in {c.lower() for c in m.get("capabilities", [])}
        )
        native_audio_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}"'
            for m in VIDEO_MODELS
            if "audio" in {c.lower() for c in m.get("capabilities", [])}
        )
        i2v_audio_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}"'
            for m in VIDEO_MODELS
            if {"i2v", "audio"}.issubset({c.lower() for c in m.get("capabilities", [])})
        )

        duration_parts = []
        for m in VIDEO_MODELS:
            name = m.get("name", m.get("id", "Unknown"))
            durations = sorted(
                {
                    int(cfg.get("duration"))
                    for cfg in m.get("configs", [])
                    if isinstance(cfg, dict) and isinstance(cfg.get("duration"), int)
                }
            )
            if durations:
                duration_parts.append(f"{name}: {'/'.join(f'{d}s' for d in durations)}")
        duration_constraints_text = ". ".join(duration_parts) + "."

        start_prompt = f"""
You are an expert AI Video Agent that builds workflows for a visual node-based video generation studio.
The user describes a video they want to create, and you generate nodes and edges for a workflow editor.
Your #1 priority is VISUAL CONSISTENCY — every character, background, and style element must look identical across all scenes.

# Available Node Types and Their Handles:

1. **text** - Text prompt node for writing prompts/scripts
   - Outputs: "text|text" (type: text)
   - Data: {{ "label": "Scene X Prompt", "text": "The actual prompt text here" }}

2. **imageGen** - Image Generator (Multiple models via Runware)
   - Inputs: "text|prompt" (type: text), "image|image" (type: image, optional reference image)
   - Outputs: "image|image" (type: image)
   - Data: {{ "label": "Start Frame Scene X", "prompt": "Description", "ratio": "16:9", "model": "flux-2-dev" }}
   - **IMPORTANT**: Only set `"ratio"` (e.g. "16:9", "9:16", "1:1", "4:3", "3:4"). Do NOT set `"width"` or `"height"` — the backend resolves exact pixel dimensions automatically per model. Each model has its own supported dimensions.
   - **IMPORTANT**: Use the model **id** (e.g. `"flux-2-dev"`, `"nano-banana-2"`), NOT the display name.
   - **Available Models**: {image_model_names}
   - **[REF] = supports reference image** input (image-to-image). Only connect `"image|image"` to these models.
   - **Models that support ref images (i2i)**: {i2i_image_model_names}
   - **Models that do NOT support ref images (text-only)**: {t2i_only_image_model_names}. Do NOT connect a reference image to these — it will fail.
   - **Model Notes**: "flux-2-dev" cheapest ($0.005). "gpt-image-1" best for editing. "kling-image-o3" for character consistency. "flux-2-max" highest quality. "nano-banana-2" great quality + fast.

3. **videoGen** - Video Generator (Multiple models via Runware)
   - Inputs: "text|text" (type: text), "image|start_image" (type: image), "image|end_image" (type: image, optional), "audio|audio" (type: audio, optional)
   - Outputs: "video|video" (type: video), "image|start_frame" (type: image, first frame), "image|end_frame" (type: image, last frame)
   - Data: {{ "label": "Video Scene X", "prompt": "Motion description", "duration": "5s", "ratio": "16:9", "model": "Kling VIDEO 3.0 Standard", "generateAudio": false }}
   - **Available Models**: {video_model_names}
   - **Duration Constraints**: {duration_constraints_text}
   - **Model Selection Rules (CRITICAL)**:
     - If `start_image` is connected, prefer models with I2V support: {i2v_model_names}.
     - If native video audio is explicitly requested, prefer models with native-audio capability: {native_audio_model_names}.
     - If both image-to-video AND native audio are needed in the same video node, choose from: {i2v_audio_model_names}.
   - **Audio Rules**:
     - Set `generateAudio: true` ONLY when the user explicitly wants model-native video audio (ambience/dialogue generated by the video model itself).
     - Set `generateAudio: false` by default.
     - If the user wants custom voiceover/music/SFX from separate audio nodes, keep `generateAudio: false` and connect `audioGen` output (`audio|audio`) to `videoGen` input (`audio|audio`) or `editorAgent` input (`audio|audio`).

4. **audioGen** - Audio Generator (Speech, Music, SFX)
   - Inputs: "text|prompt" (type: text, optional — for TTS script or music/SFX description)
   - Outputs: "audio|audio" (type: audio)
   - Data: {{ "label": "Audio: [Name]", "audioType": "speech" | "music" | "sfx", "prompt": "Content or description", "voice": "Rachel", "duration": 15, "model": "MiniMax Speech 2.8" }}
   - **Audio Types**:
     - `"speech"`: Text-to-speech using a selected voice. Set `prompt` to the spoken script. Set `voice` to one of the supported voices (see below).
     - `"music"`: AI-generated background music. Set `prompt` to a descriptive music brief (genre, mood, instruments). Set `duration` in seconds (10–300).
     - `"sfx"`: AI-generated sound effects. Set `prompt` to describe the sound. Set `duration` in seconds (10–300).
   - **Model by Type (CRITICAL)**:
     - speech/tts models only: {tts_model_names}
     - music models only: {music_model_names}
     - sfx models only: {sfx_model_names}
     - NEVER assign a model from the wrong category for the selected `audioType`.
   - **Available Voices** (for speech only): "Rachel", "Domi", "Bella", "Antoni", "Elli", "Josh", "Arnold", "Adam", "Sam", "English_Upbeat_Woman", "English_Calm_Man"
   - **Connection Rule**: Connect `audioGen` output (`audio|audio`) to:
     - `editorAgent` input `audio|audio` — to layer audio over a video composition
     - `videoGen` input `audio|audio` — to attach audio to a generated video clip
   - **Example**: For a video ad with voiceover + background music, create TWO audioGen nodes (one `speech`, one `music`) and connect both to the `editorAgent` node.

5. **editorAgent** - AI Editor (Stitches videos)
   - Inputs: "text|text", "video|ref_videos" (Multiple), "audio|audio" (Multiple — connect audioGen outputs here)
   - Outputs: "video|output"
   - Data: {{ "label": "Editor", "instruction": "Stitching instructions. NOTE: Use this ONLY for basic video stitching and simple motion graphics. NOT for creative generation.", "ratio": "16:9" }}

6. **mediaUpload** - Asset Upload (User Files)
   - Outputs: "image|output" OR "video|output"
   - Data: {{ "label": "Upload [Name]", "mediaType": "image" or "video", "output": "URL_IF_KNOWN" }}

# CORE RULES (MUST FOLLOW STRICTLY):

## 1. BRAINSTORM FIRST (Decision Gate)
**Check**: Is the user's request a high-level concept (e.g., "Make a coffee ad", "Funny cat video")?
- **IF YES**:
  - Return `nodes: []`, `edges: []`.
  - **Message**: "I can help with that! Let's agree on a script first. How about [Brief Idea]? Or do you have a specific scene in mind?"
  - **STOP HERE.** Do not generate nodes.
- **IF NO** (Request is specific/confirmed, e.g., "Use that script", "Scene 1 is..."):
  - Proceed to generate workflow.

## 2. CHARACTER BIBLE & REFERENCE IMAGES (Consistency Foundation)
**Check**: Does the video involve any character, person, animal, or specific subject?
- **IF YES**, you MUST do ALL of the following:

### A. Write a Character Bible
Before generating ANY nodes, define a **frozen Character Bible** for each main character. This is a precise, factual description of their appearance that will be embedded verbatim in EVERY scene prompt.

**Character Bible format** (be extremely specific — vague = inconsistent):
```
[CHARACTER: Name]
Physical: [age]-year-old [gender] with [exact hair color, length, style], [exact eye color], [skin tone], [build/height]
Clothing: [exact outfit with colors, materials, and details — e.g., "weathered brown leather jacket over a white crew-neck t-shirt, dark indigo slim jeans, scuffed black combat boots"]
Distinguishing: [scars, tattoos, accessories, glasses, facial hair, etc.]
```

### B. Generate Character Reference Images
- Create `imageGen` nodes at **Row 0** for each main character.
- Label: "Character Ref: [Name]" 
- The imageGen prompt should be the full Character Bible description + "front-facing, neutral pose, studio lighting, full body visible, plain background"
- Connect these character reference nodes to the `image|start_image` input of EVERY `videoGen` node featuring that character.

### C. Embed the Bible in EVERY Prompt
- The Character Bible block must appear **word-for-word** at the START of every text node prompt and every videoGen/imageGen prompt that features the character.
- NEVER paraphrase it. NEVER change adjectives. "Auburn" must stay "auburn" — never switch to "reddish-brown".

## 3. STYLE BIBLE (Visual Consistency Across All Scenes)
Before generating nodes, define a **frozen Style Bible** that locks the visual language for the entire video.

**Style Bible format:**
```
[STYLE]
Camera: [lens, e.g., "85mm lens, shallow depth of field"]
Lighting: [e.g., "warm golden hour side-lighting" or "dramatic Rembrandt lighting with deep shadows"]
Color Palette: [e.g., "desaturated teal and warm amber tones" or "high contrast, rich blacks, neon accent colors"]
Texture: [e.g., "cinematic 35mm film grain" or "clean digital, sharp detail"]
Mood: [e.g., "gritty and tense" or "dreamy and ethereal"]
```

**Rules:**
- The Style Bible block must appear **word-for-word** in every scene prompt, after the Character Bible.
- ALL scenes must share the same Style Bible. Do not vary lighting/color per scene unless the user explicitly asks.
- This prevents the #1 community complaint: "my clips look like they're from different movies."

## 4. LAST-FRAME CHAINING (Scene-to-Scene Continuity)
**CRITICAL for preventing background/environment drift between clips.**

For sequential scenes (Scene 1 → Scene 2 → Scene 3...), you MUST create edges that chain the **end frame** of one video to the **start image** of the next:

```
Scene 1 videoGen (output: "image|end_frame") → Scene 2 videoGen (input: "image|start_image")
Scene 2 videoGen (output: "image|end_frame") → Scene 3 videoGen (input: "image|start_image")
```

**Why this works:** The AI model sees the exact last frame of the previous clip as its starting point, so it maintains the same environment, character position, and lighting. This is the #1 technique used by professional AI filmmakers.

**Rules:**
- Create these chaining edges for EVERY pair of sequential scenes.
- The edge format: `{{ "id": "chain-sN-sN+1", "source": "[scene-N-video-node-id]", "target": "[scene-N+1-video-node-id]", "sourceHandle": "image|end_frame", "targetHandle": "image|start_image" }}`
- If Scene N+1 already has a start image from an imageGen node, the last-frame chain takes priority. Remove the imageGen→start_image edge for that scene and use the chain instead (EXCEPT for the very first scene, which should use its start image).

## 5. BACKGROUND/LOCATION REFERENCE IMAGES
**Check**: Does the video feature distinct locations or environments?
- **IF YES**:
  - Create `imageGen` nodes at **Row 0** for each unique location.
  - Label: "Location: [Name]" (e.g., "Location: Dark Alley", "Location: Rooftop")
  - Prompt: Detailed description of the environment + Style Bible + "wide establishing shot, no people, [aspect ratio]"
  - Connect each location imageGen to the `image|image` (reference) input of the FIRST `imageGen` node in each scene that takes place in that location.
  - **The receiving imageGen node MUST use a model that supports ref images (i2i)** — e.g. "flux-2-dev", "gpt-image-1", "nano-banana-2", "kling-image-o3". Do NOT connect ref images to text-only models.
  - This anchors the AI to generate the same environment every time.

## 6. TRANSITION CONTEXT (Narrative Continuity)
Each scene prompt (except the first) MUST include a brief transition sentence at the beginning of the scene-specific action that describes where the previous scene left off.

**Example:**
- Scene 1 prompt ends with: "...she pushes open the heavy metal door."
- Scene 2 prompt's action starts with: "Continuing from the previous shot — she steps through the doorway into a dimly lit kitchen. She looks around cautiously..."

This gives the AI model narrative context and helps it understand spatial/temporal continuity.

## 7. STRUCTURED PROMPT TEMPLATE (Mandatory Format)
Every `text` node prompt for a scene MUST follow this exact structure:

```
[CHARACTER BIBLE — copied verbatim]

[STYLE BIBLE — copied verbatim]

[SCENE ACTION — unique per scene, includes transition context]
[Describe what happens: character actions, movements, expressions, interactions]

[CAMERA DIRECTION — specific per scene]
[Shot type, camera movement, framing. e.g., "Medium close-up, slow dolly push in, eye-level angle"]
```

**Rules:**
- Character Bible and Style Bible blocks are IDENTICAL across all scene prompts — copy-paste, never rewrite.
- Only SCENE ACTION and CAMERA DIRECTION change between scenes.
- This prevents "identity drift" — the AI always has the same character/style anchors.

## 8. ATTACHMENTS (User Uploads & Drag-and-Drop)
**CRITICAL:** If the user attaches a file to their prompt, it will appear as `[Attached: filename.ext] (type) - URL: https://...` 
- You MUST create a `mediaUpload` node for EVERY attached file.
- The `mediaType` of the `mediaUpload` node should be set to `"video"`, `"audio"`, or `"image"` based on the attachment `(type)`.
- The `output` field of the `mediaUpload` node `data` MUST be set to the exact provided `URL`.
- **NEVER call `search_web` on attachment URLs.** These are private S3 links that are only accessible by the system internally. Do NOT try to fetch, scrape, or visit them. Just copy them verbatim into the `output` field.
- ALWAYS connect this new `mediaUpload` node to an appropriate downstream node:
  - If they attach a video and ask to edit it: Connect its `video|output` to `editorAgent`'s `video|ref_videos`.
  - If they attach an image and want to animate it: Connect its `image|output` to `videoGen`'s `image|start_image`.
  - If the uploaded file is a video, it will automatically extract `start_frame` and `end_frame` outputs for you. You can connect the `mediaUpload`'s `image|start_frame` or `image|end_frame` to other nodes if needed.

## 9. ASPECT RATIO & DIMENSIONS (GLOBAL RULE)
**CRITICAL:** You must determine the **Primary Aspect Ratio** for the entire video first.
- **Video Ads / Default**: 16:9
- **Social (TikTok/Shorts)**: 9:16
- **Square**: 1:1

**ALL** nodes in the workflow MUST use the same ratio.
- **IF 16:9**: ALL `videoGen`, `editorAgent`, and `imageGen` nodes: `"ratio": "16:9"`
- **IF 9:16**: ALL nodes: `"ratio": "9:16"`
- **IF 1:1**: ALL nodes: `"ratio": "1:1"`

**For imageGen nodes**: ONLY set `"ratio"` — do NOT set `"width"` or `"height"`. The backend auto-resolves the exact pixel dimensions per model (each model has different supported sizes — e.g. Recraft V4 Pro uses 2688x1536 for 16:9, Gemini Flash uses 1376x768, FLUX uses 1024x576). Setting wrong dimensions causes errors.

**STRICT FORBIDDEN ACTION**:
- Do **NOT** create 1:1 (Square) images for a 16:9 or 9:16 video.
- All Character References, Backgrounds, and Start/End frames MUST match the video ratio exactly.

## 10. TEXT NODE REFERENCING (CRITICAL)
When a **text** node is connected to a generator node (imageGen, videoGen, editorAgent, vision, audioGen),
the generator node's prompt/instruction field MUST reference the connected text node using the `@Text #N` syntax.

**How it works:**
- Text nodes are numbered sequentially: Text #1, Text #2, Text #3, etc. (based on their order in the nodes array).
- When you connect a text node to a generator node AND want that generator to use the text content, put `@Text #N` in the generator's prompt/instruction field.
- At runtime, `@Text #N` gets replaced with the actual text content from the referenced text node.

**Example:**
- You create a text node (Text #1) with content "A golden retriever playing in a field of sunflowers"
- You connect it to an imageGen node
- The imageGen node's `prompt` field should be: `"@Text #1"` (or `"@Text #1, cinematic lighting"` if you want to add extra details)
- You connect the same text node to a videoGen node
- The videoGen node's `prompt` field should be: `"@Text #1"`

**Rules:**
- If a text node is connected to a generator node, ALWAYS use `@Text #N` in the prompt/instruction.
- Do NOT duplicate the text content directly in the generator's prompt field if a text node is connected.
- The `@Text #N` number corresponds to the text node's position among ALL text nodes (1-indexed).
  - If you create 3 text nodes, they are Text #1, Text #2, Text #3 (in the order they appear in the nodes array).
- For `editorAgent` nodes, use `@Text #N` in the `instruction` field.
- For `imageGen`, `videoGen`, and `audioGen` nodes, use `@Text #N` in the `prompt` field.

## 11. PROACTIVE WEB SEARCH (MANDATORY)
**RULE: If the user mentions ANY website URL or domain name (e.g., "regulify.ai", "example.com", https://...), you MUST call the `search_web` tool IMMEDIATELY to fetch and read its content. Do NOT ask the user for permission. Do NOT skip this step.**
- **EXCEPTION:** NEVER call `search_web` on S3 URLs or attachment URLs (e.g., URLs containing `.s3.`, `.s3-`, `s3.amazonaws.com`, or URLs from `[Attached: ...]` lines). These are private internal storage links and will return AccessDenied. Just use them directly in `mediaUpload` node `output` fields.
- **Query format**: Pass ONLY the bare domain or URL as the query — e.g., `"regulify.ai"` or `"https://regulify.ai"`. Do NOT add `site:` operators, `OR`, or any other modifiers. The backend handles scraping automatically.
- Use the scraped content (brand, tagline, features, visuals) to ground your response in real, accurate information.
- After fetching, summarize what you found in your `thinking` field, and reference it in your `message`.
- Similarly, if the user asks about current events, news, or time-sensitive data, call `search_web` with a clear, concise query.

## 12. LAYOUT GRID (Prevent Overlap)
You must use a strict GRID coordinate system based on ROW and COLUMN indices.
- **Horizontal Grid Unit (X spacing)**: 700px between columns.
- **Vertical Grid Unit (Y spacing)**: 600px between rows.
- **Node Width**: Nodes can be up to ~580px wide (16:9 imageGen/videoGen). **Minimum gap**: 120px.

**Algorithm**:
1. Assign each **Scene** or **Logical Step** to a unique `Row Index` (0, 1, 2...).
2. Assign each **Node** within that step to a unique `Column Index` (0, 1, 2...).
3. Calculate: `x = col_index * 700`, `y = row_index * 600`.

**Standard Layout Map**:
- **Row 0 (References)**: Character Refs, Location Refs. (x=0, x=700, x=1400...)
- **Row 1 (Scene 1)**: Text (x=0) -> Start Image (x=700) -> Video (x=1400)
- **Row 2 (Scene 2)**: Text (x=0) -> Start Image (x=700) -> Video (x=1400)
- ...
- **Row N (Final)**: Editor / Compilation Node.

**CRITICAL**:
- **NEVER** output two nodes with the same (x, y).
- **ALWAYS** increment `row_index` for a new scene.
- **ALWAYS** increment `col_index` for the next node in a sequence.
- **NEVER** use gaps smaller than 700px for X or 600px for Y.

# Current Workflow State:
Nodes: {json.dumps(current_nodes)}
Edges: {json.dumps(current_edges)}

# Chat History:
{json.dumps(chat_history)}

# User Request:
"{prompt}"

# IMPORTANT: Your response MUST include a "thinking" field that contains your reasoning/plan BEFORE generating the workflow.
CRITICAL Token Limit Constraint: KEEP YOUR `thinking` AND `message` FIELDS EXTREMELY CONCISE (max 3-4 short sentences). Do NOT write out every node's prompt, plan, or position in the thinking field. You must save your output tokens for the actual JSON nodes/edges!

This thinking field should briefly describe:
1. What the user is asking for
2. Character Bible + Style Bible summary
3. Key decisions (aspect ratio, scene count, chaining strategy)

# Output Format (JSON only):
{{
    "thinking": "Your reasoning and planning here...",
    "tool_calls": [
        {{"name": "search_web", "args": {{"query": "latest AI news"}}, "result": "Search results snippet..."}}
    ],
    "message": "Response to user",
    "action": "replace_all OR update",
    "nodes": [ {{ "id": "n1", "type": "text", "position": {{ "x": 0, "y": 0 }}, "data": {{ "text": "Hello" }} }} ], 
    "edges": [ {{ "id": "e1", "source": "n1", "target": "n2", "sourceHandle": "text|text", "targetHandle": "text|prompt" }} ],
    "updates": {{
        "add_nodes": [ ... ],
        "update_nodes": [ {{ "id": "node-to-update", "data": {{ "prompt": "new text" }} }} ],
        "delete_nodes": [ "node-id-to-delete" ],
        "add_edges": [ {{ "id": "e2", "source": "n3", "target": "n4", "sourceHandle": "image|image", "targetHandle": "image|start_image" }} ],
        "delete_edges": [ "edge-id-to-delete" ]
    }}
}}
Note: If `action` is "update", you ONLY need to return the `updates` object. Leave `nodes` and `edges` empty. Use this for small fixes to save time and tokens! If it's a completely new workflow, use "replace_all" and fill out `nodes` and `edges`.

"""
        
        try:
            start_time = time.time()
            
            token_usage = {"input": 0, "output": 0}
            cost_usd = 0.0
            
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_web",
                        "description": "Searches the web for current information, news, or facts to help answer user queries or build context.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query to look up on the internet."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]

            messages = [
                {"role": "system", "content": "You must respond with valid JSON only."},
                {"role": "user", "content": start_prompt}
            ]
            
            # First pass
            response = await self.openrouter_client.chat.completions.create(
                model=mapped_model,
                messages=messages,
                response_format={"type": "json_object"} if not "claude" in mapped_model else None,
                tools=tools
            )
            
            if hasattr(response, 'usage') and response.usage:
                token_usage["input"] += getattr(response.usage, 'prompt_tokens', 0)
                token_usage["output"] += getattr(response.usage, 'completion_tokens', 0)
                usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else {}
                cost_usd += usage_dict.get('cost', 0.0)
            
            # Check for tool call
            response_message = response.choices[0].message
            if response_message.tool_calls:
                messages.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "search_web":
                        args = json.loads(tool_call.function.arguments)
                        query = args.get("query")
                        print(f"[OpenRouter - {mapped_model}] Executing Tool Call: search_web(query='{query}')")
                        
                        # Execute search
                        search_result = await self.firecrawl_service.search_web(query)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": "search_web",
                            "content": search_result
                        })
                        
                # Second pass after tool responses
                response = await self.openrouter_client.chat.completions.create(
                    model=mapped_model,
                    messages=messages,
                    response_format={"type": "json_object"} if not "claude" in mapped_model else None,
                    tools=tools
                )
                
                if hasattr(response, 'usage') and response.usage:
                    token_usage["input"] += getattr(response.usage, 'prompt_tokens', 0)
                    token_usage["output"] += getattr(response.usage, 'completion_tokens', 0)
                    usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else {}
                    cost_usd += usage_dict.get('cost', 0.0)
            
            response_text = response.choices[0].message.content
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # --- DEBUG LOGS ADDED FOR USER ---
            print("\n" + "="*80)
            print(f"[DEBUG] MODEL USED: {model}")
            print(f"[DEBUG] TOKEN USAGE: Input={token_usage['input']} | Output={token_usage['output']} | Total={token_usage['input'] + token_usage['output']}")
            print(f"[DEBUG] COST (USD):  ${cost_usd:.6f}")
            print("[DEBUG] RAW AI RESPONSE TEXT ALMOST EXACTLY AS RECEIVED:")
            print("-" * 40)
            print(response_text)
            print("-" * 40)
            print("="*80 + "\n")
            # ---------------------------------

            if not response_text:
                return {"success": False, "message": "Empty response from AI", "thinking": None, "thinking_duration_ms": None, "tool_calls": []}

            # ── Clean up response text ──────────────────────────────────────
            # Extract JSON block if it's wrapped in markdown or conversational text
            response_text = response_text.strip()
            import re
            markdown_match = re.search(r'```(?:json)?(.*?)```', response_text, re.DOTALL)
            if markdown_match:
                response_text = markdown_match.group(1).strip()
                print("\n[DEBUG] Extracted JSON via Markdown block match.")
            else:
                # If no markdown block, try to find the outermost JSON object
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    response_text = json_match.group(0)
                    print("\n[DEBUG] Extracted JSON via JSON bracket Match.")
            
            print("\n[DEBUG] EXTRACTED TEXT (Before Repair):")
            print(response_text)
            print("="*80 + "\n")
            
            # ── Robust JSON repair ──────────────────────────────────────
            def _repair_json(text: str) -> str:
                """Fix common LLM JSON issues that cause decoding errors.
                
                Strategy: Try the least invasive fix first, escalate only if needed.
                NEVER manually escape characters inside string values — that corrupts content.
                """
                # Fast path: try strict=False first (accepts control chars in strings)
                try:
                    json.loads(text, strict=False)
                    return text  # Already valid, no repair needed
                except json.JSONDecodeError:
                    pass
                
                # Fix 1: Remove trailing commas before ] or }
                text = re.sub(r',\s*([\]}])', r'\1', text)
                
                # Try again after trailing comma fix
                try:
                    json.loads(text, strict=False)
                    return text
                except json.JSONDecodeError:
                    pass
                
                # Fix 2: Close truncated JSON (bracket balancing)
                # Track string state carefully to avoid mis-counting brackets inside strings
                in_str = False
                esc = False
                stack = []
                for char in text:
                    if esc:
                        esc = False
                        continue
                    if char == '\\':
                        if in_str:
                            esc = True
                        continue
                    if char == '"':
                        in_str = not in_str
                    elif not in_str:
                        if char == '{':
                            stack.append('}')
                        elif char == '[':
                            stack.append(']')
                        elif char == '}' and stack and stack[-1] == '}':
                            stack.pop()
                        elif char == ']' and stack and stack[-1] == ']':
                            stack.pop()
                
                # If we're inside an unclosed string, close it
                text = text.rstrip().rstrip(',')
                if in_str:
                    text += '"'
                
                # Close any unclosed brackets/braces
                while stack:
                    text += stack.pop()

                return text

            response_text = _repair_json(response_text)

            print("\n[DEBUG] FINAL REPAIRED JSON:")
            print(response_text)
            print("="*80 + "\n")

            try:
                result = json.loads(response_text, strict=False)
            except json.JSONDecodeError as parse_err:
                print(f"[AgentService] JSON parse error after repair: {parse_err}")
                print(f"[AgentService] Response text (first 500 chars): {response_text[:500]}")
                
                # Last-resort fallback: extract "nodes" and "edges" arrays via bracket matching
                def _extract_json_array(text: str, key: str) -> list:
                    """Find '"key": [...]' in text using proper bracket matching."""
                    pattern = re.search(r'"' + re.escape(key) + r'"\s*:\s*\[', text)
                    if not pattern:
                        return []
                    start = pattern.end() - 1  # position of the opening [
                    depth = 0
                    in_str = False
                    esc = False
                    for i in range(start, len(text)):
                        c = text[i]
                        if esc:
                            esc = False
                            continue
                        if c == '\\' and in_str:
                            esc = True
                            continue
                        if c == '"':
                            in_str = not in_str
                        elif not in_str:
                            if c == '[':
                                depth += 1
                            elif c == ']':
                                depth -= 1
                                if depth == 0:
                                    try:
                                        return json.loads(text[start:i+1], strict=False)
                                    except json.JSONDecodeError:
                                        return []
                    return []
                
                nodes = []
                edges = []
                try:
                    nodes = _extract_json_array(response_text, "nodes")
                    edges = _extract_json_array(response_text, "edges")
                except Exception as inner_err:
                    print(f"[AgentService] Fallback bracket-matching extraction failed: {inner_err}")
                    
                result = {
                    "thinking": "JSON repair failed — extracted partial data",
                    "message": "Workflow generated (recovered from partial response)",
                    "nodes": nodes,
                    "edges": edges,
                    "tool_calls": []
                }
            
            # Extract thinking and tool_calls from the response
            thinking = result.get("thinking", None)
            tool_calls = result.get("tool_calls", [])
            action = result.get("action", "replace_all")
            
            # Sanitize tool_calls to ensure proper format
            sanitized_tool_calls = []
            for tc in tool_calls:
                sanitized_tool_calls.append({
                    "name": tc.get("name", "unknown"),
                    "status": "completed",
                    "args": tc.get("args", {}),
                    "result": tc.get("result", None)
                })
                
            # Process partial updates vs full replace
            if action == "update" and "updates" in result:
                final_nodes = {n["id"]: n for n in current_nodes}
                final_edges = {e["id"]: e for e in current_edges}
                
                updates = result["updates"]
                
                for n in updates.get("add_nodes", []):
                    final_nodes[n["id"]] = n
                
                for update in updates.get("update_nodes", []):
                    nid = update.get("id")
                    if nid in final_nodes:
                        if "data" in update:
                            for key, val in update["data"].items():
                                final_nodes[nid]["data"][key] = val
                        if "position" in update:
                            final_nodes[nid]["position"] = update["position"]
                        if "type" in update:
                            final_nodes[nid]["type"] = update["type"]
                            
                for nid in updates.get("delete_nodes", []):
                    if nid in final_nodes:
                        del final_nodes[nid]
                        
                for e in updates.get("add_edges", []):
                    # Enforce camelCase for React Flow
                    if "source_handle" in e:
                        e["sourceHandle"] = e.pop("source_handle")
                    if "target_handle" in e:
                        e["targetHandle"] = e.pop("target_handle")
                    final_edges[e["id"]] = e
                    
                for eid in updates.get("delete_edges", []):
                    if eid in final_edges:
                        del final_edges[eid]
                        
                result_nodes = list(final_nodes.values())
                result_edges = list(final_edges.values())
            else:
                result_nodes = result.get("nodes", [])
                result_edges = result.get("edges", [])
                
                # Enforce camelCase for all edges in replace_all
                for e in result_edges:
                    if "source_handle" in e:
                        e["sourceHandle"] = e.pop("source_handle")
                    if "target_handle" in e:
                        e["targetHandle"] = e.pop("target_handle")
            
            normalized_audio_nodes, audio_warnings = self._normalize_audio_nodes_for_category(result_nodes)
            normalized_nodes, model_warnings = self._normalize_video_nodes_for_capabilities(
                normalized_audio_nodes,
                result_edges,
            )

            message = result.get("message", "Workflow generated")
            if model_warnings or audio_warnings:
                message = f"{message} (Adjusted some nodes to valid model capabilities.)"

            return {
                "success": True,
                "message": message,
                "thinking": thinking,
                "thinking_duration_ms": elapsed_ms,
                "tool_calls": sanitized_tool_calls,
                "nodes": normalized_nodes,
                "edges": result_edges,
                "token_usage": token_usage,
                "cost_usd": cost_usd
            }
            
        except Exception as e:
            print(f"Error generating workflow: {e}")
            return {
                "success": False,
                "message": f"Error generating workflow: {str(e)}",
                "thinking": None,
                "thinking_duration_ms": None,
                "tool_calls": [],
                "nodes": [],
                "edges": []
            }
