# subagent/planner.py
from typing import List, Literal
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from config.settings import model

class PlannedStep(BaseModel):
    step_number: int = Field(..., description="1-based index of the step")
    target_subagent: Literal[
        "research_subagent", 
        "document_subagent", 
        "document_upload_agent", 
        "communication_agent"
    ] = Field(..., description="Subagent assigned to perform this step")
    task_description: str = Field(..., description="Self-contained instructions for the target subagent")

class ExecutionPlan(BaseModel):
    goal: str = Field(..., description="High-level goal summary of the user prompt")
    reasoning: str = Field(..., description="Rationale behind this step-by-step breakdown")
    steps: List[PlannedStep] = Field(..., description="Ordered list of steps to execute")



planner_subagent = Agent[None, ExecutionPlan](
    model,
    name="planner_subagent",
    description="Analyzes complex user requests and generates a structured, step-by-step execution plan",
    output_type=ExecutionPlan,
    instructions="""
    You are an expert AI Planner.
    Analyze user prompts and decompose them into an ordered, step-by-step ExecutionPlan.
    
    Subagents available for target assignment:
    1. research_subagent: Gathers live web data, facts, and structured content.
    2. document_subagent: Generates PDF, DOCX, or Marp PPT files from text/markdown.
    3. document_upload_agent: Uploads local files to Cloudflare R2 cloud storage.
    4. communication_agent: Sends, drafts, or reads emails via Gmail.
    
    Rules:
    - Ensure each task_description is self-contained and clear.
    - Order steps logically (e.g. Research -> Document Generation -> Upload -> Email>).
    """
)
