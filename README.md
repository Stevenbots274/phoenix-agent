# 🔥 PHOENIX Agent

**Multi-Agent AI Platform** — Upload files, analyze code, push to GitHub, and chat with AI using your own API keys or our infrastructure.

![PHOENIX Agent](https://phoenix-agent.fly.dev/static/og-card.png)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 💬 **AI Chat** | Chat with multiple AI models. Use infrastructure or bring your own keys. |
| 📁 **File Upload** | Upload any file type — ZIP, code, documents. Extract and analyze. |
| 🐙 **GitHub Integration** | Create repos, push ZIP contents, manage code from chat. |
| 🤖 **Multi-Agent System** | Code review, file analysis, GitHub operations — all AI-powered. |
| 🔐 **Bring Your Own Keys** | Use OpenAI or Google Gemini API keys. Toggle infrastructure on/off. |
| ⚡ **Fast & Secure** | FastAPI + Neon PostgreSQL + JWT auth + persistent chat history. |

---

## 🚀 Quick Deploy to Fly.io

### 1. Clone & Setup

```bash
git clone <your-repo>
cd phoenix-agent
```

### 2. Create Neon Database

1. Go to [neon.tech](https://neon.tech) and create a new project
2. Copy the connection string (looks like: `postgresql://user:pass@host.neon.tech/neondb?sslmode=require`)

### 3. Deploy

```bash
# Install Fly CLI if not already
# https://fly.io/docs/hands-on/install-flyctl/

# Login to Fly
fly auth login

# Launch the app
fly launch

# Set secrets (NEVER commit these to git!)
fly secrets set DATABASE_URL="postgresql://user:pass@host.neon.tech/neondb?sslmode=require"
fly secrets set SECRET_KEY="your-random-64-char-secret-key-change-me"
fly secrets set INFRASTRUCTURE_BASE_URL="https://ollama-fastapi-railway-deployment.fly.dev/"
fly secrets set INFRASTRUCTURE_API_KEY="ollama_thfd2mMOx7E8Y14i_fBUMxej5JolfIXf1WIDQL8cD7g"

# Deploy
fly deploy
```

### 4. Open Your App

```bash
fly open
```

Your PHOENIX Agent is live! 🎉

---

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | Neon PostgreSQL connection string |
| `SECRET_KEY` | ✅ | JWT signing key (generate random 64+ chars) |
| `INFRASTRUCTURE_BASE_URL` | ✅ | Self-hosted Ollama/Azure endpoint URL |
| `INFRASTRUCTURE_API_KEY` | ✅ | API key for infrastructure endpoint |
| `APP_NAME` | ❌ | App display name (default: PHOENIX Agent) |
| `DEBUG` | ❌ | Debug mode (default: false) |

---

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Register new user (email + password) |
| `POST` | `/api/auth/signin` | Login existing user |
| `GET` | `/api/auth/me` | Get current user profile |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/send` | Send message to AI |
| `GET` | `/api/chat/sessions` | List chat sessions |
| `GET` | `/api/chat/sessions/{id}/messages` | Get session messages |
| `DELETE` | `/api/chat/sessions/{id}` | Delete session |

### Files
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload/` | Upload any file |
| `GET` | `/api/upload/` | List uploaded files |
| `POST` | `/api/upload/analyze` | Analyze file with AI |
| `DELETE` | `/api/upload/{id}` | Delete file |

### GitHub
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/github/connect` | Connect GitHub PAT |
| `GET` | `/api/github/repos` | List user repos |
| `POST` | `/api/github/repos` | Create repository |
| `POST` | `/api/github/push` | Push files to repo |
| `POST` | `/api/github/push-zip` | Push ZIP to repo |
| `POST` | `/api/github/create-and-push` | Create repo + push ZIP |

### Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/settings/` | Get user settings |
| `PUT` | `/api/settings/` | Update settings |
| `GET` | `/api/settings/models` | List available AI models |

### Agent Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/agent/task` | Run agent task |
| `GET` | `/api/agent/tasks` | List tasks |
| `GET` | `/api/agent/tasks/{id}` | Get task result |
| `POST` | `/api/agent/code-review` | Review code |
| `POST` | `/api/agent/chat` | Direct agent chat |

---

## 🏗️ Tech Stack

- **Backend**: FastAPI + asyncpg + SQLAlchemy (async)
- **Frontend**: Vanilla JavaScript SPA (no build step)
- **Database**: Neon PostgreSQL (serverless)
- **AI Backends**: 
  - Infrastructure: Self-hosted Ollama/Azure (hidden from users)
  - User-provided: OpenAI GPT-4o / Google Gemini
- **Auth**: JWT + bcrypt password hashing
- **Deployment**: Fly.io (Docker container)

---

## 🎨 Project Structure

```
phoenix-agent/
├── app/
│   ├── main.py                 # FastAPI app entry
│   ├── core/
│   │   ├── config.py           # Settings (.env)
│   │   ├── database.py         # Neon DB + SQLAlchemy models
│   │   └── security.py         # JWT auth + password hashing
│   ├── services/
│   │   ├── ai_service.py       # Multi-provider AI (Azure/Ollama/OpenAI/Gemini)
│   │   ├── github_service.py   # GitHub API integration
│   │   └── agent_service.py    # Multi-agent orchestration
│   └── routers/
│       ├── auth.py             # Sign up / Sign in
│       ├── chat.py             # Chat sessions & messages
│       ├── github.py            # Repo creation & push
│       ├── upload.py            # File upload & analysis
│       ├── settings.py          # AI provider & profile config
│       └── agent.py             # Agent tasks
├── migrations/                  # Alembic DB migrations
├── static/
│   └── index.html              # Complete SPA frontend
├── Dockerfile
├── fly.toml                    # Fly.io deployment config
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔐 Security Notes

- **Infrastructure keys** (`INFRASTRUCTURE_API_KEY`, `INFRASTRUCTURE_BASE_URL`) are hidden from users. Set them as Fly.io secrets.
- **User API keys** (OpenAI, Gemini) are stored per-user in the database. Users can add/remove them anytime.
- **GitHub tokens** are stored per-user. Users must create a PAT with `repo` scope at [github.com/settings/tokens](https://github.com/settings/tokens).
- **JWT tokens** expire after 7 days. Users must re-login after expiration.
- **Passwords** are hashed with bcrypt before storage.

---

## 💡 Usage Tips

### Chat Commands
- **"Create a repo and push this"** — Upload a ZIP in chat, then say this. PHOENIX will create a repo and push all files.
- **"Analyze this file"** — Upload a file, then ask PHOENIX to analyze it.
- **"Review my code"** — Paste code and ask for a review.

### Settings
1. Go to **Settings** → toggle **Use Infrastructure** on/off
2. Add your **OpenAI** or **Gemini** API key
3. Go to **GitHub** → connect your **Personal Access Token**
4. Select your preferred **AI model** in the chat

---

## 📝 License

MIT License — Built with 🔥 by Phoenix.

---

## 🆘 Support

- Create an issue on GitHub
- Contact: [your-email]
- Twitter: [@CryptoPhoenixz](https://twitter.com/CryptoPhoenixz)
