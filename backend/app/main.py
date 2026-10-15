"""Synthetic-data-only AI Workflow Assistant starter API.

No email integrations, customer accounts, external writes, or LLM calls are enabled.
"""
import os
import hmac
import logging
import time
from secrets import token_hex
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from app.ai_processor import extract, mock_extract, ProcessorError
from app.agents import run_agents, AGENTS
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, select, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./workflow_dev.db')
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Message(Base):
    __tablename__ = 'inbox_messages'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), unique=True)
    sender: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default='new')
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    urgency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey('inbox_messages.id'), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default='pending_review')

class Approval(Base):
    __tablename__ = 'approvals'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'), unique=True)
    draft: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(32), default='pending')
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    reference_id: Mapped[str] = mapped_column(String(36))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class WorkflowRun(Base):
    __tablename__ = 'workflow_execution_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey('inbox_messages.id'), unique=True)
    status: Mapped[str] = mapped_column(String(32), default='completed')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class WorkflowStep(Base):
    __tablename__ = 'workflow_execution_steps'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('workflow_execution_runs.id'))
    node_id: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(default=0)

WORKFLOW_NODES = [
    {'id':'trigger','name':'New sample message','kind':'trigger','description':'Select a synthetic inbox message'},
    {'id':'dedupe','name':'Duplicate guard','kind':'condition','description':'Prevent duplicate task creation'},
    {'id':'intake_agent','name':'Intake agent','kind':'agent','description':'Validate fictional input'},
    {'id':'classification_agent','name':'Classification agent','kind':'agent','description':'Extract category and urgency'},
    {'id':'planning_agent','name':'Task planning agent','kind':'agent','description':'Propose task without side effects'},
    {'id':'quality_agent','name':'Quality review agent','kind':'agent','description':'Check output and flag manual review'},
    {'id':'task','name':'Create task','kind':'action','description':'Commit approved task proposal'},
    {'id':'approval','name':'Human approval','kind':'review','description':'Queue response draft for review'},
]

def step(db: Session, run_id: str, node_id: str, detail: str, order: int):
    db.add(WorkflowStep(id=str(uuid4()),run_id=run_id,node_id=node_id,status='completed',detail=detail,order_index=order))

class MessageIn(BaseModel):
    sender: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    source_id: Optional[str] = None

class BatchIn(BaseModel):
    messages: list[MessageIn] = Field(min_length=1, max_length=50)

class DecisionIn(BaseModel):
    decision: str
    draft: Optional[str] = None

class TaskUpdate(BaseModel):
    status: str

app = FastAPI(title='AI Workflow Assistant API', version='1.1.0')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('FRONTEND_ORIGINS', 'http://localhost:3000').split(','), allow_credentials=False, allow_methods=['GET','POST','PATCH'], allow_headers=['Content-Type'])

logger = logging.getLogger('workflow_assistant')
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))

@app.middleware('http')
async def authorization_and_metrics(request: Request, call_next):
    started = time.monotonic()
    request_id = token_hex(8)
    # Health is unauthenticated and contains no sensitive data.
    if request.url.path.startswith('/api/') and request.url.path != '/api/health':
        expected = os.getenv('BACKEND_API_KEY', '')
        supplied = request.headers.get('x-api-key', '')
        if not expected or not hmac.compare_digest(supplied, expected):
            response = JSONResponse({'detail': 'Unauthorized'}, status_code=401)
            response.headers['X-Request-ID'] = request_id
            return response
    try:
        response = await call_next(request)
    except Exception:
        logger.exception('request_failed request_id=%s path=%s', request_id, request.url.path)
        raise
    response.headers['X-Request-ID'] = request_id
    response.headers['Cache-Control'] = 'no-store'
    logger.info('request_id=%s method=%s path=%s status=%d duration_ms=%d',
                request_id, request.method, request.url.path, response.status_code,
                int((time.monotonic() - started) * 1000))
    return response


def get_db():
    with SessionLocal() as db:
        yield db

def audit(db: Session, event: str, ref: str, note: str):
    db.add(Audit(id=str(uuid4()), event_type=event, reference_id=ref, note=note))

def message_json(m: Message):
    return {'id': m.id, 'source_id': m.source_id, 'sender':m.sender,'subject':m.subject,'body':m.body,'status':m.status,'category':m.category,'urgency':m.urgency,'summary':m.summary,'created_at':m.created_at.isoformat()}

def task_json(t: Task):
    return {'id':t.id,'message_id':t.message_id,'title':t.title,'status':t.status}

def approval_json(a: Approval):
    return {'id':a.id,'task_id':a.task_id,'draft':a.draft,'decision':a.decision,'decided_at':a.decided_at.isoformat() if a.decided_at else None}

