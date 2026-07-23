from config.settings import setting
from memory.database import (
    init_db, engine, User, ChatSession, Message, Task, 
    get_or_create_user, create_chat_session, save_message
)
from memory.redis_memory import RedisMemory
from memory.qdrant_memory import QdrantMemory
from subagent.upload import R2Storage
from subagent.communication import GmailAuth
from agent.personalAgent import personal_agent, AgentDeps, execute_dynamic_workflow
import os
from contextlib import asynccontextmanager
from typing import Optional, List
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks,Request
from fastapi.responses import HTMLResponse 
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from datetime import datetime
import httpx
import re
import asyncio

@asynccontextmanager
async def lifespan(app:FastAPI):
    init_db()
    yield


app =FastAPI(
        title="Vanshu AI Personal assistant api",
         description="Backend API powering the Luna personal assistant with Redis, Supabase, Qdrant, and Celery.",
    version="1.0.0",
    lifespan=lifespan
    )

if os.path.exists("frontend/dist/assets"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
# 🟢 Serve the built React index.html at the root URL
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = "frontend/dist/index.html"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Vanshu AI Backend is running</h1><p>Please run <code>npm run build</code> inside the frontend directory.</p>"

class ChatReqest(BaseModel):
    email: str = Field(..., example="its.sumitpandit@gmail.com")
    name: str = Field("User", example="Sumit Pandit")
    prompt: str = Field(..., example="create a report on crypto market and send it to my mail")
    session_id: Optional[UUID] = Field(None, description="Optional session ID to continue an existing chat")


class ChatResponse(BaseModel):
    session_id:UUID
    user_id:UUID
    execution_mode:str
    response:str
    task_id:Optional[str]=None


r2= R2Storage(
    access_key=setting.CLOUDFLARE_ACCESS_KEY_ID,
    secret_key=setting.CLOUDFLARE_SECRET_ACCESS_KEY_ID,
    endpoint_url=setting.CLOUDFLARE_R2_ENDPOINT,
    bucket=setting.CLOUDFLARE_R2_BUCKET,
    public_url=setting.CLOUDFLARE_R2_PUBLIC_URL,
)

redis_mem = RedisMemory()
qdrant_mem = QdrantMemory()

@app.post("/chat",response_model=ChatResponse)
async def chat_endpoint(request:ChatReqest):

    user = get_or_create_user(email=request.email,name=request.name)
    if request.session_id:
        with Session(engine) as session:
            chat_session = session.get(ChatSession,request.session_id)
            if not chat_session:
                raise HTTPException(status_code=404,detail="chat session not found")
    else:
        chat_session = create_chat_session(user_id=user.id,title=f"Chat {datetime.now().strftime('%Y-%m-%d')}")
    save_message(session_id=chat_session.id,role="user",content=request.prompt)

    deps = AgentDeps(
        gmail_auth=GmailAuth(),
        r2_storage=r2,
        redis_mem=redis_mem,
        qdrant_mem=qdrant_mem,
        user_id=str(user.id),
        session_id=str(chat_session.id)
    )
    final_output=""
    task_id=None
    execution_mode="sync"

    try:
        result = await personal_agent.run(request.prompt,deps=deps)
        final_output =result.output

        execution_mode = deps.execution_mode or "sync"
        task_id = deps.active_task_id

         # Check if the output indicates an async task pipeline was started
        if "Task Chain ID" in final_output or "Celery" in final_output:
            execution_mode = "async_chain"
            # Extract task ID from output text if needed, or inspect result
            # E.g. "Successfully queued background Celery task pipeline. Chain Task ID: <id>"
            parts = final_output.split("Chain Task ID: ")
            if len(parts) > 1:
                task_id = parts[1].strip()
        # 6. Save agent response to Database & Redis
        save_message(session_id=chat_session.id, role="assistant", content=final_output)
        redis_mem.append_message(str(chat_session.id), "user", request.prompt)
        redis_mem.append_message(str(chat_session.id), "assistant", final_output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent runtime error: {str(e)}")
    return ChatResponse(
        session_id=chat_session.id,
        user_id=user.id,
        execution_mode=execution_mode,
        response=final_output,
        task_id=task_id
    )
    


@app.get("/task/{task_id}")
async def get_task_status(task_id: UUID):
    """Retrieves status and results for background Celery tasks from Supabase."""
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found in tracking registry")
        
        return {
            "task_id": task.id,
            "status": task.status,
            "result": task.result,
            "download_link": task.link,
            "created_at": task.created_at
        }


@app.get("/history/{session_id}")
async def get_chat_history(session_id: UUID):
    """Fetches full chat history logs for a session."""
    with Session(engine) as session:
        messages = session.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()
        return messages



# 🟢 API to list historical sessions for a user's email
@app.get("/sessions/{email}")
async def get_user_sessions(email: str):
    """List all chat sessions for a user by email."""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            return []
        sessions = session.exec(
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.created_at.desc())
        ).all()
        return sessions


# Simple email validation pattern
EMAIL_REGEX = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')

# 🟢 Telegram Webhook Endpoint
@app.post("/telegram")
async def telegram_webhook(request: Request):
    """Webhook to receive messages from the Telegram bot and route them to Vanshu."""
    token = getattr(setting, "TELEGRAM_BOT_TOKEN", None)
    if not token:
        return {"status": "ok", "detail": "Telegram bot token is not configured"}
        
    payload = await request.json()
    message = payload.get("message")
    if not message or "text" not in message:
        return {"status": "ok"}
        
    chat_id = message["chat"]["id"]
    text = message["text"].strip()
    first_name = message["from"].get("first_name", "User")
    
    # 1. Lookup user by telegram_id
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == str(chat_id))).first()
        
        # 2. Onboarding Flow if user is not registered
        if not user:
            if EMAIL_REGEX.match(text):
                existing_user = session.exec(select(User).where(User.email == text)).first()
                if existing_user:
                    existing_user.telegram_id = str(chat_id)
                    session.add(existing_user)
                    user = existing_user
                else:
                    user = User(email=text, name=first_name, telegram_id=str(chat_id))
                    session.add(user)
                session.commit()
                session.refresh(user)
                
                await send_telegram_message(
                    token, 
                    chat_id, 
                    f"Email registered successfully! I am Vanshu, your AI Personal Assistant. How can I help you today? 😊"
                )
            else:
                await send_telegram_message(
                    token, 
                    chat_id, 
                    "Welcome! I am Vanshu, your AI Personal Assistant. 🤖\n\nTo get started, please reply with your email address so I can set up your profile and deliver reports to your inbox."
                )
            return {"status": "ok"}

    # 3. Route prompt to Vanshu AI Orchestrator
    with Session(engine) as session:
        chat_session = session.exec(
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.created_at.desc())
        ).first()
        if not chat_session:
            chat_session = ChatSession(user_id=user.id, title="Telegram Chat Session")
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)
            
    # Save the user's message
    save_message(session_id=chat_session.id, role="user", content=text)
    
    deps = AgentDeps(
        gmail_auth=GmailAuth(),
        r2_storage=r2,
        redis_mem=redis_mem,
        qdrant_mem=qdrant_mem,
        user_id=str(user.id),
        session_id=str(chat_session.id)
    )
    
    # Run the assistant in a background task so we respond immediately to Telegram's 
    # webhook connection, avoiding webhook timeouts during heavy web research or PDF creation.
    asyncio.create_task(run_assistant_and_reply_telegram(token, chat_id, text, deps, chat_session.id))
    
    return {"status": "ok"}


async def send_telegram_message(token: str, chat_id: int, text: str):
    """Helper to send a message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            })
        except Exception as e:
            print(f"Error sending Telegram message: {e}")


async def run_assistant_and_reply_telegram(token: str, chat_id: int, prompt: str, deps: AgentDeps, session_id: UUID):
    """Runs the personal agent and sends the outcome to the Telegram chat."""
    try:
        result = await personal_agent.run(prompt, deps=deps)
        response_text = result.output
        
        # Save assistant response
        save_message(session_id=session_id, role="assistant", content=response_text)
        redis_mem.append_message(str(session_id), "user", prompt)
        redis_mem.append_message(str(session_id), "assistant", response_text)
        
        # Reply to user on Telegram
        await send_telegram_message(token, chat_id, response_text)
    except Exception as e:
        error_msg = f"Sorry, I encountered an error while processing your request: {str(e)}"
        await send_telegram_message(token, chat_id, error_msg)
