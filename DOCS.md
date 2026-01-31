# Kureita AI Video Platform - Documentation

## Project Creation Flow

This document details the complete execution flow when a user creates a new project, step-by-step.

---

## 🔵 STEP 1: Frontend - User Fills Form

**File:** `apps/web/src/app/projects/new/page.tsx`

```typescript
Line 56-84: handleSubmit() is called when user clicks "Create Video"

Line 61-68: Build the project data object:
{
  website_url: "https://example.com",
  brand_name: "Example Brand",
  description: "...",
  target_audience: "...",
  video_duration: 30,
  style: "cinematic"
}

Line 70: projectsApi.create(data)  → POST /api/projects
Line 74: projectsApi.start(projectId)  → POST /api/projects/{id}/start
Line 77: router.push(`/projects/${projectId}`)  → Redirect to project page
```

---

## 🔵 STEP 2: API - Create Project

**File:** `apps/api/app/api/endpoints/projects.py`

```python
Line 68-95: create_project() endpoint

Line 74-90: Creates MongoDB document:
{
  website_url, brand_name, description, target_audience,
  video_duration, style,
  status: "draft",
  progress: 0,
  brand_profile: null,
  story: null,
  scenes: [],
  video_url: null,
  created_at, updated_at
}

Line 92: Insert into MongoDB
Line 95: Return project with ID
```

---

## 🔵 STEP 3: API - Start Generation

**File:** `apps/api/app/api/endpoints/projects.py`

```python
Line 150-185: start_generation() endpoint

Line 160: Find project in DB
Line 166-167: Check if already generating
Line 170-180: Update status to "analyzing"
Line 183: background_tasks.add_task(run_generation_pipeline, project_id)
          ↓
          Runs pipeline in background, returns immediately
```

---

## 🔵 STEP 4: Pipeline - Initialize

**File:** `apps/api/app/services/pipeline.py`

```python
Line 336-342: run_generation_pipeline(project_id)
Line 341: pipeline = GenerationPipeline(project_id)
Line 342: await pipeline.run()

Line 31-41: __init__() - Initialize all services:
  - self.scraper = WebScraper()
  - self.brand_analyzer = BrandAnalyzer()
  - self.storyteller = Storyteller()
  - self.script_writer = ScriptWriter()
  - self.video_generator = VideoGenerator()
  - self.video_composer = VideoComposer()
```

---

## 🔵 STEP 5: Pipeline - Stage 1: Analyze Website

**File:** `apps/api/app/services/pipeline.py`

```python
Line 54: await self._update_status(ProjectStatus.ANALYZING, 5)
Line 55: brand_profile = await self._analyze_website(project)

Line 123-150: _analyze_website()
  Line 131: scraped_content = await self.scraper.scrape(website_url)
            → Scrapes website HTML, extracts text
  
  Line 134-138: brand_profile = await self.brand_analyzer.analyze(...)
            → LLM analyzes content, extracts:
               - Brand name, tagline, description
               - Primary colors, tone
               - Products, unique selling points
  
  Line 141-147: Save brand_profile to MongoDB
```

---

## 🔵 STEP 6: Pipeline - Stage 2: Create Story

**File:** `apps/api/app/services/pipeline.py`

```python
Line 58: await self._update_status(ProjectStatus.PLANNING, 20)
Line 59: story = await self._create_story(project, brand_profile)

Line 152-179: _create_story()
  Line 161-167: story = await self.storyteller.create_story(...)
            → LLM generates:
               - title: "Your Brand Story"
               - synopsis: "A compelling narrative..."
               - key_messages: ["Innovation", "Quality", ...]
               - target_emotion: "excitement"
               - call_to_action: "Visit us today!"
  
  Line 170-176: Save story to MongoDB
```

---

## 🔵 STEP 7: Pipeline - Stage 3: Write Script

**File:** `apps/api/app/services/pipeline.py`

```python
Line 62: await self._update_status(ProjectStatus.PLANNING, 35)
Line 63: scenes = await self._create_script(project, brand_profile, story)

Line 181-206: _create_script()
  Line 188-193: scenes = await self.script_writer.create_script(...)
            → LLM generates scenes array:
               [
                 { id: 1, start_time: 0, end_time: 8, 
                   description: "Opening shot",
                   visual_prompt: "Cinematic wide shot of...",
                   voiceover_text: "Welcome to...",
                   on_screen_text: "Brand Name" },
                 { id: 2, start_time: 8, end_time: 16, ... },
                 { id: 3, start_time: 16, end_time: 24, ... }
               ]
  
  Line 197-203: Save scenes to MongoDB
```

