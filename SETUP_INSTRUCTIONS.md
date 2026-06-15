# Quick Setup Guide for Arinar V2 🚀

Hey! Here's everything you need to get Arinar running on your machine.

## What You'll Need (5 minutes to install)

1. **Docker Desktop** → https://www.docker.com/products/docker-desktop
2. **Node.js 18+** → https://nodejs.org/
3. **Python 3.11** → https://www.python.org/downloads/
4. **OpenRouter API Key** (FREE) → https://openrouter.ai/

## Setup Steps (10 minutes)

### 1. Clone & Enter Project
```bash
git clone https://github.com/vprasanna7/arinar-2026.git
cd arinar-2026/arinar-v2
```

### 2. Start Database
```bash
# Make sure Docker Desktop is running, then:
cd infra/docker
docker-compose up -d db
cd ../..
```

### 3. Start Backend (Terminal 1)
```bash
cd apps/api
pip install -r requirements.txt
cp .env.example .env.local
# Edit .env.local if needed (defaults should work)
python -m uvicorn src.main:app --reload --port 8000
```

Backend runs at: **http://localhost:8000**

### 4. Start Frontend (Terminal 2)
```bash
cd apps/web
npm install
cp .env.example .env.local
# Edit .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Frontend runs at: **http://localhost:3000**

### 5. Add Your API Key
1. Open http://localhost:3000
2. Go to Settings (⚙️ icon)
3. Paste your OpenRouter API key
4. Click "Save & Verify"

## You're Done! 🎉

Click **"Create New Debate"** and start playing with the 101 AI agents!

---

## First Debate Idea

Try: **"Should startups use TypeScript or JavaScript?"**

Add these agents:
- **Senior Engineer (Pragmatic)** - will advocate for TypeScript
- **Tech Nerd** - will be enthusiastic about features
- **Startup Evaluator (YC Partner)** - will focus on shipping fast
- **Elon Musk** - first principles thinking

Watch them debate in real-time! Click "View reasoning" to see their chain-of-thought.

---

## Troubleshooting

**Database error?**
```bash
docker ps | grep postgres
# Should see "arinar-db" running
# If not: docker-compose up -d db
```

**Backend won't start?**
```bash
python --version  # Should be 3.11+
cd apps/api
pip install -r requirements.txt --force-reinstall
```

**Frontend won't start?**
```bash
cd apps/web
rm -rf .next node_modules
npm install
```

**Need help?** Check the full README.md or create a GitHub issue.

---

## Cool Features to Try

1. **Live Thinking** - See agents think step-by-step in real-time
2. **Autonomous Behaviors** - Watch agents form coalitions and challenge each other
3. **101 Agent Personas** - Tax experts, startup evaluators, iconic voices (Elon, Steve Jobs, etc.)
4. **Constitutional AI** - Every response goes through 3-stage validation
5. **Intervene** - Jump in anytime to guide the debate

Have fun! 🚀
