# Vanshu AI: Agentic Personal Assistant & Task Orchestration Engine

Vanshu AI is a powerful, decoupled, multi-agent assistant designed to handle long-running background tasks—such as research, document compilation, file synchronization, and email delivery—efficiently and asynchronously.

---

## 🏗️ System Architecture

Vanshu AI uses a decoupled, queue-based architecture to separate short-lived HTTP chat interactions from heavy, compute-intensive background pipelines.

```mermaid
graph TD
    %% Frontend Layer
    A[Vercel Frontend - React/TS] -->|Secure Tunnel| B[Cloudflare Tunnel]
    
    %% Gateway Layer
    B -->|Port 8000| C[FastAPI Gateway - Docker Web]
    
    %% Cache & Database Layer
    C -->|Store/Retrieve Tasks| D[(Supabase SQL - PostgreSQL)]
    C -->|Read/Write Session Context| E[(Redis Cache)]
    C -->|Read Long-term Memory| F[(Qdrant Vector DB)]
    
    %% Task Queue Layer
    C -->|Queue Async Chain| G[(Redis Message Broker)]
    G -->|Dispatch Task Signatures| H[Celery Workers - Docker Worker]
    
    %% External Integrations Layer
    H -->|Search Web| I[DuckDuckGo / WebSearch]
    H -->|Compile Docs| J[WeasyPrint / Pandoc]
    H -->|Upload Files| K[Cloudflare R2 Storage]
    H -->|Deliver Reports| L[Gmail OAuth API]
    H -->|Update Status & Links| D
```

---

## ⚡ Core Capabilities

Vanshu AI operates in two execution modes depending on task complexity:
1. **Synchronous Mode (`sync`)**: Instant chat responses, memory retrieval, and simple tool executions.
2. **Asynchronous Mode (`async_chain`)**: Complex workflows mapped out by a **Planner Subagent**, chained together into Celery task signatures, and executed in the background.

### 🔍 Web Research & Intelligence
* Performs automated web searches using DuckDuckGo.
* Extracts content, filters noise, and compiles synthesis reports.

### 📄 Multi-Format Document Compilation
* Renders high-fidelity PDF documents from Markdown/HTML using WeasyPrint (with fully supported C system libraries).
* Generates structured MS Word briefs (`.docx`) using Pandoc.
* Renders presentation slide decks as formatted PDFs.

### ☁️ Cloud Storage Synchronization
* Automatically uploads compiled reports and slides to Cloudflare R2 object storage.
* Generates secure, signed public download links for artifact retrieval.

### ✉️ Email Delivery & Draft Automation
* Authenticates securely via Gmail OAuth (using persistent `client_secret.json` and `token.json` volumes).
* Drafts introduction emails or directly delivers generated documents to the user's inbox with secure attachments.

### 🧠 Dual-Layer Memory System
* **Short-Term Memory**: Uses Redis to store recent chat messages and maintain context windows.
* **Long-Term Vector Memory**: Uses Qdrant database to store, retrieve, and recall user preferences and historical facts.

---

## 🛠️ Tool Registry & Task Schemas

### 1. Agent Tools (`agent/personalAgent.py`)
* `remember_user_preference`: Stores specific user facts/preferences to Qdrant memory.
* `get_realtime_and_date`: Obtains current timestamps to root context.
* `execute_dynamic_workflow`: Parses plans from the Planner Subagent, wraps steps into a Celery task signature `chain`, dispatches them via Redis, and writes tracking coordinates to Supabase.

### 2. Background Celery Tasks (`tasks/background_tasks.py`)
* `tasks.research_task`: Coordinates web queries and text summarization.
* `tasks.create_pdf_task`: Generates PDF documents from reports.
* `tasks.create_docx_task`: Compiles Pandoc-based Word documents.
* `tasks.render_slides_task`: Renders presentation decks.
* `tasks.upload_r2_task`: Handles cloud storage uploads.
* `tasks.send_email_task`: Sends an email with attachments using Gmail OAuth.
* `tasks.draft_email_task`: Creates a draft email in the user's inbox.

### 3. FastAPI REST Endpoints (`main.py`)
* `POST /chat`: Initiates a message round-trip, processes memory, and launches background chains.
* `GET /task/{task_id}`: Retrieves the status, errors, and download links for a specific background task.
* `GET /tasks/all/{email}`: Lists all background tasks triggered by a user's email address.
* `GET /history/{session_id}`: Returns message history logs for a session.
* `GET /sessions/{email}`: Returns all chat sessions started by a user's email address.
* `POST /telegram`: Receives and routes bot queries to Vanshu AI.

---

## 🚀 Setting Up Local Development

### 1. Prerequisites
* [Docker Desktop](https://www.docker.com/) (version 25+ with Compose v2 plugin)
* [Node.js](https://nodejs.org/) (for frontend compiler)
* [Python 3.12](https://www.python.org/)

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
# AI Models
OPENROUTER_API_KEY="your_openrouter_key"
LOGFIRE_TOKEN="your_pydantic_logfire_token"

# Database & Cache
DATABASE_URL="postgresql://user:pass@host:5432/db"
REDIS_URL="redis://localhost:6379/0"
QDRANT_URL="https://your-qdrant-cluster.io"
QDRANT_API_KEY="your_qdrant_key"

# Cloudflare R2 Storage
CLOUDFLARE_ACCESS_KEY_ID="your_access_key"
CLOUDFLARE_SECRET_ACCESS_KEY_ID="your_secret_key"
CLOUDFLARE_R2_ENDPOINT="https://account-id.r2.cloudflarestorage.com"
CLOUDFLARE_R2_BUCKET="your-bucket-name"
CLOUDFLARE_R2_PUBLIC_URL="https://pub-url.r2.dev"

# Telegram Integration
TELEGRAM_BOT_TOKEN="your_bot_token"
```

### 3. Running the Backend (Docker)
Start the Redis broker, database listener, FastAPI web gateway, and Celery workers:
```bash
docker-compose up -d --build
```

### 4. Running the Frontend
Navigate to the frontend folder, install dependencies, and run the development compiler:
```bash
cd frontend
npm install
npm run dev
```

---

## 🌐 Production Deployment

* **Backend Engine**: Hosted on an Ubuntu Azure VM. Orchestrated using Docker Compose, exposed securely to the internet via an account-less **Cloudflare Tunnel** running in the background.
* **Frontend Dashboard**: Hosted on **Vercel**, fetching data dynamically from the Cloudflare HTTPS Tunnel gateway.
* **Credentials Volume**: Persistent Gmail OAuth credentials (`token.json` and `client_secret.json`) are mounted securely to the VM host filesystem to prevent data loss on rebuilds.
