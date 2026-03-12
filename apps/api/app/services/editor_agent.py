"""Editor Agent Service - Uses Anthropic Claude to write Remotion composition code dynamically."""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from openai import AsyncOpenAI, RateLimitError, APIStatusError

from app.core.config import settings


# ── Remotion Skills / Knowledge ──────────────────────────────────────────────
# This is injected into the AI prompt so it knows how to write
# valid Remotion compositions for client-side web rendering.

REMOTION_SKILLS = """
## Remotion Composition Rules

You are writing a Remotion composition that will be rendered **client-side** using `@remotion/web-renderer`.
You are a world-class motion designer and art director. Your compositions must feel premium,
editorial-grade, and indistinguishable from professional post-production output.
Follow these rules EXACTLY:

### Module Structure
Your code MUST:
1. Import from 'react', 'remotion', '@remotion/media', and 'lucide-react' ONLY.
2. Export metadata constants: `fps`, `width`, `height`, `durationInFrames`
3. Export a default function component as the composition.

```tsx
import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig, interpolate, spring, Easing } from 'remotion';
import { Video, Audio } from '@remotion/media';
import { Sparkles, ArrowRight, Star } from 'lucide-react';

export const fps = 30;
export const width = 1080; // MUST match project aspect ratio! (1080 for 9:16, 1920 for 16:9)
export const height = 1920; // MUST match project aspect ratio! (1920 for 9:16, 1080 for 16:9)
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
  - `crossOrigin` (string) - MUST ALWAYS BE SET TO "anonymous"
  - `trimBefore` (number, frames) - trim start of video
  - `trimAfter` (number, frames) - trim end of video
  - `playbackRate` (number) - speed: 1=normal, 0.5=slow, 2=fast. MUST be > 0. DO NOT use negative values for reverse.
  - `volume` (number 0-1, or function (frame) => number)
  - `style` (CSSProperties)
  - `muted` (boolean)
- `<Audio>` - Audio element. Props:
  - `src` (string, required)
  - `crossOrigin` (string) - MUST ALWAYS BE SET TO "anonymous"
  - `volume` (number 0-1, or function)
  - `trimBefore` (number, frames)
### Web Renderer Limitations (CRITICAL)
The following CSS properties are NOT supported in web rendering:
- NO `filter` (blur, brightness, contrast, etc.)
- NO `backdrop-filter`
- NO `clip-path`
- NO `mix-blend-mode`
- NO `z-index` (use DOM order instead - later elements render on top)
- NO `inset` shadows / spread radius on box-shadow

The following ARE supported:
- `opacity`
- `transform` (translate, scale, rotate)
- `backgroundColor`, `background` (solid, gradients)
- `border`, `borderRadius`
- Basic `box-shadow` (no inset, no spread)
- All text styling (font, color, size, weight, etc.)
- `position`, `top`, `left`, `right`, `bottom`
- Flexbox layout
- SVG elements

---

## DESIGN QUALITY STANDARDS (MANDATORY)

Your output MUST meet these professional standards. Failure to follow these will produce unusable output.

### 1. NO EMOJIS — USE PROFESSIONAL ICONS
- NEVER use emoji characters (e.g. no fire, heart, star, crying face, etc.) in ANY text overlay.
- NEVER use unicode symbols as decorative elements.
- Emojis are unprofessional and make video content look amateurish and template-generated.
- Instead of emojis, use professional SVG icons from 'lucide-react'. They provide a premium, modern aesthetic.
- Ensure icons match the text color and proportions, feeling like a natural extension of the typography.
- Bad: "This product is fire 🔥🔥🔥"  Good: "This changes everything."
- Bad: "Wait for it... 😱"  Good: "Wait for it. <ArrowRight size={24} />"
- Bad: "✨ Glow up ✨"  Good: "<Sparkles size={28} style={{ marginRight: 12 }} /> The glow up."

### 2. BRAND-INTELLIGENT TYPOGRAPHY
Choose fonts that match the brand identity and project context. DO NOT default to Inter for everything.
Analyze the project context (product type, brand name, industry, tone) and select the most appropriate
Google Fonts pairing from these curated options:

**Sport / Athletic / Performance brands:**
- Headlines: "Oswald" or "Bebas Neue" (condensed, bold, high-impact)
- Body: "Barlow" or "Barlow Condensed" (clean, athletic, modern)

**Luxury / Fashion / Premium brands:**
- Headlines: "Playfair Display" or "Cormorant Garamond" (elegant serif)
- Body: "Montserrat" (refined geometric sans)

**Tech / SaaS / Modern brands:**
- Headlines: "Space Grotesk" or "Sora" (geometric, futuristic)
- Body: "Inter" or "DM Sans" (clean, technical, neutral)

**Health / Wellness / Beauty brands:**
- Headlines: "Outfit" or "Plus Jakarta Sans" (soft, approachable, modern)
- Body: "Nunito Sans" or "Lato" (warm, friendly)

**Food / Beverage / Lifestyle brands:**
- Headlines: "Poppins" or "Raleway" (friendly, rounded, inviting)
- Body: "Source Sans 3" or "Open Sans" (readable, warm)

**Editorial / Media / Content brands:**
- Headlines: "DM Serif Display" or "Libre Baskerville" (journalistic authority)
- Body: "Source Serif 4" or "Merriweather" (readable, trustworthy)

**Bold / Streetwear / Youth brands:**
- Headlines: "Anton" or "Archivo Black" (loud, impactful, no-nonsense)
- Body: "Work Sans" or "Manrope" (modern, geometric)

**Minimalist / Clean / Studio brands:**
- Headlines: "Instrument Sans" or "General Sans" (understated elegance)
  Note: If these are not available as Google Fonts, fallback to "Inter" weight 600+ or "DM Sans"
- Body: "Inter" or "Figtree" (invisible design, lets content breathe)

IMPORTANT: Pick ONE headline font and ONE body font per composition. Apply them consistently.
Never mix more than 2 font families total. Use weight variations (300, 400, 500, 600, 700) for hierarchy.

### 3. TEXT OVERLAY PRINCIPLES
- Write CONCISE, PUNCHY copy. Short sentences. One idea per overlay.
- Use sentence case or lowercase for a modern feel. ALLCAPS only for single-word impact moments.
- Letter-spacing: slight tracking (0.01-0.04em) on subheadings, tight (-0.02em) on large headlines.
- Line-height: 1.1-1.2 for headlines, 1.4-1.5 for body text.
- Text should breathe — generous padding and margins around text blocks.
- Position text in the lower third or center; avoid cluttering the top.
- Keep all text within safe zones: top 10%, bottom 15%, sides 5% margins.
- Use semi-transparent backgrounds ONLY when text is over busy video. Prefer solid color or gradient.
- NEVER put text backgrounds with hard corners — always use borderRadius (min 4px).
- Maximum 2 lines of text per overlay. If you need more, split across sequences.

### 4. COLOR PALETTE
- Derive your color palette from the content/brand context:
  - Primary text: white (#FFFFFF) or near-white (#F5F5F5) on dark backgrounds
  - Accent color: extract from brand context (e.g. Nike = #FF6B00 volt, not random neon)
  - Avoid pure primary colors (#FF0000, #00FF00, #0000FF) — they look cheap
  - Use muted, sophisticated tones: slate (#64748B), warm gray (#78716C), soft gold (#D4A547)
  - Backgrounds: deep black (#0A0A0A), dark charcoal (#1A1A1A), or brand-dark variants
- Drop shadows on text: subtle only. Max: `0px 2px 8px rgba(0,0,0,0.5)`. Never harsh.

### 5. ANIMATION & MOTION DESIGN
- Animations should feel EFFORTLESS and CONFIDENT, never flashy or desperate.
- USE ABUNDANT MOTION GRAPHICS. Elevate plain video clips with elegant text overlays, animated transitions, or branded graphical elements to keep the viewer constantly engaged.
- Preferred easing: cubic-bezier(0.16, 1, 0.3, 1) for entries (expo-out), never linear.
- Text entries: fade + subtle translateY (10-20px max). Never bounce, never spin, never zoom from 0.
- Hold text on screen for minimum 1.5 seconds for readability.
- Transitions between scenes: prefer hard cuts or quick fades (5-10 frames). Long dissolves are amateur.
- Scale animations: subtle range only (0.95-1.05). Never scale from 0 or to values > 1.15.
- Stagger multiple text elements by 8-15 frames for a polished editorial feel.
- Exit animations: simple fade out over 5-8 frames. No complex exit choreography.

### 6. COMPOSITION LAYOUT
- Embrace negative space. A composition that breathes is more premium than one that's cluttered.
- Visual hierarchy: one dominant element per frame. Support with 1-2 secondary elements max.
- Use consistent margins and padding throughout (multiples of 8px: 16, 24, 32, 40, 48, 64, 80).
- Align elements to an implicit grid. Center-aligned or left-aligned — never both in the same comp.

---

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

#### Professional text overlay (PREFERRED STYLE)
```tsx
<Sequence from={0} durationInFrames={90}>
  <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 120 }}>
    <div style={{
      color: '#F5F5F5',
      fontSize: 42,
      fontWeight: 600,
      fontFamily: '"Oswald", sans-serif',
      letterSpacing: '-0.01em',
      lineHeight: 1.15,
      textAlign: 'center',
      padding: '0 48px',
      opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: 'clamp' }),
      transform: `translateY(${interpolate(frame, [0, 10], [14, 0], { extrapolateRight: 'clamp' })}px)`,
    }}>
      This changes everything.
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

#### Audio Layering & Mixing
```tsx
// Background music — full composition, low volume
<Audio src={musicUrl} volume={0.2} />

// Voiceover — plays from start, high volume
<Sequence from={0} durationInFrames={voiceDurationFrames}>
  <Audio src={voiceoverUrl} volume={1} />
</Sequence>

// SFX — triggered at a visual moment
<Sequence from={transitionFrame} durationInFrames={30}>
  <Audio src={sfxUrl} volume={0.8} />
</Sequence>

// Music with volume ducking during voiceover
<Audio src={musicUrl} volume={(f) => {
  const voStart = 0;
  const voEnd = voiceDurationFrames;
  if (f >= voStart && f <= voEnd) return 0.08;
  return 0.25;
}} />
```

### AUDIO HANDLING RULES (CRITICAL)
When audio tracks are provided, FOLLOW THESE RULES:
1. **Duration alignment**: Set `durationInFrames` to AT LEAST `longest_audio_duration_seconds × fps`.
   If video clips/scenes are shorter than the audio, DO NOT leave a blank black screen and DO NOT simply hold a frozen frame. Instead, you MUST add an engaging, branded motion graphics outro (using text, solid/gradient backgrounds, animations, and brand context) to fill the remaining duration.
   **CRITICAL OUTRO AESTHETICS:** The outro MUST be professional, clean, elegant, and aesthetic. NO AI clichés, NO emojis EVER (use lucide-react icons instead if needed). Use brand-matching typography (e.g., elegant serif for luxury/aesthetic brands, clean geometric sans for tech). Treat it as a high-end commercial sign-off.
2. **Layer by type**:
   - **Music/Score**: Plays for FULL composition duration at volume 0.15–0.30. Place `<Audio>` at root level, OUTSIDE any `<Sequence>`.
   - **Speech/Voiceover**: Plays at volume 0.9–1.0. Start from beginning or sync to scenes with `<Sequence>`.
   - **SFX (Sound Effects)**: Trigger at specific visual moments. Wrap in `<Sequence from={exactFrame}>`.
3. **Volume ducking**: When voiceover AND music coexist, reduce music to 0.05–0.10 during speech segments.
4. **NEVER drop or ignore** an audio track. Every track MUST appear as an `<Audio>` element in the output.
5. **Don't trim** audio unless explicitly instructed. Let tracks play their natural duration.
6. **Exact URLs**: Use the audio URLs exactly as provided — do NOT invent or modify URLs.

#### Subtitles / Captions (Word-by-Word Timing)
```tsx
// Word-by-word animated captions — premium, modern look
const words = [
  { text: "This",    start: 0,   end: 8 },
  { text: "changes", start: 8,   end: 18 },
  { text: "everything.", start: 18, end: 30 },
];

<AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 80 }}>
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', padding: '0 40px' }}>
    {words.map((w, i) => {
      const visible = frame >= w.start && frame <= w.end + 5;
      const localFrame = Math.max(0, frame - w.start);
      const scale = spring({ frame: localFrame, fps, config: { damping: 12, stiffness: 200 } });
      const opacity = interpolate(localFrame, [0, 4], [0, 1], { extrapolateRight: 'clamp' });
      if (!visible) return null;
      return (
        <span key={i} style={{
          fontSize: 38,
          fontWeight: 700,
          fontFamily: '"Oswald", sans-serif',
          color: '#FFFFFF',
          backgroundColor: 'rgba(0,0,0,0.65)',
          borderRadius: 6,
          padding: '4px 12px',
          transform: `scale(${scale})`,
          opacity,
          textShadow: '0 2px 8px rgba(0,0,0,0.4)',
        }}>
          {w.text}
        </span>
      );
    })}
  </div>
</AbsoluteFill>
```

Caption positioning: Bottom center for landscape (paddingBottom: 60–100px),
center-bottom for portrait (paddingBottom: 180–240px).
Keep backgrounds semi-transparent (#000000 at 55–70% opacity, rounded corners).
Large bold text (32–44px) for readability on mobile.

#### Transition Library
Use these ready-made transition patterns between scenes:

**Crossfade** (10–20 frame overlap):
```tsx
// Scene A fades out over last 15 frames, Scene B fades in over first 15 frames
<Sequence from={0} durationInFrames={165}>
  <AbsoluteFill style={{ opacity: interpolate(frame, [150, 165], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>
    <Video src={urlA} style={{ width: '100%', height: '100%', objectFit: 'cover' }} crossOrigin="anonymous" />
  </AbsoluteFill>
</Sequence>
<Sequence from={150} durationInFrames={165}>
  <AbsoluteFill style={{ opacity: interpolate(frame - 150, [0, 15], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>
    <Video src={urlB} style={{ width: '100%', height: '100%', objectFit: 'cover' }} crossOrigin="anonymous" />
  </AbsoluteFill>
</Sequence>
```

**Slide Left** (scene B pushes scene A off-screen):
```tsx
const transitionFrames = 15;
const progress = interpolate(frame - transitionStart, [0, transitionFrames], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
// Scene A
<AbsoluteFill style={{ transform: `translateX(${-progress * 100}%)` }}>
  <Video src={urlA} ... />
</AbsoluteFill>
// Scene B
<AbsoluteFill style={{ transform: `translateX(${(1 - progress) * 100}%)` }}>
  <Video src={urlB} ... />
</AbsoluteFill>
```

**Slide Up** (same as Slide Left but vertical):
```tsx
const progress = interpolate(frame - transitionStart, [0, transitionFrames], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
// Scene A
<AbsoluteFill style={{ transform: `translateY(${-progress * 100}%)` }}>...</AbsoluteFill>
// Scene B
<AbsoluteFill style={{ transform: `translateY(${(1 - progress) * 100}%)` }}>...</AbsoluteFill>
```

**Zoom Through** (subtle zoom into scene A, then scene B appears):
```tsx
const zoomProgress = interpolate(frame - transitionStart, [0, transitionFrames], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
// Scene A zooms in and fades
<AbsoluteFill style={{ transform: `scale(${1 + zoomProgress * 0.15})`, opacity: 1 - zoomProgress }}>
  <Video src={urlA} ... />
</AbsoluteFill>
// Scene B fades in at normal scale
<AbsoluteFill style={{ opacity: zoomProgress }}>
  <Video src={urlB} ... />
</AbsoluteFill>
```

**Hard Cut** (default — no overlap, no animation):
```tsx
<Sequence from={0} durationInFrames={150}><Video src={urlA} ... /></Sequence>
<Sequence from={150} durationInFrames={150}><Video src={urlB} ... /></Sequence>
```

Choose transitions based on content mood:
- **Crossfade**: Emotional, documentary, lifestyle transitions
- **Slide Left/Up**: Energetic, tech, product reveals
- **Zoom Through**: Dramatic, emphasis moments
- **Hard Cut**: Fast-paced, modern, music videos
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

### Scene Inspiration
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
4. Export: `fps`, `width`, `height`, `durationInFrames` (sum of all scenes PLUS any added outro time needed to match audio), and a `default` component.
5. Calculate total `durationInFrames` by summing all scene durations. If the audio is longer than this sum, pad the end with an animated motion graphics outro to match the audio length perfectly.

### Compositor Inspiration
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
export const width = 1080; // MUST match project aspect ratio! (1080 for 9:16, 1920 for 16:9)
export const height = 1920; // MUST match project aspect ratio! (1920 for 9:16, 1080 for 16:9)
export const durationInFrames = scene1Duration + scene2Duration;

export default function MyComposition() {
  return (
    <AbsoluteFill>
      <Sequence from={0} durationInFrames={scene1Duration}>
        <HookScene width={width} height={height} />
      </Sequence>
      <Sequence from={scene1Duration} durationInFrames={scene2Duration}>
        <MontageScene width={width} height={height} />
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
        self.openrouter_api_key = settings.openrouter_api_key
        self.client = None
        if self.openrouter_api_key:
            self.client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": settings.api_base_url,
                    "X-Title": "Kureita"
                }
            )
        # AWS Lambda has a read-only filesystem except for /tmp/.
        # Use /tmp/compositions/ on Lambda and static/compositions/ locally.
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            self.compositions_dir = Path("/tmp/compositions")
        else:
            self.compositions_dir = Path("static/compositions")
        self.compositions_dir.mkdir(parents=True, exist_ok=True)
        print("[EditorAgent] Initialized (code-generation mode, Claude Sonnet 4.6)")

    async def edit_video(
        self,
        instruction: str,
        node_id: str = "unknown",
        ref_videos: Optional[List[str]] = None,
        audio: Optional[str] = None,
        audio_tracks: Optional[List[Dict[str, Any]]] = None,
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

            # Build effective audio tracks list
            effective_tracks = audio_tracks
            if not effective_tracks and audio:
                effective_tracks = [{"url": audio, "type": "unknown", "duration_seconds": 10, "description": "Audio track"}]

            code = await self._generate_composition_code(
                instruction=instruction,
                ref_videos=ref_videos,
                audio_tracks=effective_tracks,
                text_input=text_input,
                ref_images=ref_images,
                mode=mode,
                upstream_scenes=upstream_scenes,
            )

            # Save to file for persistence / debugging
            # On Lambda, this goes to /tmp/compositions/ (only writable path).
            try:
                file_path = self.compositions_dir / f"{node_id}.tsx"
                file_path.write_text(code, encoding="utf-8")
                print(f"[EditorAgent] Saved composition to {file_path}")
            except OSError as write_err:
                # Non-fatal: the code is returned in the response regardless.
                print(f"[EditorAgent] Warning: could not save composition file: {write_err}")

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
        audio_tracks: Optional[List[Dict[str, Any]]] = None,
        text_input: Optional[str] = None,
        ref_images: Optional[List[str]] = None,
        mode: Optional[str] = None,
        upstream_scenes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Use Anthropic Claude Sonnet 4.6 to write Remotion composition TSX code."""

        # Build input descriptions
        ref_videos = ref_videos or []
        ref_images = ref_images or []
        video_list = ""
        for i, url in enumerate(ref_videos):
            video_list += f"  Video {i + 1}: \"{url}\" (assume ~5 seconds, 30fps)\n"

        image_list = ""
        for i, url in enumerate(ref_images):
            image_list += f"  Image {i + 1}: \"{url}\"\n"

        audio_tracks = audio_tracks or []
        audio_list = ""
        for i, track in enumerate(audio_tracks):
            t = track.get("type", "unknown")
            dur = track.get("duration_seconds", "?")
            desc = track.get("description", "")
            audio_list += f'  Track {i + 1}: "{track["url"]}" (type: {t}, duration: {dur}s, description: "{desc}")\n'

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

