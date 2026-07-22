from typing import List, Literal, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from config.settings import model

class CeleryTaskCall(BaseModel):
    task_name: Literal[
        "tasks.create_pdf_task",
        "tasks.create_docx_task",
        "tasks.render_slides_task",
        "tasks.upload_r2_task",
        "tasks.send_email_task",
        "tasks.draft_email_task"
    ] = Field(..., description="The exact Celery task name to queue.")
    kwargs: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Constant keyword arguments. Do NOT supply arguments passed forward from previous steps."
    )

class PlannedStep(BaseModel):
    step_number: int = Field(..., description="1-based index of the step")
    target_subagent: Literal[
        "research_subagent", 
        "document_subagent", 
        "document_upload_agent", 
        "communication_agent"
    ] = Field(..., description="Subagent assigned to perform this step")
    task_description: str = Field(..., description="Instructions for this subagent")

class DynamicWorkflowPlan(BaseModel):
    execution_mode: Literal["sync", "async_chain"] = Field(
        ...,
        description="Use 'sync' for interactive queries (reading/checking email, quick answers). Use 'async_chain' for heavy processing (report compilation, file conversion, email sends)."
    )
    task_chain: List[CeleryTaskCall] = Field(
        default_factory=list,
        description="Ordered list of Celery tasks to chain together in the background (Active if execution_mode is 'async_chain')."
    )
    sync_steps: List[PlannedStep] = Field(
        default_factory=list,
        description="Ordered list of subagent steps to execute synchronously right now (Active if execution_mode is 'sync')."
    )

planner_subagent = Agent[None, DynamicWorkflowPlan](
    model,
    name="planner_subagent",
    description="Analyzes user requests and generates a structured, dynamic execution plan (sync or async_chain>).",
    output_type=DynamicWorkflowPlan,
    instructions="""
    You are an expert AI Planner and Workflow Orchestrator.
    Your goal is to analyze user prompts and generate a structured DynamicWorkflowPlan.
    
    1. **Decide the Execution Mode**:
       - Choose `"sync"` for fast, interactive queries (e.g. searching/reading emails, quick Q&A).
       - Choose `"async_chain"` for heavy, multi-step tasks (e.g. generating reports, uploading files, sending emails).
       
    2. **If `"sync"` is selected**:
       - Populate `sync_steps` with sequential subagent assignments to complete the request step-by-step.
       - Keep `task_chain` empty.
       
    3. **If `"async_chain"` is selected**:
       - Build an ordered list of tasks in `task_chain` using these available tasks:
         * `tasks.create_pdf_task`: Renders a professional PDF from markdown.
         * `tasks.create_docx_task`: Compiles a Word (.docx) document from markdown.
         * `tasks.render_slides_task`: Creates Marp presentation slides.
         * `tasks.upload_r2_task`: Uploads a file and returns its public URL.
         * `tasks.send_email_task`: Sends an email to recipients.
         * `tasks.draft_email_task`: Saves a draft email.
       - **Important Chaining Rule**: The output of task N is automatically passed as the first positional argument of task N+1.
         * Do NOT include parameters in `kwargs` that will be automatically passed forward from the previous task (such as the `file_path` for R2 upload or the `url` for sending emails). Only include constant arguments (like `recipient_list`, `subject`, `filename`, `markdown_content`).
    """
)