@app.get('/api/health')
def health():
    return {'ok':True, 'mode':'synthetic_only', 'version':'1.1.0', 'ai_provider':os.getenv('AI_PROVIDER','mock')}

@app.get('/api/ready')
def readiness():
    """Database check. Requires the same API key as protected endpoints."""
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
            revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one_or_none()
        if revision != '0001_initial':
            return JSONResponse({'ready': False, 'reason': 'migration_required'}, status_code=503)
        return {'ready': True, 'database': 'connected', 'schema_revision': revision}
    except Exception:
        logger.warning('readiness_failed', exc_info=False)
        return JSONResponse({'ready': False, 'reason': 'database_unavailable_or_unmigrated'}, status_code=503)

@app.get('/api/dashboard/summary')
def summary(db: Session=Depends(get_db)):
    statuses = dict(db.execute(select(Message.status,func.count()).group_by(Message.status)).all())
    return {'messages':db.scalar(select(func.count()).select_from(Message)) or 0,'processed':sum(statuses.get(k,0) for k in ['processed','approved','rejected']),'pending_approvals':db.scalar(select(func.count()).select_from(Approval).where(Approval.decision=='pending')) or 0,'tasks':db.scalar(select(func.count()).select_from(Task)) or 0}

@app.get('/api/inbox')
def inbox(db: Session=Depends(get_db)):
    return [message_json(m) for m in db.scalars(select(Message).order_by(Message.created_at.desc())).all()]

@app.get('/api/inbox/{message_id}')
def get_message(message_id:str,db:Session=Depends(get_db)):
    m=db.get(Message,message_id)
    if not m: raise HTTPException(404,'Message not found')
    return message_json(m)

@app.post('/api/inbox/sample', status_code=201)
def add_sample(payload:MessageIn,db:Session=Depends(get_db)):
    # Deliberately accepts only manually entered / synthetic test messages.
    source_id=payload.source_id or 'sample-'+str(uuid4())
    existing=db.scalar(select(Message).where(Message.source_id==source_id))
    if existing: return message_json(existing)
    m=Message(id=str(uuid4()),source_id=source_id,sender=payload.sender,subject=payload.subject,body=payload.body,status='new')
    db.add(m);audit(db,'message_created',m.id,'Synthetic sample message added');db.commit()
    return message_json(m)

def classify(text: str):
    result=mock_extract('',text)
    return result.category,result.urgency

@app.post('/api/inbox/{message_id}/process')
def process(message_id:str,db:Session=Depends(get_db)):
    m=db.get(Message,message_id)
    if not m: raise HTTPException(404,'Message not found')
    prior=db.scalar(select(Task).where(Task.message_id==m.id))
    if prior: return {'message':message_json(m),'task':task_json(prior),'duplicate_prevented':True}
    try:
        agent_result=run_agents(m.sender,m.subject,m.body,classifier=extract)
        result,provider=agent_result.extraction,agent_result.provider
    except ProcessorError as exc:
        raise HTTPException(502,str(exc)) from exc
    m.category,m.urgency=result.category,result.urgency
    m.summary=result.summary
    m.status='processed'
    task=Task(id=str(uuid4()),message_id=m.id,title=agent_result.task_title)
    db.add(task)
    db.add(Approval(id=str(uuid4()),task_id=task.id,draft=result.draft))
    run=WorkflowRun(id=str(uuid4()),message_id=m.id,status='awaiting_approval')
    db.add(run)
    for i,(node,detail) in enumerate([('trigger','Synthetic message selected'),('dedupe','No existing task'),*agent_result.trace,('task','Task created'),('approval','Draft queued for review')]):
        step(db,run.id,node,detail,i)
    audit(db,'message_processed',m.id,f'Processor={provider}, category={m.category}, urgency={m.urgency}, confidence={result.confidence:.2f}')
    db.commit()
    return {'message':message_json(m),'task':task_json(task),'duplicate_prevented':False}

@app.post('/api/inbox/sample-batch')
def add_sample_batch(payload:BatchIn,db:Session=Depends(get_db)):
    # Atomic batch import; synthetic fixtures only. No external integrations.
    seen=set()
    result=[]
    inserted=0
    for item in payload.messages:
        source_id=item.source_id or 'sample-'+str(uuid4())
        if source_id in seen:
            raise HTTPException(422, 'Duplicate source_id within batch')
        seen.add(source_id)
        existing=db.scalar(select(Message).where(Message.source_id==source_id))
        if existing:
            result.append(message_json(existing))
            continue
        m=Message(id=str(uuid4()),source_id=source_id,sender=item.sender,subject=item.subject,body=item.body,status='new')
        db.add(m)
        audit(db,'message_created',m.id,'Synthetic sample message added in batch')
        db.flush()
        result.append(message_json(m))
        inserted+=1
    db.commit()
    return {'inserted':inserted,'existing':len(result)-inserted,'messages':result}