### Project Context (use this to infer brand category and choose appropriate fonts)
Analyze the instruction and context below to determine:
1. What type of brand/product this is (sport, luxury, tech, health, food, editorial, etc.)
2. Select the appropriate font pairing from the Brand-Intelligent Typography guide above
3. Derive an accent color that fits the brand
4. Match the overall tone (bold, elegant, playful, clinical, etc.)

Context from upstream nodes: {text_input if text_input else "(none — infer from instruction)"}

### Available Inputs
Videos ({len(ref_videos)} total):
{video_list if video_list else "  (none)"}
Images ({len(ref_images)} total):
{image_list if image_list else "  (none)"}
Audio Tracks ({len(audio_tracks)} total):
{audio_list if audio_list else "  (none)"}

### CRITICAL REMINDERS
- DIMENSIONS: Read the instruction carefully to determine the aspect ratio (9:16 vertical = width 1080, height 1920). Set the exported `width` and `height` exactly as requested.
- ZERO emojis in any text overlay. Write professional copy and use 'lucide-react' icons exclusively.
- Choose brand-appropriate fonts from the typography guide. Do NOT default to Inter unless the brand is tech/SaaS. For aesthetic brands, use elegant or refined typefaces.
- Keep animations subtle and confident. No bouncing, spinning, or flashy effects.
- Embrace negative space. Less is more. Premium compositions breathe.
{"- AUDIO: Set durationInFrames to AT LEAST " + str(max((t.get('duration_seconds', 0) for t in audio_tracks), default=0)) + " × fps to fit the audio. If the video clips fall short, YOU MUST ADD A HIGH-QUALITY MOTION GRAPHICS OUTRO to fill the void. This outro MUST be hyper-professional, clean, elegant, matched strictly to brand fonts, with ZERO emojis (use lucide-react icons)." if audio_tracks else ""}
{"- AUDIO: Include ALL " + str(len(audio_tracks)) + " audio track(s) as <Audio> elements. Do NOT drop any." if audio_tracks else ""}
{"- AUDIO: Music at volume 0.15-0.30 (full duration). Voiceover at 0.9-1.0. SFX in <Sequence> at specific moments." if audio_tracks else ""}
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
4. Calculate `durationInFrames` carefully. If audio is longer than the sum of all scenes, you MUST add an extra `<Sequence>` at the end containing an engaging motion graphics outro to pad the duration so it matches the longest audio perfectly. Never leave a black screen.
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

        # Retry with exponential backoff for transient API errors
        max_retries = 3
        base_delay = 5  # seconds

        for attempt in range(1, max_retries + 1):
            try:
                if not self.client:
                    raise ValueError("OpenRouter API key is not configured.")

                stream = await self.client.chat.completions.create(
                    model="anthropic/claude-sonnet-4.6",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    stream=True,
                )

                code_chunks = []
                async for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        content = chunk.choices[0].delta.content
                        if content:
                            code_chunks.append(content)

                code = "".join(code_chunks).strip()
                break  # Success — exit retry loop

            except RateLimitError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))  # 5s, 10s, 20s
                    print(f"[EditorAgent] Rate limit error, retrying in {delay}s (attempt {attempt}/{max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    raise
            except APIStatusError as e:
                retryable = e.status_code in (429, 529, 502, 503, 504)
                if retryable and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))  # 5s, 10s, 20s
                    print(f"[EditorAgent] Transient API error ({e.status_code}), retrying in {delay}s (attempt {attempt}/{max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    raise  # Non-retryable or final attempt — propagate

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
