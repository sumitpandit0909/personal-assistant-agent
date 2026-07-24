from memory.database import update_task_status
from sqlalchemy import update
from memory.celery_app import celery_app
import os
from config.settings import setting
from markdown import markdown
from weasyprint import HTML
import subprocess
import base64
import asyncio
from pydantic import BaseModel
from typing import Optional
from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os.path
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
from config.settings import model

class ResearchOutput(BaseModel):
    content: str
    query: str
    filename: Optional[str] = None 
    to:Optional[str] =None
    subject:Optional[str] =None
    body:Optional[str] =None

class DocumentOutput(BaseModel):
    file_path:str
    research_data: dict

class UploadOutputData(BaseModel):
    url:str
    research_data:dict

@celery_app.task(bind=True,name="tasks.create_pdf_task")
def create_pdf_task(self,*args, **kwargs):
    # 1. Parse arguments dynamically
    if len(args) == 2:
        # Called directly from subagent tool: markdown_content (str), filename (str)
        markdown_content = args[0]
        filename = args[1]
        research_data = None
    elif len(args) == 1 and isinstance(args[0], dict):
        # Called in a Celery chain: research_data (dict)
        research_data = args[0]
        data = ResearchOutput.model_validate(research_data)
        markdown_content = data.content
        filename = data.filename or kwargs.get("filename")
    else:
        markdown_content = kwargs.get("markdown_content", "")
        filename = kwargs.get("filename")
        research_data = None
    update_task_status(self.request.id,status="processing",result="Creating pdf...")
    try:
        chosen_filename=data.filename or filename or "report.pdf"
        base_name, _ = os.path.splitext(chosen_filename)
        safe_filename = os.path.basename(base_name + ".pdf")
        abs_path = os.path.abspath(safe_filename)
        html_body = markdown(markdown_content,extensions=['tables', 'fenced_code'])
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
        HTML(string=full_html).write_pdf(abs_path)
        
        output = DocumentOutput(file_path=abs_path,research_data=research_data)
        update_task_status(self.request.id,status="completed",result="Pdf created successfully",link=abs_path)
        if research_data:
            output = DocumentOutput(file_path=abs_path, research_data=research_data)
            return output.model_dump()
        else:
            return abs_path
    except Exception as e:
        update_task_status(self.request.id,status="failed",result=str(e))
        raise e


@celery_app.task(name="tasks.create_docx_task",bind=True)
def create_docx_task(self,*args, **kwargs):
     # 1. Parse arguments dynamically
    if len(args) == 2:
        # Called directly from subagent tool: markdown_content (str), filename (str)
        markdown_content = args[0]
        filename = args[1]
        research_data = None
    elif len(args) == 1 and isinstance(args[0], dict):
        # Called in a Celery chain: research_data (dict)
        research_data = args[0]
        data = ResearchOutput.model_validate(research_data)
        markdown_content = data.content
        filename = data.filename or kwargs.get("filename")
    else:
        markdown_content = kwargs.get("markdown_content", "")
        filename = kwargs.get("filename")
        research_data = None
    update_task_status(self.request.id,status="processing",result="creating docx...")
    try:
        chosen_filename =data.filename or filename or "report.docx"
        base_name, _ = os.path.splitext(chosen_filename)
        safe_filename = os.path.basename(base_name + ".docx")
        abs_path = os.path.abspath(safe_filename)
        tmp_file = "tmp.md"
        with open(tmp_file,"w",encoding="utf-8") as file:
            file.write(markdown_content)
        output_path = abs_path
        cmd =[
            "pandoc",
            tmp_file,
            "-o",
            output_path,
            "--reference-doc=custom_reference.docx"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=False)

        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        output = DocumentOutput(file_path=output_path,research_data=research_data)
        if result.returncode == 0:
            update_task_status(self.request.id,status="completed",result="successfully converted to docx",link=abs_path)
            if research_data:
                output = DocumentOutput(file_path=abs_path, research_data=research_data)
                return output.model_dump()
            else:
                return abs_path
        else:
            update_task_status(self.request.id,status="failed",result="error converting to docx")
            raise Exception(result.stderr)
            
    except Exception as e:
        if os.path.exists(abs_path):
            os.remove(abs_path)
        update_task_status(self.request.id,status="failed",result=str(e))
        raise e