---

## 🔵 STEP 8: Pipeline - Stage 4: Generate Video Assets

**File:** `apps/api/app/services/pipeline.py`

```python
Line 66: await self._update_status(ProjectStatus.GENERATING, 50)
Line 67: scenes_with_assets = await self._generate_assets(project, scenes)

Line 208-258: _generate_assets()
  FOR EACH SCENE (Line 216-255):
    Line 221: prompt = self._build_veo_prompt(scene, style)
              → "cinematic, professional lighting. Wide shot of... Narrator speaks: '...'"
    
    Line 230-237: result = await self.video_generator.generate_clip(
                    prompt=prompt,
                    duration=8,
                    use_fast_model=True,
                    resolution="720p",
                    ...
                  )
              ↓
              (In MOCK mode: copies existing video, simulates 5-15s delay)
              (In REAL mode: calls Veo 3.1 API, polls until done)
    
    Line 241: scene_dict["asset_url"] = video_url
              → "http://localhost:8000/static/videos/generated_123.mp4"
    
    Line 245-248: Update scene in MongoDB with asset_url
```

---

## 🔵 STEP 9: Pipeline - Stage 5: Compose Video with Remotion

**File:** `apps/api/app/services/pipeline.py`

```python
Line 70: await self._update_status(ProjectStatus.COMPOSING, 85)
Line 71-75: final_video_url = await self._compose_video(scenes, brand_profile, story)

Line 260-292: _compose_video()
  Line 279-284: final_url = await self.video_composer.compose_video(
                  project_id=self.project_id,
                  scenes=scenes,
                  brand_profile=brand_profile,
                  story=story,
                )
```

**File:** `apps/api/app/services/video_composer.py`

```python
Line 30-90: compose_video()
  Line 60-65: Build payload with scenes, brand, story
  
  Line 68-72: POST to Remotion server:
              http://localhost:3001/render
              {
                project_id: "...",
                scenes: [...],
                brand: {...},
                story: {...}
              }
```

**File:** `apps/remotion/src/server.ts`

```typescript
Line 24-100: POST /render endpoint
  Line 47-54: Calculate video metadata (fps, duration)
  
  Line 57-62: Bundle Remotion project
  
  Line 70-89: renderMedia() - Renders video with:
              - Background videos from scenes
              - Text overlays (on_screen_text)
              - Brand watermark
              - Call-to-action on last scene
              - Fade transitions
  
  Line 95-99: Return { output_path, filename }
```

---

## 🔵 STEP 10: Pipeline - Finalize

**File:** `apps/api/app/services/pipeline.py`

```python
Line 78-82: if final_video_url:
              await self.collection.update_one(
                {"_id": ObjectId(self.project_id)},
                {"$set": {"video_url": final_video_url}}
              )

Line 83: await self._update_status(ProjectStatus.COMPLETED, 100)
```

---

## 🔵 STEP 11: Frontend - Display Result

**File:** `apps/web/src/app/projects/[id]/page.tsx`

```typescript
Line 75-86: Polling every 3 seconds while status is in-progress

Line 198-210: When completed, shows video player:
              <video src={project.video_url} controls autoPlay />
```

---

## Architecture Flow Diagram

```
Frontend                    API                         Services
────────────────────────────────────────────────────────────────
[Create Form]
     │
     ├──► POST /api/projects ──► MongoDB (status: draft)
     │
     ├──► POST /api/projects/{id}/start
     │         │
     │         └──► Background Task starts
     │                    │
     │                    ├──► WebScraper.scrape()
     │                    ├──► BrandAnalyzer.analyze() → LLM
     │                    ├──► Storyteller.create_story() → LLM
     │                    ├──► ScriptWriter.create_script() → LLM
     │                    │
     │                    ├──► FOR EACH SCENE:
     │                    │      VideoGenerator.generate_clip()
     │                    │      → Veo 3.1 (or mock)
     │                    │
     │                    ├──► VideoComposer.compose_video()
     │                    │      → POST to Remotion server
     │                    │      → Remotion renders final MP4
     │                    │
     │                    └──► Update status: COMPLETED
     │
     └──► Redirect to /projects/{id}
              │
              └──► Poll GET /api/projects/{id} every 3s
                        │
                        └──► Display video when complete
```

