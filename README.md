# Kureita — AI Video Production Studio

A node-based AI video production platform. Build video workflows visually by connecting nodes — generate images, animate with video AI, add voiceovers, and compose final exports — all powered by real AI providers.

## Tech Stack

### Frontend (`apps/web`)
- **Next.js 15** with React 19
- **TypeScript**
- **Tailwind CSS** with custom dark design system
- **React Flow** — node-based visual workflow editor
- **Framer Motion** for animations
- **Auth0** for authentication
- **Lucide React** for icons
- **Axios** for API calls

### Backend (`apps/api`)
- **FastAPI** with Python 3.11+
- **Pydantic v2** for validation
- **uv** for package management
- **MongoDB** (via Motor) for persistence
- **AWS Lambda + SAM** — serverless deployment
- **AWS S3** — asset storage with presigned URLs

### AI Providers
| Provider | Used For |
|----------|----------|
| **Google Gemini** | Veo 3 video generation, editor agent (thinking model) |
| **OpenAI (GPT-4o)** | Agent reasoning, story generation, script writing |
| **Anthropic Claude** | Alternative LLM for agent tasks |
| **Runware** | Image generation (FLUX, SDXL, and others) |
| **Kling AI** | Image-to-video, text-to-video generation |
| **BytePlus (Seaweed)** | Seeddance 2.0 video generation |
| **ElevenLabs / gTTS** | Voiceover / audio generation |
| **Firecrawl** | Advanced web scraping |

---

## Workflow Nodes

The canvas editor supports the following node types:

| Node | Description |
|------|-------------|
| `mediaUpload` | Upload images, videos, or audio as inputs |
| `text` | Static text / prompt block |
| `imageGen` | Generate images via Runware (FLUX, SDXL, etc.) |
| `videoGen` | Generate video clips (Kling, Veo, BytePlus Seaweed) |
| `audioGen` | Generate voiceovers (ElevenLabs or gTTS) |
| `editorAgent` | AI agent that writes and executes TSX/JSX to compose the final video export |
| `assistant` | AI chat sidebar for workflow guidance |
| `comment` | Annotation node for adding notes |

Nodes are connected by edges. The runner resolves them in topological order, passing outputs from upstream nodes as inputs to downstream ones.

---

## Getting Started

### Prerequisites
- Node.js 20+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — Python package manager
- MongoDB (local or Atlas)

### Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`

### Backend Setup

```bash
cd apps/api
uv sync
uv run uvicorn main:app --reload --port 8000
```

API runs at `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Environment Variables

Copy `.env.example` to `.env` in `apps/api` and fill in your values:

```env
# App
DEBUG=true
CORS_ORIGINS=http://localhost:3000

# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=kureita

# AI / LLM APIs
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
KLING_API_KEY=...
BYTEPLUS_API_KEY=...

# Image Generation
# (Runware API key — get at https://runware.ai)
RUNWARE_API_KEY=...

# Audio
ELEVENLABS_API_KEY=...
USE_MOCK_AUDIO=false   # set true to use free gTTS instead

# AWS (required in production)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=kureita-assets

# Auth0
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://api.kureita.com

# Firecrawl (optional — enhanced scraping)
FIRECRAWL_API_KEY=...
```

---

## Project Structure

```
mvp/
├── apps/
│   ├── web/                        # Next.js frontend
│   │   └── src/
│   │       ├── app/
│   │       │   ├── dashboard/      # Workflow list + creator
│   │       │   │   └── workflow/   # Canvas editor page
│   │       │   ├── usage/          # Billing & usage dashboard
│   │       │   └── login/          # Auth0 login
│   │       ├── components/
│   │       │   ├── workflow/
│   │       │   │   ├── nodes/      # All node UI components
│   │       │   │   ├── flow-editor.tsx
│   │       │   │   ├── agent-sidebar.tsx
│   │       │   │   └── node-wrapper.tsx
│   │       │   ├── billing/        # Add credits modal
│   │       │   └── ui/             # Shared design system
│   │       └── lib/
│   │           ├── workflow-api.ts  # API client for workflows
│   │           └── inspirations.ts  # Pre-built workflow templates
│   └── api/                        # FastAPI backend
│       ├── app/
│       │   ├── api/endpoints/
│       │   │   ├── workflow.py     # Workflow CRUD + execution
│       │   │   ├── agent.py        # AI agent chat endpoint
│       │   │   ├── assets.py       # S3 presigned upload URLs
│       │   │   ├── billing.py      # Credits & usage history
│       │   │   └── canvas.py       # Legacy canvas pipeline
│       │   ├── services/
│       │   │   ├── node_runner.py  # Core node execution engine
│       │   │   ├── editor_agent.py # TSX-writing editor agent
│       │   │   ├── agent_service.py# AI agent with tool use
│       │   │   ├── runware_service.py # Runware image gen
│       │   │   ├── image_generator.py
│       │   │   ├── video_generator.py # Kling / Veo / BytePlus
│       │   │   ├── audio_generator.py # ElevenLabs / gTTS
│       │   │   ├── billing.py
│       │   │   └── storage_service.py # S3 operations
│       │   └── core/
│       │       ├── config.py
│       │       ├── database.py     # MongoDB connection
│       │       └── auth.py         # Auth0 JWT verification
│       ├── main.py
│       ├── Dockerfile
│       └── template.yaml           # AWS SAM deployment template
├── turbo.json
└── package.json
```

---

## API Reference

All endpoints (except internal ones) require `Authorization: Bearer <Auth0 JWT>`.

### Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workflows` | List all workflows |
| `POST` | `/api/workflows` | Create a new workflow |
| `GET` | `/api/workflows/{id}` | Get workflow by ID |
| `PUT` | `/api/workflows/{id}` | Update workflow (nodes, edges, name) |
| `DELETE` | `/api/workflows/{id}` | Delete workflow |
| `POST` | `/api/workflows/{id}/nodes/{node_id}/run` | Run a single node |
| `POST` | `/api/workflows/{id}/run` | Run entire workflow |
| `POST` | `/api/workflows/{id}/nodes/{node_id}/extract-frames` | Save video frame extracts |

### Assets & Uploads

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/assets/presign-upload` | Get S3 presigned URL for direct upload |

### Billing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/billing/balance` | Get current credit balance |
| `GET` | `/api/billing/usage` | Get usage history (logs) |
| `POST` | `/api/billing/deposit` | Add credits / record deposit |

### Agent & Scraping

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/agent/chat` | Chat with the AI workflow assistant |
| `POST` | `/api/scrape` | Scrape a website URL for brand context |

### Internal (Lambda-to-Lambda)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/workflows/execute-background` | Background node execution (auth via shared secret) |
| `POST` | `/api/workflows/job-processor` | Async job orchestration |

---

## Deployment

The API deploys as a Docker container on **AWS Lambda** using the Lambda Web Adapter. The frontend deploys on **AWS Amplify**.

```bash
# Build and deploy API to Lambda
cd apps/api
sam build
sam deploy --config-env prod

# Frontend — push to main branch triggers Amplify auto-deploy
```

See `.agent/workflows/deploy.md` for the full step-by-step deployment workflow.

---

## License

MIT
