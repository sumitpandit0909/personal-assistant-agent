from distro import name
from anthropic.types.beta.deployment_create_params import Agent
import os
import subprocess
from markdown import markdown
from weasyprint import HTML
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai import FunctionToolset, ModelSettings,Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from dataclasses import dataclass
from pydantic import BaseModel,Field
from config.settings import setting,model

class RenderSlideRequest(BaseModel):
    markdown_content:str=Field(...,description="The full Marp-compliant markdonw string represeting all slides, starting with the frontmatter header (e.g '---marp:true \\n theme:gaia \\n---') ")
    filename:str = Field("presentation.html",description="the output html file name, use related to content .Use alphanumeric characters and hyphens only, ending in '.html'.")

class CreateDocxRequest(BaseModel):
    markdown_content:str=Field(...,description="full markdown content of the document")
    filename:str=Field(...,description="output file name,ending with .docx")

class CreatePdfRequest(BaseModel):
    markdown_content:str=Field(...,description="full markdown content of the pdf")
    filename:str=Field(...,description="output file name,ending with .pdf")

class SubagentResponse(BaseModel):
    success:bool= Field(...,description="whether the document generation was success or failed")
    message:str= Field(...,description="message document created succesfful with doctype or if failed reason of failing")
    file_path:str=Field(...,description="absoulute file path of the created document")

productivity_toolset = FunctionToolset()

@productivity_toolset.tool_plain()
async def create_pdf(request:CreatePdfRequest):
    try:
        safe_filename = os.path.basename(request.filename)
        abs_path = os.path.abspath(safe_filename)
        html_body = markdown(request.markdown_content,extensions=['tables', 'fenced_code'])
        full_html=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <link rel="stylesheet" href="print_styles.css">
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        HTML(string=full_html).write_pdf(request.filename)
        return f"Successfully converted markdown to pdf: {abs_path}"
    except Exception as e:
        return f"An error occurred: {str(e)}"
    
@productivity_toolset.tool_plain()
async def create_docx(request:CreateDocxRequest):
    try:
        safe_filename = os.path.basename(request.filename)
        abs_path = os.path.abspath(safe_filename)
        tmp_file = "tmp.md"
        with open(tmp_file,"w",encoding="utf-8") as file:
            file.write(request.markdown_content)
        output_path = request.filename
        cmd =[
            "pandoc",
            tmp_file,
            "-o",
            output_path,
            "--reference-doc=custom_reference.docx"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        if os.path.exists(tmp_file):
            os.remove(tmp_file)
            
        if result.returncode == 0:
            return f"Successfully converted markdown to docx: {abs_path}"
        else:
            return f"Error converting markdown to docx:\n{result.stderr}"
            
    except Exception as e:
        if os.path.exists(request.filename):
            os.remove(request.filename)
        return f"An error occurred: {str(e)}"

@productivity_toolset.tool_plain(retries=2)
async def render_slides(request: RenderSlideRequest) -> str:
    temp_md_path = "temp_presentation.md"

    try:
        safe_filename = os.path.basename(request.filename)
        abs_path = os.path.abspath(safe_filename)
        with open(temp_md_path, "w", encoding="utf-8") as f:
            f.write(request.markdown_content)

        cmd = ["npx", "-y", "@marp-team/marp-cli@latest", temp_md_path, "-o", request.filename]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)

        if result.returncode == 0:
            return f"Successfully converted markdown to HTML: {abs_path}"
        else:
            return f"Error converting markdown to HTML:\n{result.stderr}"
            
    except Exception as e:
        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)
        return f"An error occurred: {str(e)}"

document_subagent = Agent(
    model,
    name="document_subagent",
    description="subagent for creating documents in pdf, docx and ppt format",
    output_type=SubagentResponse,
    instructions="""
        You are a productivity assistant capable of creating presentations, PDF reports, and Word (DOCX) documents.
        
        Guidelines:
        1. **Presentations (Slides)**:
            - When asked for slides, a presentation, or a pitch deck, first use web search to find relevant information or image links.
            - Write the slides in clean Marp Markdown format, incorporating the images.
            - Start with a frontmatter header (e.g. specifying 'marp: true', a theme like 'gaia' or 'uncover', pagination, etc.).
            - Separate slides using triple dashes ('---').
            - Call the 'render_slides' tool to build the presentation.
            
            2. **PDF Documents & Reports**:
            - When asked to create a PDF document, report, or printed page, write the content in standard clean Markdown (supporting headings, lists, bold text, and tables).
            - Do not use Marp headers or slide separators. Keep it formatted as a continuous document.
            - Call the 'create_pdf' tool to compile it. It will automatically apply professional print styles.
            
            3. **Word Documents (DOCX)**:
            - When asked to write a Word document, a report in Word, or a .docx file, write the content in standard clean Markdown.
            - Call the 'create_docx' tool to compile it using pandoc.
            
            4. After creating the file, return the correct absolute file path in your SubagentResponse output. 
            Always select the correct tool for the specific output format requested by the user.
        """,
        toolsets=[productivity_toolset]
)