---

## Key Components

### 1. Frontend (Next.js)
- **New Project Form** (`apps/web/src/app/projects/new/page.tsx`)
  - Multi-step form (Website → Style → Details)
  - Validates input
  - Creates project and starts generation

- **Project Detail Page** (`apps/web/src/app/projects/[id]/page.tsx`)
  - Displays project status and progress
  - Polls API every 3 seconds while generating
  - Shows video player when complete

### 2. API (FastAPI)
- **Project Endpoints** (`apps/api/app/api/endpoints/projects.py`)
  - `POST /api/projects` - Create project
  - `GET /api/projects/{id}` - Get project
  - `POST /api/projects/{id}/start` - Start generation
  - `PATCH /api/projects/{id}` - Update project
  - `DELETE /api/projects/{id}` - Delete project

### 3. Pipeline Service
- **Generation Pipeline** (`apps/api/app/services/pipeline.py`)
  - Orchestrates the entire generation workflow
  - 6 stages: Analyze → Story → Script → Assets → Compose → Finalize
  - Updates project status and progress in MongoDB

### 4. AI Services
- **Brand Analyzer** (`apps/api/app/agents/brand_analyzer.py`)
  - Analyzes website content
  - Extracts brand information using LLM

- **Storyteller** (`apps/api/app/agents/storyteller.py`)
  - Creates compelling story narrative
  - Generates title, synopsis, key messages, CTA

- **Script Writer** (`apps/api/app/agents/script_writer.py`)
  - Breaks down story into scenes
  - Generates visual prompts, voiceover text, on-screen text

### 5. Video Services
- **Video Generator** (`apps/api/app/services/video_generator.py`)
  - Generates video clips using Veo 3.1 API
  - Supports mock mode for development
  - Uploads to S3 or saves locally

- **Video Composer** (`apps/api/app/services/video_composer.py`)
  - Sends scene data to Remotion server
  - Returns final composed video URL

### 6. Remotion Service
- **Render Server** (`apps/remotion/src/server.ts`)
  - Receives render requests from API
  - Bundles Remotion project
  - Renders final MP4 with:
    - Background videos from Veo
    - Text overlays
    - Brand watermark
    - Smooth transitions
    - Call-to-action

- **Video Composition** (`apps/remotion/src/compositions/VideoComposition.tsx`)
  - React component that defines video structure
  - Sequences scenes
  - Adds text animations
  - Applies transitions

---

## Environment Configuration

### API (.env)
```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=kureita

# Gemini API (for Veo 3.1)
GEMINI_API_KEY=your_key
USE_MOCK_VEO=true  # Set to false for production

# Remotion
REMOTION_URL=http://localhost:3001

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=
S3_ENDPOINT=

# API Base URL
API_BASE_URL=http://localhost:8000
```

### Remotion
- Outputs to: `apps/api/static/videos/`
- Serves on: `http://localhost:3001`

---

## Status Flow

```
draft → analyzing → planning → generating → composing → completed
                              ↓
                            failed
```

## Progress Stages

- 0% - Draft
- 5% - Analyzing Website
- 15% - Brand Profile Created
- 20% - Creating Story
- 30% - Story Created
- 35% - Writing Script
- 45% - Script Created
- 50-80% - Generating Video Assets (distributed per scene)
- 85% - Composing Video
- 100% - Completed

---

## Data Models

### Project
```python
{
  id: str,
  website_url: str,
  brand_name: str | null,
  description: str | null,
  target_audience: str | null,
  video_duration: int,
  style: VideoStyle,
  status: ProjectStatus,
  progress: int,
  brand_profile: BrandProfile | null,
  story: Story | null,
  scenes: Scene[],
  video_url: str | null,
  thumbnail_url: str | null,
  created_at: datetime,
  updated_at: datetime,
}
```

### BrandProfile
```python
{
  name: str,
  tagline: str | null,
  description: str | null,
  primary_colors: str[],
  logo_url: str | null,
  tone: str,
  products: str[],
  unique_selling_points: str[],
}
```

### Story
```python
{
  title: str,
  synopsis: str,
  key_messages: str[],
  target_emotion: str,
  call_to_action: str,
}
```

### Scene
```python
{
  id: int,
  start_time: float,
  end_time: float,
  description: str,
  visual_prompt: str,
  voiceover_text: str | null,
  on_screen_text: str | null,
  asset_url: str | null,
}
```

