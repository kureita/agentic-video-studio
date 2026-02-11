"""Editor Agent Service - Uses Gemini to write Remotion composition code dynamically."""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from google import genai
from google.genai import types

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


class EditorAgent:
    """AI-powered video editor. Generates Remotion TSX composition code
    that the frontend compiles and renders client-side."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.compositions_dir = Path("static/compositions")
        self.compositions_dir.mkdir(parents=True, exist_ok=True)
        print("[EditorAgent] Initialized (code-generation mode)")

    async def edit_video(
        self,
        instruction: str,
        node_id: str = "unknown",
        ref_videos: Optional[List[str]] = None,
        audio: Optional[str] = None,
        text_input: Optional[str] = None,
        ref_images: Optional[List[str]] = None,
    ) -> dict:
        """
        Generate a Remotion composition TSX file based on the editing instruction.

        Returns:
            { success: True, code: "<TSX source code>" }
        """
        try:
            print(f"[EditorAgent] Generating code for: {instruction[:100]}...")

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
            )

            # Save to file for persistence / debugging
            file_path = self.compositions_dir / f"{node_id}.tsx"
            file_path.write_text(code, encoding="utf-8")
            print(f"[EditorAgent] Saved composition to {file_path}")

            return {
                "success": True,
                "code": code,
            }

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
    ) -> str:
        """Use Gemini to write Remotion composition TSX code."""

        # Build input descriptions
        video_list = ""
        for i, url in enumerate(ref_videos):
            video_list += f"  Video {i + 1}: \"{url}\" (assume ~5 seconds, 30fps)\n"

        image_list = ""
        for i, url in enumerate(ref_images):
            image_list += f"  Image {i + 1}: \"{url}\"\n"

        prompt = f"""{REMOTION_SKILLS}

---

## Your Task

Write a complete Remotion composition in TSX that fulfills the user's editing instruction.

### User Instruction
"{instruction}"

### Available Inputs
Videos ({len(ref_videos)} total):
{video_list if video_list else "  (none)"}
Images ({len(ref_images)} total):
{image_list if image_list else "  (none)"}
Audio: {"Yes - " + audio if audio else "None"}
Additional context: {text_input if text_input else "None"}

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

        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
            ),
        )

        code = response.text.strip()

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

        # Basic validation
        if "export default" not in code and "export function" not in code:
            raise ValueError("Generated code does not contain a default export. The AI may have produced invalid output.")

        return code
