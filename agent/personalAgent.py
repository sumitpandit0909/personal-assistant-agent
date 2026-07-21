import sys
import asyncio
from dataclasses import dataclass
from pydantic_graph import End
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')
from pydantic_ai import Agent,UserPromptNode,ModelRequestNode,CallToolsNode,ToolCallPart
from config.settings import setting ,model
from subagent.communication import GmailAuth,communication_agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from subagent.document import document_subagent
from subagent.upload import document_upload_agent, R2Storage
from subagent.planner import planner_subagent
from subagent.research import research_subagent
from pydantic_ai.capabilities import WebSearch
from pydantic_ai_harness.subagents import SubAgents,SubAgent
import logfire

logfire.configure()
logfire.instrument_system_metrics()
logfire.instrument_pydantic_ai()

@dataclass
class AgentDeps:
    gmail_auth: GmailAuth
    r2_storage: R2Storage



personal_agent=Agent(
    model,
    instructions="""
    You are a helpful personal assistant.
    Assist the user in their day-to-day tasks by understanding their needs and responding in a helpful and organized manner.
    
    You have access to the following subagents:
    1. planner_subagent: Analyzes user prompts and returns a structured, step-by-step ExecutionPlan.
    2. research_subagent: Conducts web research to gather live data, facts, and structured content.
    3. document_subagent: Compiles research into formatted documents (PDF, DOCX, Marp PPT) and returns local file paths.
    4. document_upload_agent: Uploads local files to Cloudflare R2 storage and returns the public URL.
    5. communication_agent: Reads, drafts, and sends emails via Gmail.
    
    Workflow Guidelines:
    1. STEP 1 (Planning): For any multi-step task, FIRST delegate to `planner_subagent` to break down the request into an ExecutionPlan.
    2. STEP 2 (Execution): Sequentially execute each step in the generated plan by calling `delegate_task` for the assigned target subagent, passing outputs (data, file paths, URLs) from one step to the next.
    3. STEP 3 (Response): Once all steps in the plan are complete, present a clear final summary to the user.
    """,
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


@personal_agent.tool_plain
def get_realtime_and_date():
    """
    Get the current date and time.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
r2 = R2Storage(
    access_key=setting.CLOUDFLARE_ACCESS_KEY_ID,
    secret_key=setting.CLOUDFLARE_SECRET_ACCESS_KEY_ID,
    endpoint_url=setting.CLOUDFLARE_R2_ENDPOINT,
    bucket=setting.CLOUDFLARE_R2_BUCKET,
    public_url=setting.CLOUDFLARE_R2_PUBLIC_URL,
)

async def run_personal_agent():
    async with personal_agent.iter("check if i had received any mail from skylar henderson in last 1 week if received pleasy give me the summary what it says", deps=AgentDeps(GmailAuth(),r2)) as nodes:
        async for node in nodes:
            if isinstance(node,UserPromptNode):
                print(f"[Initialising] user prompt: {node.user_prompt}")
            elif isinstance(node,ModelRequestNode):
                print(f"[Calling Model] {node.request.parts}")
            elif isinstance(node,CallToolsNode):
                for part in node.model_response.parts:
                    if isinstance(part,ToolCallPart):
                        print(f"[Calling Tool] {part.tool_name} with args: {part.args}")
                # print(f"[Calling Tool] {node.model_response.model_name} with args: {node.model_response.parts}")
            elif isinstance(node,End):
                print(f"[Output] result : {node.data.output}")
                



asyncio.run(run_personal_agent())