@celery_app.task(name="tasks.render_slides_task",bind=True)
def render_slide_task(self,*args, **kwargs):
     # 1. Parse arguments dynamically
    if len(args) == 2:
        # Called directly from subagent tool: markdown_content (str), filename (str)
        markdown_content = args[0]
        filename = args[1]
        research_data = None
    elif len(args) == 1 and isinstance(args[0], dict):
        # Called in a Celery chain: research_data (dict)
        research_data = args[0]
        data = ResearchOutput.model_validate(research_data)
        markdown_content = data.content
        filename = data.filename or kwargs.get("filename")
    else:
        markdown_content = kwargs.get("markdown_content", "")
        filename = kwargs.get("filename")
        research_data = None
    temp_md_path = "temp_presentation.md"
    update_task_status(self.request.id, status="processing",result="creting slides...")

    try:
        chosen_filename= data.filename or filename or "presentation.html"
        base_name, _ = os.path.splitext(chosen_filename)
        safe_filename = os.path.basename(base_name + ".html")
        abs_path = os.path.abspath(safe_filename)
        with open(temp_md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        cmd = ["npx", "-y", "@marp-team/marp-cli@latest", temp_md_path, "-o", abs_path]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=False)

        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)

        if result.returncode == 0:
            output = DocumentOutput(file_path=abs_path,research_data=research_data)
            update_task_status(self.request.id, status="completed",result="presentation created successfully",link=abs_path)
            if research_data:
                output = DocumentOutput(file_path=abs_path, research_data=research_data)
                return output.model_dump()
            else:
                return abs_path
        else:
            update_task_status(self.request.id, status="failed",result="error creating presentation")
            raise Exception(result.stderr)
            
    except Exception as e:
        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)
        update_task_status(self.request.id, status="failed",result=str(e))
        raise e

@celery_app.task(name="tasks.upload_r2_task", bind=True, max_retries=3, default_retry_delay=10)
def upload_r2_task(self, *args, **kwargs):
    # 1. Parse arguments dynamically
    if len(args) == 1 and isinstance(args[0], str):
        # Called directly from subagent tool: file_path (str)
        file_path = args[0]
        research_data = None
    elif len(args) == 1 and isinstance(args[0], dict):
        # Called in a Celery chain: document_data (dict)
        document_data = args[0]
        data = DocumentOutput.model_validate(document_data)
        file_path = data.file_path
        research_data = data.research_data
    else:
        file_path = kwargs.get("file_path") or kwargs.get("document_data", {}).get("file_path")
        research_data = kwargs.get("document_data", {}).get("research_data")
    
    update_task_status(self.request.id, status="processing", result="Uploading file to R2...")
    
    try:
        from subagent.upload import R2Storage
        # 2. Instantiate R2Storage locally inside the worker using settings
        storage = R2Storage(
            access_key=setting.CLOUDFLARE_ACCESS_KEY_ID,
            secret_key=setting.CLOUDFLARE_SECRET_ACCESS_KEY_ID,
            endpoint_url=setting.CLOUDFLARE_R2_ENDPOINT,
            bucket=setting.CLOUDFLARE_R2_BUCKET,
            public_url=setting.CLOUDFLARE_R2_PUBLIC_URL
        )
        
        # 3. Perform the upload
        public_url = storage.upload(file_path)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"DEBUG: Cleaned up local file: {file_path}")
        except Exception as e:
            print(f"[Cleanup Warning] Failed to delete local file {file_path}: {e}")
        # 4. Save success status and public URL link
        update_task_status(self.request.id, status="completed", result="Upload successful", link=public_url)
        if research_data:
            output = UploadOutputData(url=public_url, research_data=research_data)
            return output.model_dump()
        else:
            return public_url
        
    except Exception as exc:
        # 5. Handle retry or log failure
        update_task_status(self.request.id, status="failed", result=str(exc))
        raise self.retry(exc=exc)