@app.get('/api/analytics/categories')
def analytics_categories(db:Session=Depends(get_db)):
    rows=db.execute(select(Message.category,func.count()).where(Message.category.is_not(None)).group_by(Message.category)).all()
    return {'categories': [{'name':category,'count':count} for category,count in rows],
            'high_urgency':db.scalar(select(func.count()).select_from(Message).where(Message.urgency=='high')) or 0}

@app.get('/api/tasks')
def tasks(db:Session=Depends(get_db)):
    return [task_json(t) for t in db.scalars(select(Task).order_by(Task.title)).all()]

@app.patch('/api/tasks/{task_id}')
def update_task(task_id:str,payload:TaskUpdate,db:Session=Depends(get_db)):
    if payload.status not in ['pending_review','open','in_progress','done']: raise HTTPException(422,'Invalid status')
    t=db.get(Task,task_id)
    if not t: raise HTTPException(404,'Task not found')
    if payload.status in ('open','in_progress','done'):
        approval=db.scalar(select(Approval).where(Approval.task_id==t.id))
        if approval is not None and approval.decision != 'approved':
            raise HTTPException(409, 'Task requires an approved review before progressing')
    t.status=payload.status;audit(db,'task_updated',t.id,payload.status);db.commit()
    return task_json(t)

@app.get('/api/approvals')
def approvals(db:Session=Depends(get_db)):
    return [approval_json(a) for a in db.scalars(select(Approval)).all()]

@app.patch('/api/approvals/{approval_id}')
def decide(approval_id:str,payload:DecisionIn,db:Session=Depends(get_db)):
    if payload.decision not in ['approved','rejected']: raise HTTPException(422,'Use approved or rejected')
    a=db.get(Approval,approval_id)
    if not a: raise HTTPException(404,'Approval not found')
    if a.decision != 'pending': raise HTTPException(409,'Approval already decided')
    if payload.draft is not None:
        if not payload.draft.strip() or len(payload.draft)>2000:
            raise HTTPException(422,'Draft must contain 1 to 2000 characters')
        a.draft=payload.draft
    a.decision=payload.decision;a.decided_at=datetime.now(timezone.utc)
    t=db.get(Task,a.task_id)
    if t:
        t.status='open' if payload.decision=='approved' else 'pending_review'
        m=db.get(Message,t.message_id)
        if m: m.status=payload.decision
    run=db.scalar(select(WorkflowRun).where(WorkflowRun.message_id==t.message_id)) if t else None
    if run: run.status='approved' if payload.decision=='approved' else 'rejected'
    audit(db,'approval_decided',a.id,payload.decision+' (no external action)')
    db.commit()
    return approval_json(a)

@app.get('/api/agents')
def agent_catalog():
    return {'agents':AGENTS,'autonomous':False,'outbound_actions_enabled':False,'human_approval_required':True}

@app.get('/api/workflows/diagram')
def workflow_diagram():
    return {'id':'inbox-triage-v1','name':'Inbox triage and draft approval','editable':False,
            'nodes':WORKFLOW_NODES,
            'edges':[{'source':WORKFLOW_NODES[i]['id'],'target':WORKFLOW_NODES[i+1]['id']} for i in range(len(WORKFLOW_NODES)-1)]}

@app.get('/api/workflow-runs/{run_id}')
def workflow_run_detail(run_id:str,db:Session=Depends(get_db)):
    run=db.get(WorkflowRun,run_id)
    if not run: raise HTTPException(404,'Workflow run not found')
    steps=db.scalars(select(WorkflowStep).where(WorkflowStep.run_id==run_id).order_by(WorkflowStep.order_index)).all()
    return {'id':run.id,'message_id':run.message_id,'status':run.status,'created_at':run.created_at.isoformat(),
            'steps':[{'node_id':s.node_id,'status':s.status,'detail':s.detail} for s in steps]}

@app.get('/api/workflows')
def workflows():
    return [{'id':'inbox-triage-v1','name':'Inbox triage and draft approval','mode':os.getenv('AI_PROVIDER','mock'),'enabled':True}]

@app.get('/api/workflow-runs')
def runs(db:Session=Depends(get_db)):
    items=db.scalars(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(100)).all()
    return [{'id':r.id,'message_id':r.message_id,'status':r.status,'created_at':r.created_at.isoformat()} for r in items]

@app.get('/api/audit-events')
def events(db:Session=Depends(get_db)):
    return [{'id':a.id,'event':a.event_type,'reference_id':a.reference_id,'note':a.note,'created_at':a.created_at.isoformat()} for a in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100)).all()]
