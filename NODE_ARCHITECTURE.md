# Node Architecture

## Vision Node
```
┌─────────────────────────────────────┐
│ Vision                        [Eye] │
├─────────────────────────────────────┤
│                                     │
│  ┌─────────────────────────────┐   │
│  │ OUTPUT AREA (Read-only)     │   │ ← Top 2/3
│  │ Text output appears here    │   │
│  │ after running the node      │   │
│  └─────────────────────────────┘   │
│  ─────────────────────────────────  │ ← Divider
│  ┌─────────────────────────────┐   │
│  │ INSTRUCTION AREA (Editable) │   │ ← Bottom 1/3
│  │ Enter your instruction...   │   │
│  └─────────────────────────────┘   │
│  [Gemini 2.0 Flash]                 │
└─────────────────────────────────────┘
  ○ text (in)
  ○ ref_images (in)
  ○ ref_videos (in)
                    ○ output (text out)
```

**Inputs:**
- `text` - Text input
- `ref_images` - Reference images (multiple connections allowed)
- `ref_videos` - Reference videos (multiple connections allowed)

**Output:**
- `text` - Generated text that can be used as prompt for other nodes

**Purpose:** Uses Gemini as a chat model to analyze inputs and generate text prompts

---

## Editor Agent Node
```
┌─────────────────────────────────────┐
│ Editor Agent          [Clapperboard]│
├─────────────────────────────────────┤
│  ┌─────────────────────────────┐   │
│  │                             │   │
│  │   VIDEO PREVIEW AREA        │   │
│  │   (16:9 aspect ratio)       │   │
│  │                             │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ INSTRUCTION AREA            │   │
│  │ Describe editing task...    │   │
│  └─────────────────────────────┘   │
│  [Remotion]                         │
└─────────────────────────────────────┘
  ○ text (in)
  ○ ref_images (in)
  ○ ref_videos (in)
                    ○ output (video out)
```

**Inputs:**
- `text` - Text instructions
- `ref_images` - Reference images
- `ref_videos` - Reference videos to edit/stitch

**Output:**
- `video` - Edited video output

**Purpose:** Uses Remotion to stitch videos, add transitions, and perform editing tasks

---

## Media Upload Node
```
┌─────────────────────────────────────┐
│ Media Upload              [Upload]  │
├─────────────────────────────────────┤
│  ┌─────────────────────────────┐   │
│  │  [Image/Video Badge]        │   │
│  │                             │   │
│  │   PREVIEW AREA              │   │
│  │   (Shows uploaded media)    │   │
│  │                             │   │
│  └─────────────────────────────┘   │
│                                     │
│  OR (when empty):                   │
│  ┌─────────────────────────────┐   │
│  │     [Upload Icon]           │   │
│  │  Upload Image or Video      │   │
│  │  Drag & drop or click       │   │
│  │  [JPG, PNG] [MP4, MOV]      │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
                    ○ output (dynamic)
```

**Inputs:** None

**Output:**
- `image` - If image is uploaded
- `video` - If video is uploaded
- `any` - Before upload (changes dynamically)

**Purpose:** Upload media files that can be used as inputs for other nodes

---

## Node Connections

### Example Workflow 1: Vision → Image Generator
```
[Text Node] ──text──> [Vision Node] ──text──> [Image Generator] ──image──> [Output]
                          ↑
                       ref_images
                          │
                   [Media Upload]
```

### Example Workflow 2: Editor Agent
```
[Media Upload] ──video──┐
[Media Upload] ──video──┼──> [Editor Agent] ──video──> [Output]
[Text Node] ──text──────┘
```

### Example Workflow 3: Vision with Multiple References
```
[Media Upload] ──image──┐
[Media Upload] ──image──┤
[Media Upload] ──video──┼──> [Vision Node] ──text──> [Video Generator]
[Text Node] ──text──────┘
```

## Connection Rules

1. **Vision Node**
   - Can accept multiple reference images
   - Can accept multiple reference videos
   - Outputs text only

2. **Editor Agent Node**
   - Can accept multiple reference videos
   - Can accept multiple reference images
   - Outputs video only

3. **Media Upload Node**
   - Output type changes based on uploaded content
   - No inputs (source node)
   - Can connect to any node that accepts its media type
