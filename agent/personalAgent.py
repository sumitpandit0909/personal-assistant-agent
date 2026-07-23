from uuid import uuid4
from pydantic_ai import RunContext
from memory.database import create_task_record
from uuid import UUID
from typing import Optional
import sys
import asyncio
from dataclasses import dataclass
from pydantic_graph import End
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')
from pydantic_ai import Agent
from config.settings import model
from subagent.communication import GmailAuth,communication_agent
from subagent.document import document_subagent
from subagent.upload import document_upload_agent, R2Storage
from subagent.planner import planner_subagent
from subagent.research import research_subagent
from pydantic_ai.capabilities import WebSearch
from pydantic_ai_harness.subagents import SubAgents,SubAgent
import logfire
from celery import chain, signature
from memory.redis_memory import RedisMemory
from memory.qdrant_memory import QdrantMemory

logfire.configure()
logfire.instrument_system_metrics()
logfire.instrument_pydantic_ai()

@dataclass
class AgentDeps:
    gmail_auth: GmailAuth
    r2_storage: R2Storage
    redis_mem: RedisMemory
    qdrant_mem: QdrantMemory
    user_id: str
    session_id: str
    active_task_id: Optional[str] = None    # 🟢 ADD THIS
    execution_mode: Optional[str] = None    # 🟢 ADD THIS




personal_agent = Agent[AgentDeps](
    model,
    deps_type=AgentDeps,
    instructions="""
    You are Vanshu, a helpful personal assistant equipped with long-term and short-term memory.
    Assist the user in their day-to-day tasks by understanding their needs and preferences.
    
    CRITICAL ORCHESTRATION RULES:
    1. Before taking any action on a user request, you MUST delegate the request to `planner_subagent` to analyze it and produce a DynamicWorkflowPlan.
    2. Once `planner_subagent` returns the plan:
       - If the execution mode is "async_chain", you MUST immediately call the `execute_dynamic_workflow` tool with the plan and return the result to the user. Do NOT attempt to run any other subagent steps.
       - If the execution mode is "sync", execute the steps returned in the plan sequentially.
    """
    ,
    capabilities=[
        SubAgents(agents=[
            SubAgent(planner_subagent),
            SubAgent(research_subagent),
            SubAgent(document_subagent),
            SubAgent(document_upload_agent),
            SubAgent(communication_agent)
        ]),
        WebSearch(local='duckduckgo')
    ]
)

@personal_agent.system_prompt
async def inject_memories(ctx:RunContext[AgentDeps])-> str:
    """
    Before every prompt , injecr relevant facts retrived from Qdrant vector memory.
    """
    try:
        recalled=ctx.deps.qdrant_mem.recall_facts(user_id=ctx.deps.user_id,
        query=ctx.prompt,top_k=5)
        if recalled:
            return f"\n[Recalled Memories & User Preferences]:\n{recalled}\n"
    except Exception as e:
        print(f"[Memory Warning] Failed to recall facts: {e}")
    return ""

@personal_agent.tool
async def remember_user_preference(ctx: RunContext[AgentDeps], preference_text: str) -> str:
    """Call this tool whenever the agent responds finally with result,and user prompt"""
    ctx.deps.qdrant_mem.store_fact(
        user_id=ctx.deps.user_id, 
        fact_text=preference_text, 
        session_id=ctx.deps.session_id
    )
    return f"Successfully saved to long-term memory: '{preference_text}'"

@personal_agent.tool_plain
def get_realtime_and_date():
    """
    Get the current date and time.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@personal_agent.tool
async def execute_dynamic_workflow(ctx: RunContext[AgentDeps], plan_json: str) -> str:
    """
    Takes the planned DynamicWorkflowPlan JSON, parses it, and executes it.
    If async_chain, compiles and starts the Celery chain.
    If sync, returns instructions to execute step-by-step.
    """
    from subagent.planner import DynamicWorkflowPlan
    import json
    
    # Parse the LLM's plan
    plan_dict = json.loads(plan_json)
    plan = DynamicWorkflowPlan(**plan_dict)
    if plan.execution_mode == "async_chain":
        if not plan.task_chain:
            return "Task chain was marked async but is empty."
            
        celery_sigs = []
        for task_call in plan.task_chain:
            sig = signature(task_call.task_name, kwargs=task_call.kwargs)
            celery_sigs.append(sig)
            
        # Build and dispatch the chain 
        workflow = chain(*celery_sigs)
        result = workflow.delay()
        # Write the initial task state as "pending" to the database
        create_task_record(
            task_id=result.id, 
            user_id=UUID(ctx.deps.user_id), 
            task_name="Report Generation Pipeline"
        )
        ctx.deps.active_task_id=str(result.id)
        ctx.deps.execution_mode="async_chain"
        
        return f"Successfully queued background Celery task pipeline. Chain Task ID: {result.id}"
        return f"Successfully queued background Celery task pipeline. Chain Task ID: {result.id}"
    else:
        # For sync execution, tell the orchestrator to execute the step list
        steps_str = "\n".join(
            f"Step {s.step_number}: Call {s.target_subagent} with instructions: {s.task_description}" 
            for s in plan.sync_steps
        )
        return f"Sync Mode Selected. Please execute the following steps:\n{steps_str}"

# r2 = R2Storage(
#     access_key=setting.CLOUDFLARE_ACCESS_KEY_ID,
#     secret_key=setting.CLOUDFLARE_SECRET_ACCESS_KEY_ID,
#     endpoint_url=setting.CLOUDFLARE_R2_ENDPOINT,
#     bucket=setting.CLOUDFLARE_R2_BUCKET,
#     public_url=setting.CLOUDFLARE_R2_PUBLIC_URL,
# )
# redis_mem = RedisMemory()
# qdrant_mem = QdrantMemory()
    
# deps = AgentDeps(
#     gmail_auth=GmailAuth(),
#     r2_storage=r2,
#     redis_mem=redis_mem,
#     qdrant_mem=qdrant_mem,
#     user_id=str(uuid4()),
#     session_id=str(uuid4())
# )

# async def run_personal_agent():

#     async with personal_agent.iter("check if i had received any mail from skylar henderson in last 1 week if received pleasy give me the summary what it says", deps=deps) as nodes:
#         async for node in nodes:
#             if isinstance(node,UserPromptNode):
#                 print(f"[Initialising] user prompt: {node.user_prompt}")
#             elif isinstance(node,ModelRequestNode):
#                 print(f"[Calling Model] {node.request.parts}")
#             elif isinstance(node,CallToolsNode):
#                 for part in node.model_response.parts:
#                     if isinstance(part,ToolCallPart):
#                         print(f"[Calling Tool] {part.tool_name} with args: {part.args}")
#                 # print(f"[Calling Tool] {node.model_response.model_name} with args: {node.model_response.parts}")
#             elif isinstance(node,End):
#                 print(f"[Output] result : {node.data.output}")
                



# asyncio.run(run_personal_agent())



