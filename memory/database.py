from datetime import datetime
from sqlmodel import SQLModel, Field,Relationship,create_engine,Session,select
from uuid import UUID, uuid4
from typing import List,Optional
from config.settings import setting


class User(SQLModel,table=True):
    id: UUID =Field(default_factory=uuid4,primary_key=True)
    email:str =Field(unique=True,index=True)
    name:str
    telegram_id: Optional[str] = Field(default=None, unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # relationship 
    sessions : List["ChatSession"] =Relationship(back_populates="user")
    tasks: List["Task"] = Relationship(back_populates="user")

class ChatSession(SQLModel,table=True):
    id: UUID =Field(default_factory=uuid4,primary_key=True)
    user_id : UUID =Field(foreign_key="user.id")
    title: Optional[str]="New Chat Session"
    created_at:datetime = Field(default_factory=datetime.utcnow)
    #relationship
    user : Optional["User"]= Relationship(back_populates="sessions")
    messages :List["Message"] =Relationship(back_populates="session")


class Message(SQLModel,table=True):
    id:UUID=Field(default_factory=uuid4,primary_key=True)
    session_id:Optional[UUID]=Field(default=None,foreign_key="chatsession.id")
    role:str=Field(...,description="user,assistant,tool,or system")
    content:str =Field(...)
    created_at:datetime=Field(default_factory=datetime.utcnow)
    #relationship
    session:Optional["ChatSession"]= Relationship(back_populates="messages")


class DocumentRecord(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    filename: str = Field(...)
    file_path: str = Field(...)
    public_url: Optional[str] = None
    doc_type: str = Field(..., description="pdf, docx, html, ppt")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Task(SQLModel,table=True):
    id:UUID=Field(default_factory=uuid4,primary_key=True)
    user_id:UUID=Field(foreign_key="user.id")
    task:str
    status:str=Field(...,description="pending,completed,failed")
    result:str
    link:str|None=None
    created_at:datetime=Field(default_factory=datetime.utcnow)
    user:Optional["User"]=Relationship(back_populates="tasks")


engine = create_engine(setting.DATABASE_URL)



def init_db():
    SQLModel.metadata.create_all(engine)
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS "telegram_id" VARCHAR(255) UNIQUE;'))
        conn.commit()
def get_session():
    with Session(engine) as session:
        yield session


# helper function 


def get_or_create_user(email: str, name: str) -> User:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(email=email, name=name)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

def create_chat_session(user_id: UUID, title: str = "New Chat") -> ChatSession:
    with Session(engine) as session:
        db_session = ChatSession(user_id=user_id, title=title)
        session.add(db_session)
        session.commit()
        session.refresh(db_session)
        return db_session

def save_message(session_id: UUID, role: str, content: str):
    with Session(engine) as session:
        db_msg = Message(session_id=session_id, role=role, content=content)
        session.add(db_msg)
        session.commit()

def create_task_record(task_id: str, user_id: UUID, task_name: str) -> Task:
    with Session(engine) as session:
        db_task = Task(
            id=UUID(task_id), 
            user_id=user_id, 
            task=task_name, 
            status="pending", 
            result="Task queued."
        )
        session.add(db_task)
        session.commit()
        session.refresh(db_task)
        return db_task

def update_task_status(task_id: str, status: str, result: str, link: str = None):
    with Session(engine) as session:
        db_task = session.get(Task, UUID(task_id))
        if db_task:
            db_task.status = status
            db_task.result = result
            if link:
                db_task.link = link
            session.add(db_task)
            session.commit()

def save_document_record(user_id: UUID, filename: str, file_path: str, doc_type: str, public_url: str = None):
    with Session(engine) as session:
        record = DocumentRecord(
            user_id=user_id,
            filename=filename,
            file_path=file_path,
            doc_type=doc_type,
            public_url=public_url
        )
        session.add(record)
        session.commit()
