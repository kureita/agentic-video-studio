"""Editor Agent Service - Uses Anthropic Claude to write Remotion composition code dynamically."""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from anthropic import AsyncAnthropic

from app.core.config import settings


# ── Remotion Skills / Knowledge ──────────────────────────────────────────────
# This is injected into the AI prompt so it knows how to write
# valid Remotion compositions for client-side web rendering.

REMOTION_SKILLS = """
## Remotion Composition Rules

You are writing a Remotion composition that will be rendered **client-side** using `@remotion/web-renderer`.
Follow these rules EXACTLY:

### Module Structure
Your code MUST:
1. Import from 'react', 'remotion', and '@remotion/media' ONLY.
2. Export metadata constants: `fps`, `width`, `height`, `durationInFrames`
3. Export a default function component as the composition.

```tsx
import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig, interpolate, spring, Easing } from 'remotion';
import { Video, Audio } from '@remotion/media';

export const fps = 30;
export const width = 1920;
export const height = 1080;
export const durationInFrames = 300; // 10 seconds at 30fps

export default function MyComposition() {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {/* Your composition here */}
    </AbsoluteFill>
  );
}
```

### Available Remotion APIs
From 'remotion':
- `AbsoluteFill` - Full-size container (position: absolute, inset: 0)
- `Sequence` - Time-based container. Props: `from` (frame), `durationInFrames`, `name`
- `useCurrentFrame()` - Returns current frame number
- `useVideoConfig()` - Returns { fps, width, height, durationInFrames }
- `interpolate(frame, inputRange, outputRange, options)` - Map frame to value
  - options: { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
- `spring({ frame, fps, config })` - Spring animation (0 to 1)
  - config: { damping, mass, stiffness, overshootClamping }
- `Easing` - Easing functions (Easing.bezier, Easing.ease, etc.)

From '@remotion/media':
- `<Video>` - Video element. Props:
  - `src` (string, required) - video URL
  - `trimBefore` (number, frames) - trim start of video
  - `trimAfter` (number, frames) - trim end of video
  - `playbackRate` (number) - speed: 1=normal, 0.5=slow, 2=fast. MUST be > 0. DO NOT use negative values for reverse.
  - `volume` (number 0-1, or function (frame) => number)
  - `style` (CSSProperties)
  - `muted` (boolean)
- `<Audio>` - Audio element. Props:
  - `src` (string, required)
  - `volume` (number 0-1, or function)
  - `trimBefore` (number, frames)

### Web Renderer Limitations (CRITICAL)
The following CSS properties are NOT supported in web rendering:
- ❌ `filter` (blur, brightness, contrast, etc.)
- ❌ `backdrop-filter`
- ❌ `clip-path`
- ❌ `mix-blend-mode`
- ❌ `z-index` (use DOM order instead - later elements render on top)
- ❌ `inset` shadows / spread radius on box-shadow

The following ARE supported:
- ✅ `opacity`
- ✅ `transform` (translate, scale, rotate)
- ✅ `backgroundColor`, `background` (solid, gradients)
- ✅ `border`, `borderRadius`
- ✅ Basic `box-shadow` (no inset, no spread)
- ✅ All text styling (font, color, size, weight, etc.)
- ✅ `position`, `top`, `left`, `right`, `bottom`
- ✅ Flexbox layout
- ✅ SVG elements

### Common Patterns

#### Stitching videos sequentially
```tsx
const clips = [
  { src: "url1", duration: 150 },  // 5 sec at 30fps
  { src: "url2", duration: 120 },  // 4 sec
];
let offset = 0;
return (
  <AbsoluteFill>
    {clips.map((clip, i) => {
      const from = offset;
      offset += clip.duration;
      return (
        <Sequence key={i} from={from} durationInFrames={clip.duration}>
          <AbsoluteFill>
            <Video src={clip.src} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </AbsoluteFill>
        </Sequence>
      );
    })}
  </AbsoluteFill>
);
```

#### Slow motion
```tsx
<Video src={url} playbackRate={0.5} style={...} />
// At 0.5x, a 5sec clip plays for 10sec. Set durationInFrames accordingly.
```

#### Fast forward
```tsx
<Video src={url} playbackRate={2} style={...} />
// At 2x, a 5sec clip plays in 2.5sec. Set durationInFrames accordingly.
```

#### Fade transition between clips
```tsx
// Overlap two sequences and fade opacity
<Sequence from={0} durationInFrames={160}>
  <AbsoluteFill style={{ opacity: interpolate(frame - 0, [130, 150], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>
    <Video src={url1} ... />
  </AbsoluteFill>
</Sequence>
<Sequence from={140} durationInFrames={160}>
  <AbsoluteFill style={{ opacity: interpolate(frame - 140, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>
    <Video src={url2} ... />
  </AbsoluteFill>
</Sequence>
```

#### Text overlay / caption
```tsx
<Sequence from={0} durationInFrames={90}>
  <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 80 }}>
    <div style={{
      color: 'white',
      fontSize: 48,
      fontWeight: 700,
      fontFamily: 'Inter, sans-serif',
      backgroundColor: 'rgba(0,0,0,0.6)',
      padding: '8px 24px',
      borderRadius: 8,
    }}>
      Hello World
    </div>
  </AbsoluteFill>
</Sequence>
```

#### Picture-in-Picture
```tsx
<AbsoluteFill>
  <Video src={mainUrl} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
  <div style={{ position: 'absolute', bottom: 20, right: 20, width: 320, height: 180, borderRadius: 8, overflow: 'hidden', border: '2px solid white' }}>
    <Video src={pipUrl} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
  </div>
</AbsoluteFill>
```

#### Zooming / Ken Burns effect
```tsx
const scale = interpolate(frame, [0, durationInFrames], [1, 1.3], { extrapolateRight: 'clamp' });
<AbsoluteFill style={{ transform: `scale(${scale})` }}>
  <Video src={url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
</AbsoluteFill>
```
"""


