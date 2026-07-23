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
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from datetime import datetime

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