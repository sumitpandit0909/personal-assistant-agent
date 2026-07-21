from pydantic_ai import ModelSettings
from pydantic_ai.capabilities import AbstractCapability
from typing import List,Any
from pydantic import BaseModel,Field
from pydantic_ai import FunctionToolset
from dataclasses import dataclass
from pydantic_ai import RunContext,Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from config.settings import setting
import base64
from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


# dependency
@dataclass
class GmailAuth:
    credentials: Any =None

# request schema for send email
class SendEmail(BaseModel):
    to:List[str]
    subject:str
    body:str
 #request schema for read email
class ReadEmail(BaseModel):
    query:str | None
    subject:str | None
    email_id:str | None

class SubagentResponse(BaseModel):
    success: bool = Field(..., description="Whether the email operation succeeded")
    message:str = Field(..., description="Detailed summary or result of the operation")

# scopes needed for gmail interaction permissions
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose"
]

# fuction to get the gmail credentials -token.json
def get_gmail_credentials():
    creds = None
    
    # Check if we already have a saved token
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
    # If we don't have valid credentials, do the local login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            # This opens a browser tab to log in
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for subsequent runs
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())
            
    return creds




# email toolset
email_tools = FunctionToolset[Any]()

# send email tool
@email_tools.tool
async def send_email(ctx:RunContext[Any],request:SendEmail):
    
    creds = ctx.deps.gmail_auth.credentials
    if not creds:
        creds = get_gmail_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        message = EmailMessage()
        message.set_content(request.body)
        message["To"] = ", ".join(request.to)
        message["Subject"] = request.subject
        
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}
        
        send_message =(
            service.users()
            .messages()
            .send(userId="me",body =create_message)
            .execute()
        )
        return f"Email sent successfully. MessageID: {send_message['id']}"
    except HttpError as err:
        return f"An error occured while sending email : {err}"

#  draft email tool
@email_tools.tool
async def draft_email(ctx:RunContext[Any],request:SendEmail):
    creds = ctx.deps.gmail_auth.credentials
    if not creds:
        creds = get_gmail_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        message = EmailMessage()
        message.set_content(request.body)
        message["To"] = ", ".join(request.to)
        message["Subject"] = request.subject
        
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}

        draft = (
            service.users()
            .drafts()
            .create(userId="me",body={"message":create_message})
            .execute()
        )
        return f"Draft created successfully with message ID: {draft['id']}"
    except HttpError as err:
        return f"An error occured while creating draft : {err}"
        
# read email tool 
@email_tools.tool
async def read_email(ctx:RunContext[Any],request:ReadEmail):
    creds = ctx.deps.gmail_auth.credentials
    if not creds:
        creds = get_gmail_credentials()
    try:
        service = build("gmail","v1",credentials=creds)

        query =""
        if request.query:
            query =f"in:anywhere {request.query}"
        if request.subject:
            query += f"subject:{request.subject}"
        if request.email_id:
            query += f"id:{request.email_id}"

        result = service.users().messages().list(userId="me",q=query).execute()
        messages = result.get("messages",[])

        if not messages:
            return "No messages found matching your query."

        response_messages = []
        for msg_info in messages[:10]:
            msg = service.users().messages().get(userId="me",id=msg_info['id']).execute()
            payload = msg['payload']
            headers = payload['headers']
            
            for header in headers:
                if header['name'] == 'From':
                    from_header = header['value']
                elif header['name'] == 'Subject':
                    subject_header = header['value']
            
            snippet = msg['snippet']
            response_messages.append({
                "from": from_header,
                "subject": subject_header,
                "snippet": snippet,
                "id": msg_info['id']
            })
            
        return response_messages
    except HttpError as err:
        return f"An error occured while reading emails: {err}"

model = OpenRouterModel(
    "openrouter/free",
    provider=OpenRouterProvider(api_key=setting.OPENROUTER_API_KEY)
)

communication_agent = Agent[GmailAuth,SubagentResponse](
    model,
    name="communication_agent",
    description="Communication agent for sending drafting and reading emails.",
    deps_type=GmailAuth,
    output_type=SubagentResponse,
    toolsets=[email_tools],
    instructions="""
        You are a helpful assistant that can help user with their email communication.
        use the correct tool for correct task
        """
)
 