# ── Scene-level prompt additions ─────────────────────────────────────────────

REMOTION_SCENE_RULES = """
## SCENE MODE – Component Architecture

You are generating a **single, self-contained scene** component (NOT a full composition).

Follow these additional rules:
1. Export a NAMED function component (e.g., `HookScene`, `CTAScene`, `MontageScene`).
2. Export `sceneDurationInFrames` as a constant indicating how many frames this scene lasts.
3. Accept `width` and `height` as props for responsive sizing.
4. Keep ALL animations relative to frame 0 (the scene manages its own time).
5. Do NOT export `fps`, `width`, `height`, or `durationInFrames` at the module level.
6. Do NOT export a `default` function – export a named component instead.

### Scene Template
```tsx
import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
import { Video, Audio } from '@remotion/media';

export const sceneDurationInFrames = 90; // 3 seconds at 30fps

export function HookScene({ width, height }: { width: number; height: number }) {
  const frame = useCurrentFrame();
  // All frame-based animations start at 0
  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {/* Scene content */}
    </AbsoluteFill>
  );
}
```

Return ONLY the TSX code for this one scene. No markdown fences, no explanations.
"""

REMOTION_COMPOSITOR_RULES = """
## COMPOSITOR MODE – Final Composition

You are generating the **final composition** that stitches multiple scene components together.
The upstream scene TSX codes are provided below. You must INLINE them (copy the component functions)
into your output and arrange them chronologically using `<Sequence>`.

Follow these rules:
1. Copy each scene's component function and `sceneDurationInFrames` into the output.
2. Use `<Sequence from={offset} durationInFrames={sceneDuration}>` for each scene.
3. Add crossfade transitions between scenes (overlapping Sequences with opacity interpolation).
4. Export: `fps`, `width`, `height`, `durationInFrames` (sum of all scenes), and a `default` component.
5. Calculate total `durationInFrames` by summing all scene durations.

### Compositor Template
```tsx
import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, interpolate } from 'remotion';
import { Video, Audio } from '@remotion/media';

// === Scene 1 (inlined) ===
const scene1Duration = 90;
function HookScene({ width, height }: { width: number; height: number }) {
  const frame = useCurrentFrame();
  return (<AbsoluteFill>...</AbsoluteFill>);
}

// === Scene 2 (inlined) ===
const scene2Duration = 120;
function MontageScene({ width, height }: { width: number; height: number }) {
  const frame = useCurrentFrame();
  return (<AbsoluteFill>...</AbsoluteFill>);
}

export const fps = 30;
export const width = 1920;
export const height = 1080;
export const durationInFrames = scene1Duration + scene2Duration;

export default function MyComposition() {
  return (
    <AbsoluteFill>
      <Sequence from={0} durationInFrames={scene1Duration}>
        <HookScene width={1920} height={1080} />
      </Sequence>
      <Sequence from={scene1Duration} durationInFrames={scene2Duration}>
        <MontageScene width={1920} height={1080} />
      </Sequence>
    </AbsoluteFill>
  );
}
```

Return ONLY the TSX code. No markdown fences, no explanations.
"""


