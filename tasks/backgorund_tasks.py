from qdrant_client.grpc import TurboQuantBitSize
from markdown_it.rules_inline import link
from memory.database import update_task_status
from sqlalchemy import update
from memory.celery_app import celery_app
import os
from markdown import markdown
from weasyprint import HTML
import subprocess
from subagent.communication import get_gmail_credentials
import base64
from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os.path
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
from config.settings import model

@celery_app.task(bind=True,name="tasks.create_pdf_task")
def create_pdf_task(self,markdown_content: str, filename: str):
        update_task_status(self.request.id,status="processing")
        try:
            safe_filename = os.path.basename(filename)
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
            HTML(string=full_html).write_pdf(filename)
            update_task_status(self.request.id,status="completed",result="Pdf created successfully",link=abs_path)
        except Exception as e:
            update_task_status(self.request.id,status="failed",result=str(e))
            raise e


@celery_app.task(name="create_docx_task",bind=True)
def create_docx_task(self,markdown_content,filename):
    update_task_status(self.request.id,status="processing")
    try:
        safe_filename = os.path.basename(filename)
        abs_path = os.path.abspath(safe_filename)
        tmp_file = "tmp.md"
        with open(tmp_file,"w",encoding="utf-8") as file:
            file.write(markdown_content)
        output_path = filename
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
            update_task_status(self.request.id,status="completed",result="successfully converted to docx",link=abs_path)
        else:
            update_task_status(self.request.id,status="failed",result="error converting to docx")
            raise Exception(result.stderr)
            
    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        update_task_status(self.request.id,status="failed",result=str(e))
        raise e


@celery_app.task(name="render_slides_task",bind=True)
def render_slide_task(self,markdown_content,filename):
    temp_md_path = "temp_presentation.md"
    update_task_status(self.request.id, status="processing",result="creting slides...")

    try:
        safe_filename = os.path.basename(filename)
        abs_path = os.path.abspath(safe_filename)
        with open(temp_md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        cmd = ["npx", "-y", "@marp-team/marp-cli@latest", temp_md_path, "-o", filename]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)

        if result.returncode == 0:
            update_task_status(self.request.id, status="completed",result="presentation created successfully",link=abs_path)
        else:
            update_task_status(self.request.id, status="failed",result="error creating presentation")
            raise Exception(result.stderr)
            
    except Exception as e:
        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)
        update_task_status(self.request.id, status="failed",result=str(e))
        raise e


@celery_app.task(name="upload_r2_task",bind=True,max_retries=2)
def upload_r2_task(ctx,request):
    storage = ctx.deps.r2_storage

    return storage.upload(request.file_path)


@celery_app.task(name="send_email_task",bind=True)
def send_email_task(self,to,subject,body):
    update_task_status(self.request.id, status="processing", result="sending email...")
    creds = False
    if not creds:
        creds = get_gmail_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        message = EmailMessage()
        message.set_content(body)
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


@celery_app.task(name="draf_email_task",bind=True)
def draft_email_task(self,to,subject,body):
    update_task_status(self.request.id, status="processing", result="drafting email...")
    creds = False
    if not creds:
        creds = get_gmail_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        message = EmailMessage()
        message.set_content(body)
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

