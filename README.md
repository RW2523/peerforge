# Arinar V2 - AI-Powered Debate Platform 🎯

**Intelligent multi-agent debates with real-time thinking, Constitutional AI, and 100+ specialized personas**

Arinar is an AI debate platform where multiple specialized AI agents engage in structured, thoughtful discussions. Watch agents think in real-time, collaborate on documents, and synthesize insights from diverse perspectives.

---

## ✨ Key Features

- **100+ Specialized Agent Personas**: Tax experts, startup evaluators, engineers, designers, medical specialists, iconic voices (Elon Musk, Steve Jobs, etc.)
- **Constitutional AI Pipeline**: 3-stage reasoning (Reasoning → Response → Validation) for higher quality agent outputs
- **Live Chain-of-Thought**: See agents think in real-time as they process and debate
- **Multi-Agent Debates**: 2-6 agents debating complex topics with authentic perspectives
- **Real-time WebSocket Updates**: Live debate feed with typing indicators and presence
- **Autonomous Behaviors**: Agents form coalitions, challenge each other, and adapt strategies
- **Document Collaboration**: Agents can contribute to shared documents during debates
- **Memory System**: Agents remember past debates and learn over time

---

## 🚀 Quick Start

### Prerequisites

1. **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop)
2. **Node.js 18+** - [Download here](https://nodejs.org/)
3. **Python 3.11** - [Download here](https://www.python.org/downloads/)
4. **OpenRouter API Key** - [Get one free](https://openrouter.ai/)

### Installation Steps

#### 1. Clone the Repository
```bash
git clone https://github.com/vprasanna7/arinar-2026.git
cd arinar-2026/arinar-v2
```

#### 1A. Run the Application Using the Startup Script

The easiest way to run the full application locally is to use the provided startup script.

From the `arinar-v2` folder, run:

```bash
chmod +x run_app.sh
./run_app.sh
```

This script will automatically:

* Start the required Docker services: PostgreSQL, Redis, and MinIO
* Create the backend `.env.local` file
* Create the frontend `.env.local` file
* Set up the Python virtual environment if needed
* Install backend dependencies if needed
* Run database migrations
* Install frontend dependencies if needed
* Start the FastAPI backend
* Start the Next.js frontend

After the script starts successfully, open the frontend at:

```bash
http://localhost:3001
```

If running on a remote VM, use the network URL shown in the terminal, for example:

```bash
http://<VM-IP>:3001
```

The backend API runs at:

```bash
http://localhost:8000
```

API documentation is available at:

```bash
http://localhost:8000/docs
```

To stop the application, press:

```bash
Ctrl + C
```

in the terminal where `./run_app.sh` is running.

> Note: The script uses the local Docker setup in `infra/docker/docker-compose.yml` and runs the frontend on port `3001`.


#### 2. Start PostgreSQL Database
```bash
# Start Docker Desktop first, then:
cd infra/docker
docker-compose up -d db

# Verify it's running:
docker ps | grep postgres
# You should see "arinar-db" running on port 5432
```

#### 3. Set Up Backend (FastAPI)
```bash
cd apps/api

# Install Python dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env.local

# Edit .env.local with your settings (use your favorite editor)
# - DATABASE_URL should work as-is (points to Docker PostgreSQL)
# - Add your SUPABASE credentials if you have them (optional for local dev)

# Run database migrations
python -m alembic upgrade head

# Start the API server
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be running at: **http://localhost:8000**

Test it: `curl http://localhost:8000/health` (should return `{"status":"healthy"}`)

#### 4. Set Up Frontend (Next.js)
```bash
# Open a new terminal
cd apps/web

# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local

# Edit .env.local
# - NEXT_PUBLIC_API_URL=http://localhost:8000
# - Add your SUPABASE_URL and keys if you have them

# Start the development server
npm run dev
```

The frontend will be running at: **http://localhost:3000**

#### 5. Configure Your API Key

1. Open **http://localhost:3000** in your browser
2. Go to **Settings** (gear icon in nav bar)
3. Enter your **OpenRouter API Key**
4. Click **Save & Verify**

---

## 🎮 Usage Guide

### Creating Your First Debate

1. **Home Page** → Click **"Create New Debate"**

2. **Step 1: Basic Info**
   - Enter debate title (e.g., "Should we use TypeScript?")
   - Add problem statement (what you want to discuss)
   - Set time limit (optional) or max rounds (optional)

3. **Step 2: Materials** (Optional)
   - Upload documents, paste links, or add context
   - Agents will reference these materials during debate

4. **Step 3: Participants**
   - Click **"Add from Template"**
   - Browse 100+ agent personas by category:
     - **Product**: PMs, growth experts
     - **Engineering**: Architects, pragmatic engineers
     - **Design**: UX researchers, designers
     - **Business**: CFOs, legal counsel
     - **Tax & Accounting**: CPAs, tax strategists, crypto specialists
     - **Marketing**: Brand strategists, growth marketers
     - **Startup Evaluators**: YC partners, VCs, tech diligence
     - **Iconic Voices**: Elon Musk, Steve Jobs, Jeff Bezos, etc.
   - Select 2-6 agents with diverse perspectives

5. **Step 4: Preflight** (Optional)
   - AI analyzes your setup and suggests improvements
   - Review "Prep Pack" with debate preview

6. **Step 5: Review & Launch**
   - Verify everything looks good
   - Click **"Enter Room"**

### Running a Debate

Once in the debate room:

- **Next Turn**: Click to have the next agent speak
- **Intervene**: Type a message to guide the debate
- **Watch Thinking**: Expand "View reasoning" to see agent's chain-of-thought
- **Agent Behaviors**: See autonomous actions (coalitions, challenges, strategic moves)
- **Documents**: Collaborate on shared documents (if enabled)
- **Extend Debate**: Add more rounds or time if needed

### Understanding Agent Thinking

Each agent uses a **Constitutional AI pipeline**:

1. **🤔 Stage 1: Reasoning**
   - Reviews past messages
   - Analyzes the debate state
   - Forms a stance and confidence level
   - Identifies who to respond to

2. **✍️ Stage 2: Response**
   - Generates message based on reasoning
   - Uses authentic character voice
   - Addresses other agents directly

3. **✅ Stage 3: Validation**
   - Checks for hallucinations (citing non-existent participants)
   - Verifies consistency with previous statements
   - Ensures debate rules are followed
   - Regenerates if issues found

---

## 📁 Project Structure

```
arinar-v2/
├── apps/
│   ├── api/                    # FastAPI backend (Python)
│   │   ├── src/
│   │   │   ├── routes/        # API endpoints
│   │   │   ├── agent_*.py     # Agent AI logic
│   │   │   ├── turn_orchestrator.py  # Debate control
│   │   │   └── websocket_*.py # Real-time updates
│   │   └── requirements.txt
│   │
│   └── web/                   # Next.js frontend (TypeScript/React)
│       ├── src/
│       │   ├── app/          # Pages (home, room, setup, settings)
│       │   ├── components/   # UI components
│       │   ├── hooks/        # React hooks
│       │   └── lib/          # API client, WebSocket client
│       └── package.json
│
├── infra/
│   └── docker/               # PostgreSQL, Redis, etc.
│       └── docker-compose.yml
│
├── docs/                     # Architecture docs
└── reports/                  # Feature reports
```

---

## 🔧 Configuration

### Environment Variables

**Backend (`.env.local` in `apps/api/`):**
```bash
# Database (works with Docker PostgreSQL)
DATABASE_URL=postgresql://postgres:your-super-secret-postgres-password@127.0.0.1:5432/postgres

# Supabase (optional for local dev)
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Auth (set to false for local demo)
REQUIRE_AUTH=false
```

**Frontend (`.env.local` in `apps/web/`):**
```bash
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Supabase (optional for local dev)
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### OpenRouter Models

Default model: `openai/gpt-4o-mini` (cost-optimized, fast)

You can change models in:
- **Settings page** (global defaults)
- **Setup flow** (per-debate)
- **Agent templates** (per-agent defaults)

---

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# If not running, start it
cd infra/docker
docker-compose up -d db

# Check logs
docker logs arinar-db
```

### Backend Not Starting
```bash
# Check Python version (needs 3.11+)
python --version

# Reinstall dependencies
cd apps/api
pip install -r requirements.txt --force-reinstall

# Check for port conflicts
lsof -i :8000
# If port is in use, kill the process or use a different port
```

### Frontend Not Starting
```bash
# Clear cache and reinstall
cd apps/web
rm -rf .next node_modules
npm install
npm run dev
```

### "Failed to load templates/agents" Error
```bash
# Make sure:
# 1. Docker PostgreSQL is running (docker ps)
# 2. Backend API is running (curl http://localhost:8000/health)
# 3. Frontend is pointing to correct API URL (check .env.local)

# Test the endpoint directly
curl http://localhost:8000/agent-templates
# Should return JSON array of 101 agent templates
```

### Debates Not Showing Thinking
- Make sure you're using the **latest code** (pulled from main branch)
- Thinking feature requires **WebSocket connection** (check browser console for errors)
- Try refreshing the page after clicking "Next Turn"

---

## 🎨 Agent Categories

Browse our **101 specialized agents**:

### Core Categories
- **Facilitator**: Ultimate Host (neutral moderator)
- **Product**: PMs with various styles (visionary, pragmatic, growth-focused)
- **Engineering**: Architects, pragmatic engineers, ship-it mentality
- **Design**: UX researchers, design-led thinkers
- **Business**: CFOs, legal counsel, strategy experts

### Specialized Categories
- **Tax & Accounting** (12 agents): CPAs, tax strategists, enrolled agents, real estate specialists, crypto experts, retirement planners
- **Immigration** (3 agents): Policy experts, rights advocates, corporate consultants
- **Marketing** (3 agents): Brand strategists, growth marketers, content experts
- **Startup Evaluators** (3 agents): YC-style partners, VC analysts, tech due diligence
- **Subject Matter Experts** (3 agents): Industry specialists, academics, practitioners

### Thinking Styles
- **Analysts**: Rational thinkers, domain experts, data-driven
- **Critics**: Devil's advocates, quality-focused
- **Empathizers**: Heart-centered, human impact focused
- **Coaches**: Behavioral psychologists, change facilitators

### Tech & Industry
- **Tech Specialists**: Apple, Windows, GPU, AI/ML experts
- **Medical Specialists**: Surgeons, cardiologists, neurologists, psychiatrists
- **Legal Professionals**: Immigration attorneys, corporate lawyers
- **Real Estate**: Property tax experts, investment advisors

### Iconic Voices
- Elon Musk (first principles, Mars-focused)
- Steve Jobs (simplicity obsessed, design-driven)
- Jeff Bezos (customer-obsessed, long-term)
- Tim Cook (operational excellence)
- Yuval Noah Harari (big history, philosophical)
- Naval Ravikant (wealth & wisdom)
- Paul Graham (startup philosophy)
- Peter Thiel (contrarian, zero-to-one)
- Ray Dalio (principles-based)
- Warren Buffett (value investing)
- Bill Gates (technologist & philanthropist)

### Wildcards
- Visionaries, tech nerds, first principles thinkers, customer champions

---

## 📊 Tech Stack

**Frontend:**
- Next.js 15 (React framework)
- TypeScript
- WebSocket client (real-time updates)
- CSS Modules (styling)

**Backend:**
- FastAPI (Python web framework)
- PostgreSQL (database)
- WebSockets (real-time)
- OpenRouter (LLM API gateway)

**Infrastructure:**
- Docker (PostgreSQL, Redis)
- Supabase (auth & cloud DB, optional)

---

## 🤝 Contributing

This is a demo/prototype project. Feel free to:
- Experiment with new agent personas
- Modify debate rules and prompts
- Add new features
- Share feedback

---

## 📝 License

[Your License Here]

---

## 📧 Support

Questions? Issues? Reach out to:
- GitHub Issues: https://github.com/vprasanna7/arinar-2026/issues
- [Your Contact Info]

---

## 🎯 What Makes Arinar Special?

1. **Constitutional AI**: Every agent response goes through reasoning → generation → validation for higher quality
2. **Live Thinking**: See exactly how agents think and decide in real-time
3. **Authentic Personas**: 101 deeply characterized agents with distinct voices and perspectives
4. **Real Debates**: Agents genuinely disagree, form coalitions, and challenge each other
5. **Production-Ready**: Built with scalability, WebSockets, and modern best practices

Start debating with AI! 🚀