@celery_app.task(name="tasks.send_email_task",bind=True)
def send_email_task(self,*args, **kwargs):
    # 1. Parse arguments dynamically
    if len(args) == 3:
        # Called directly: to, subject, body
        to = args[0]
        subject = args[1]
        body = args[2]
    elif len(args) == 1 and isinstance(args[0], dict):
        # Called in a chain: upload_data
        upload_data = args[0]
        upload = UploadOutputData.model_validate(upload_data)
        research = ResearchOutput.model_validate(upload.research_data)
        url = upload.url or None
        body = research.body or ""
        if url:
            body += f"\n\n### Attached Report\n{url}"
        to = kwargs.get("to") or research.to
        subject = kwargs.get("subject") or research.subject
    else:
        # Fallback to kwargs
        to = kwargs.get("to")
        subject = kwargs.get("subject")
        body = kwargs.get("body", "")

    print(f"DEBUG: send_email_task called with body={body} (type={type(body)}), to={to} (type={type(to)}), subject={subject} (type={type(subject)})")

    update_task_status(self.request.id, status="processing", result="sending email...")
    from subagent.communication import get_gmail_credentials
    creds = False
    if not creds:
        creds = get_gmail_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        message = EmailMessage()
        message.set_content(body)
        if to:
            if isinstance(to, str):
                message["To"] = to
            else:
                message["To"] = ", ".join(to)

        message["Subject"] = subject
        
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}
        
        send_message =(
            service.users()
            .messages()
            .send(userId="me",body =create_message)
            .execute()
        )
        update_task_status(self.request.id, status="completed", result=f"Email sent successfully.MessageID: {send_message['id']}")
    except HttpError as err:
        update_task_status(self.request.id, status="failed", result=f"An error occured while sending email : {err}")


@celery_app.task(name="tasks.draft_email_task",bind=True)
def draft_email_task(self,*args, **kwargs):
    # 1. Parse arguments dynamically
    if len(args) == 3:
        # Called directly: to, subject, body
        to = args[0]
        subject = args[1]
        body = args[2]
    elif len(args) == 1 and isinstance(args[0], dict):
        # Called in a chain: upload_data
        upload_data = args[0]
        upload = UploadOutputData.model_validate(upload_data)
        research = ResearchOutput.model_validate(upload.research_data)
        url = upload.url or None
        body = research.body or ""
        if url:
            body += f"\n\n### Attached Report\n{url}"
        to = kwargs.get("to") or research.to
        subject = kwargs.get("subject") or research.subject
    else:
        # Fallback to kwargs
        to = kwargs.get("to")
        subject = kwargs.get("subject")
        body = kwargs.get("body", "")

    print(f"DEBUG: draft_email_task called with body={body} (type={type(body)}), to={to} (type={type(to)}), subject={subject} (type={type(subject)})")
    update_task_status(self.request.id, status="processing", result="drafting email...")
    from subagent.communication import get_gmail_credentials
    creds = False
    if not creds:
        creds = get_gmail_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        message = EmailMessage()
        message.set_content(body)
        if to:
            if isinstance(to, str):
                message["To"] = to
            else:
                message["To"] = ", ".join(to)

        message["Subject"] = subject
        
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}

        draft = (
            service.users()
            .drafts()
            .create(userId="me",body={"message":create_message})
            .execute()
        )
        update_task_status(self.request.id, status="completed", result=f"Draft created successfully with message ID: {draft['id']}")
    except HttpError as err:
        update_task_status(self.request.id, status="failed", result=f"An error occured while creating draft : {err}")

@celery_app.task(bind=True, name="tasks.research_task")
def research_task(self, query: str) -> dict:
    update_task_status(self.request.id, status="processing", result="Researching topic on the web...")
    try:
        from subagent.research import research_subagent

        # Run the async agent synchronously inside the worker thread
        async def run_research():
            result = await research_subagent.run(query)
            return ResearchOutput(
                content=result.output.content,
                query=query,
                filename=result.output.filename,
                to=result.output.to or None,
                subject=result.output.subject or None,
                body=result.output.body or None
            )

        output = asyncio.run(run_research())
        
        update_task_status(self.request.id, status="completed", result="Research completed successfully.")
        return output.model_dump()
    except Exception as e:
        update_task_status(self.request.id, status="failed", result=str(e))
        raise e