class EditorAgent:
    """AI-powered video editor. Generates Remotion TSX composition code
    that the frontend compiles and renders client-side.
    
    Supports two modes:
    - 'scene': generates a self-contained scene component (~50-100 lines)
    - 'compositor': stitches upstream scene codes into a final composition
    - None/default: original monolithic mode (backward compatible)
    """

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.compositions_dir = Path("static/compositions")
        self.compositions_dir.mkdir(parents=True, exist_ok=True)
        print("[EditorAgent] Initialized (code-generation mode, Claude Opus 4.6)")

    async def edit_video(
        self,
        instruction: str,
        node_id: str = "unknown",
        ref_videos: Optional[List[str]] = None,
        audio: Optional[str] = None,
        text_input: Optional[str] = None,
        ref_images: Optional[List[str]] = None,
        mode: Optional[str] = None,  # 'scene', 'compositor', or None (default)
        upstream_scenes: Optional[List[Dict[str, Any]]] = None,  # For compositor mode
    ) -> dict:
        """
        Generate a Remotion composition TSX file based on the editing instruction.

        Returns:
            { success: True, code: "<TSX source code>", mode: "scene"|"compositor"|None,
              sceneConfig: { durationFrames, label } }  # Only in scene mode
        """
        try:
            print(f"[EditorAgent] Generating code (mode={mode}) for: {instruction[:100]}...")

            ref_videos = ref_videos or []
            ref_images = ref_images or []
            if isinstance(ref_videos, str):
                ref_videos = [ref_videos]
            if isinstance(ref_images, str):
                ref_images = [ref_images]

            code = await self._generate_composition_code(
                instruction=instruction,
                ref_videos=ref_videos,
                audio=audio,
                text_input=text_input,
                ref_images=ref_images,
                mode=mode,
                upstream_scenes=upstream_scenes,
            )

            # Save to file for persistence / debugging
            file_path = self.compositions_dir / f"{node_id}.tsx"
            file_path.write_text(code, encoding="utf-8")
            print(f"[EditorAgent] Saved composition to {file_path}")

            result = {
                "success": True,
                "code": code,
                "mode": mode,
            }

            # For scene mode, try to extract scene config from the generated code
            if mode == "scene":
                import re
                duration_match = re.search(r'sceneDurationInFrames\s*=\s*(\d+)', code)
                scene_duration = int(duration_match.group(1)) if duration_match else 90
                
                # Extract the component name
                name_match = re.search(r'export\s+function\s+(\w+)', code)
                scene_label = name_match.group(1) if name_match else "Scene"
                
                result["sceneConfig"] = {
                    "durationFrames": scene_duration,
                    "label": scene_label,
                }

            return result

        except Exception as e:
            print(f"[EditorAgent] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
            }

    async def _generate_composition_code(
        self,
        instruction: str,
        ref_videos: List[str],
        audio: Optional[str],
        text_input: Optional[str],
        ref_images: List[str],
        mode: Optional[str] = None,
        upstream_scenes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Use Anthropic Claude Opus 4.6 to write Remotion composition TSX code."""

        # Build input descriptions
        video_list = ""
        for i, url in enumerate(ref_videos):
            video_list += f"  Video {i + 1}: \"{url}\" (assume ~5 seconds, 30fps)\n"

        image_list = ""
        for i, url in enumerate(ref_images):
            image_list += f"  Image {i + 1}: \"{url}\"\n"

        # Select the appropriate rules based on mode (used as system prompt)
        if mode == "scene":
            system_prompt = REMOTION_SKILLS + "\n\n" + REMOTION_SCENE_RULES
        elif mode == "compositor" and upstream_scenes:
            system_prompt = REMOTION_SKILLS + "\n\n" + REMOTION_COMPOSITOR_RULES
        else:
            system_prompt = REMOTION_SKILLS

        # Build the user prompt (task-specific, rules go into system message)
        user_prompt = f"""## Your Task

{"Write a single SCENE component" if mode == 'scene' else "Write a FINAL COMPOSITION that stitches scenes together" if mode == 'compositor' else "Write a complete Remotion composition"} in TSX that fulfills the user's editing instruction.

### User Instruction
"{instruction}"

### Available Inputs
Videos ({len(ref_videos)} total):
{video_list if video_list else "  (none)"}
Images ({len(ref_images)} total):
{image_list if image_list else "  (none)"}
Audio: {"Yes - " + audio if audio else "None"}
Additional context: {text_input if text_input else "None"}
"""

        # Add upstream scene codes for compositor mode
        if mode == "compositor" and upstream_scenes:
            user_prompt += "\n### Upstream Scene Components to Stitch\n"
            for i, scene in enumerate(upstream_scenes):
                label = scene.get("label", f"Scene {i + 1}")
                code = scene.get("code", "")
                duration = scene.get("durationFrames", 90)
                user_prompt += f"\n#### {label} ({duration} frames)\n```tsx\n{code}\n```\n"
            user_prompt += "\nINLINE these scene components into your composition. Do NOT use import statements for them.\n"

        # Output requirements differ by mode
        if mode == "scene":
            user_prompt += """
### Output Requirements
1. Write COMPLETE, VALID TSX code. No placeholders, no TODOs.
2. Use EXACT video/image URLs from the inputs above. Do NOT invent URLs.
3. Export a NAMED component and `sceneDurationInFrames`.
4. Do NOT export `default`, `fps`, `width`, `height`, or `durationInFrames`.
5. Keep animations relative to frame 0.
6. Use ONLY supported CSS properties (no filter, clip-path, z-index, etc.).
7. Use `<Video>` from '@remotion/media', NOT from 'remotion'.

Return ONLY the TSX code. No markdown fences, no explanations.
"""
        elif mode == "compositor":
            user_prompt += """
### Output Requirements
1. Write COMPLETE, VALID TSX code. No placeholders, no TODOs.
2. INLINE all upstream scene component functions directly in your code.
3. Export: `fps`, `width`, `height`, `durationInFrames`, and `default` component.
4. Calculate `durationInFrames` as the sum of all scene durations.
5. Use `<Sequence>` to arrange scenes chronologically.
6. Add fade transitions between scenes (overlapping Sequences with opacity interpolation).
7. Use ONLY supported CSS properties (no filter, clip-path, z-index, etc.).

Return ONLY the TSX code. No markdown fences, no explanations.
"""
        else:
            user_prompt += """
### Output Requirements
1. Write COMPLETE, VALID TSX code. No placeholders, no TODOs.
2. Use EXACT video/image URLs from the inputs above. Do NOT invent URLs.
3. Export: `fps`, `width`, `height`, `durationInFrames`, and `default` component.
4. Calculate `durationInFrames` accurately based on the editing operations.
5. Apply the user's instruction precisely - if they say slow motion, use playbackRate < 1, etc.
6. Use ONLY supported CSS properties (no filter, clip-path, z-index, etc.).
7. Use `<Video>` from '@remotion/media', NOT from 'remotion'.
8. For trimming, use `trimBefore` and `trimAfter` props (in frames, not seconds).

Return ONLY the TSX code. No markdown fences, no explanations. Do NOT use negative playbackRate even if asked to reverse.
"""

        stream = await self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=128000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            stream=True,
        )

        code_chunks = []
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                code_chunks.append(event.delta.text)

        code = "".join(code_chunks).strip()

        # Strip markdown fences if present
        if code.startswith("```"):
            lines = code.split("\n")
            # Remove first line (```tsx or ```)
            lines = lines[1:]
            # Remove last line if it's ```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines)

        # Safety check: Remove negative playbackRate (causes crash)
        # We replace playbackRate={-0.5} with playbackRate={0.5}
        import re
        code = re.sub(r'playbackRate={-(\d+(\.\d+)?)}', r'playbackRate={\1}', code)
        code = re.sub(r'playbackRate={-\s*(\d+(\.\d+)?)}', r'playbackRate={\1}', code)

        # Basic validation depends on mode
        if mode == "scene":
            if "export function" not in code and "export const" not in code:
                raise ValueError("Generated scene code does not contain a named export.")
        elif mode == "compositor" or mode is None:
            if "export default" not in code and "export function" not in code:
                raise ValueError("Generated code does not contain a default export. The AI may have produced invalid output.")

        return code
