# Kureita — AI Video Production Platform

Transform your brand into cinematic stories with AI-powered video production. Give us your website URL, and our AI agents craft compelling promotional videos — from script to screen.

## Tech Stack

### Frontend (`apps/web`)
- **Next.js 15** with React 19
- **TypeScript**
- **Tailwind CSS** with custom design system
- **Framer Motion** for animations
- **Formik + Yup** for forms
- **Lucide React** for icons
- **Axios** for API calls

### Backend (`apps/api`)
- **FastAPI** with Python 3.11+
- **Pydantic** for validation
- **uv** for package management
- Google **Gemini API** (Veo 3.1 for video)
- **ElevenLabs** for voiceover
- **Celery + Redis** for background jobs

## Getting Started

### Prerequisites
- Node.js 20+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Redis (for background jobs)

### Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

The frontend runs at `http://localhost:3000`

### Backend Setup

```bash
cd apps/api
uv sync
uv run uvicorn main:app --reload --port 8000
```

The API runs at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Environment Variables

Create a `.env` file in `apps/api`:

```env
# External APIs
GEMINI_API_KEY=your_gemini_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# Database (optional for MVP)
DATABASE_URL=postgresql+asyncpg://localhost:5432/kureita

# Redis
REDIS_URL=redis://localhost:6379

# Storage
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=kureita-assets
```

## Project Structure

```
mvp/
├── apps/
│   ├── web/                 # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/         # App router pages
│   │   │   ├── components/  # UI components
│   │   │   └── lib/         # Utilities
│   │   └── package.json
│   └── api/                 # FastAPI backend
│       ├── app/
│       │   ├── api/         # API routes
│       │   ├── core/        # Config, settings
│       │   └── models/      # Pydantic models
│       ├── main.py
│       └── pyproject.toml
├── packages/                # Shared packages (future)
├── turbo.json
└── package.json
```

## Features

### Current (MVP)
- [x] Website scraping & brand analysis
- [x] Project creation flow
- [x] Dashboard & project listing
- [x] Project detail view with progress
- [x] Elegant, minimal UI design

### Planned
- [ ] Veo 3.1 video generation integration
- [ ] ElevenLabs voiceover integration
- [ ] Remotion video composition
- [ ] AI story & script generation
- [ ] Real-time generation progress
- [ ] Video preview & download

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List all projects |
| POST | `/api/projects` | Create new project |
| GET | `/api/projects/{id}` | Get project details |
| PATCH | `/api/projects/{id}` | Update project |
| DELETE | `/api/projects/{id}` | Delete project |
| POST | `/api/projects/{id}/start` | Start generation |
| POST | `/api/scrape` | Scrape website |
| POST | `/api/generate/story` | Generate story |
| POST | `/api/generate/video` | Generate video |
| POST | `/api/generate/voiceover` | Generate voiceover |

## License

MIT

