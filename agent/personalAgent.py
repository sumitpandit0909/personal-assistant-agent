import sys
import asyncio
from dataclasses import dataclass
from pydantic_graph import End

sys.stdout.reconfigure(encoding='utf-8')
from pydantic_ai import Agent,UserPromptNode,ModelRequestNode,CallToolsNode,ToolCallPart
from config.settings import setting 
from subagent.communication import GmailAuth,communication_agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from subagent.document import document_subagent
from subagent.upload import document_upload_agent, R2Storage
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

model = OpenRouterModel(
    "openrouter/free",
    provider=OpenRouterProvider(api_key=setting.OPENROUTER_API_KEY)
)

personal_agent=Agent(
    model,
    instructions="""
    You are a helpful personal assistant.
    Assist the user in their day-to-day tasks by understanding their needs and responding in a helpful and organized manner.
    
    You have access to the following subagents and tools:
    1. document_subagent: Creates documents (PDFs, presentations, Word files) and returns the local file path.
    2. document_upload_agent: Uploads local files to Cloudflare R2 cloud storage and returns the public URL.
    3. communication_agent: Reads, drafts, and sends emails via Gmail.
    4. duckduckgo_search: Searches the web for real-time information and links.
    
    Workflow Guidelines:
    CRITICAL: When the user asks to create/generate a document or report and send or email the link, you MUST execute all 3 subagents in sequence using `delegate_task`:
      1. STEP 1: Call `delegate_task` with `agent_name="document_subagent"` to generate the document file and get its local file_path.
      2. STEP 2: Call `delegate_task` with `agent_name="document_upload_agent"` providing the local file_path from Step 1 to upload it to R2 and get the public URL.
      3. STEP 3: Call `delegate_task` with `agent_name="communication_agent"` providing the recipient's email address and the public R2 URL from Step 2 to send the email.
    
    You MUST execute STEP 1, STEP 2, and STEP 3 in sequence. Do NOT stop after STEP 1!
    - For web research or recommendations, use 'duckduckgo_search'.
    """,
    capabilities=[SubAgents(agents=[SubAgent(communication_agent),SubAgent(document_subagent),SubAgent(document_upload_agent)]),WebSearch(local='duckduckgo')]
)

r2 = R2Storage(
    access_key=setting.CLOUDFLARE_ACCESS_KEY_ID,
    secret_key=setting.CLOUDFLARE_SECRET_ACCESS_KEY_ID,
    endpoint_url=setting.CLOUDFLARE_R2_ENDPOINT,
    bucket=setting.CLOUDFLARE_R2_BUCKET,
    public_url=setting.CLOUDFLARE_R2_PUBLIC_URL,
)

async def run_personal_agent():
    async with personal_agent.iter("create a report on crypto market and send th elink to my mail its.sumitpandith@gmail.com", deps=AgentDeps(GmailAuth(),r2)) as nodes:
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



