from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from config.settings import setting,model
from pydantic_ai.capabilities import WebSearch
from typing import List,Optional
class SubagentResponse(BaseModel):
    success: bool = Field(
        ..., 
        description="Whether the research request was completed successfully."
    )
    message: str = Field(
        ..., 
        description="Brief summary message of the research outcome."
    )
    summary: str = Field(
        ..., 
        description="High-level executive summary of the research topic."
    )
    content: str = Field(
        ..., 
        description="Detailed, structured Markdown research content containing all facts, data, and sections ready for document generation."
    )
    filename:Optional[str] =Field(description="name of the file")
    to:Optional[str]= Field(description="email of the reciepient")
    subject:Optional[str]= Field(description="subject of the email")
    body:Optional[str]= Field(description="body of the email")
    sources: List[str] = Field(
        default_factory=list, 
        description="List of web URLs and references gathered during search."
    )

# subagent/research.py
research_subagent = Agent(
    model,
    name="research_subagent",
    description="Subagent for conducting comprehensive web research and gathering structured real-time data",
    output_type=SubagentResponse,
    instructions="""
    You are an expert Lead Research Analyst.
    Your goal is to conduct deep, thorough web research and synthesize your findings into a rich, multi-page Markdown report.
    
    Research & Output Guidelines:
    1. **Search Thoroughly**: Use `duckduckgo_search` to query multiple angles of the topic (e.g. current stats, market trends, key players, news, analysis).
    2. **Structured Content (`content` field)**: Write exhaustive, professional Markdown containing:
       - **# Title & Executive Summary**: Concise overview.
       - **## Key Findings & Data**: Detailed breakdown with Markdown tables, bullet points, and exact figures.
       - **## Market Trends & Industry Impact**: In-depth analysis of driving factors.
       - **## Recent Developments & News**: Timelines, announcements, or regulatory updates.
       - **## Strategic Outlook & Conclusion**: Future projections and key takeaways.
    3. **Completeness**: Do NOT truncate or write brief summaries. Provide rich, extensive content so the output naturally fills a multi-page report.
    4. **Sources (`sources` field)**: Include all retrieved web URLs.
    """,
    capabilities=[WebSearch(local='duckduckgo')]
)
