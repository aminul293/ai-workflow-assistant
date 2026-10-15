"""Explicit, testable agent roles. Only classifier optionally calls an LLM.

Agents are orchestration stages, not autonomous background workers. External side
effects are deliberately forbidden in this synthetic-data-only prototype.
"""
from dataclasses import dataclass
from typing import Callable
from app.ai_processor import Extraction, extract, ProcessorError

ALLOWED_CATEGORIES = {'billing','scheduling','service_request','general_inquiry'}
AGENTS = [
    {'id':'intake_agent','name':'Intake agent','purpose':'Validate and normalize sample inquiry','llm_calls':0},
    {'id':'classification_agent','name':'Classification agent','purpose':'Categorize and summarize with configured processor','llm_calls':'0 or 1'},
    {'id':'planning_agent','name':'Task planning agent','purpose':'Prepare a deterministic task proposal','llm_calls':0},
    {'id':'quality_agent','name':'Quality review agent','purpose':'Check output and route uncertain results for review','llm_calls':0},
]

@dataclass(frozen=True)
class AgentResult:
    extraction: Extraction
    provider: str
    task_title: str
    requires_review: bool
    trace: list[tuple[str,str]]

def run_agents(sender: str, subject: str, body: str,
               classifier: Callable[[str,str],tuple[Extraction,str]]|None=None) -> AgentResult:
    if not sender.strip() or not subject.strip() or not body.strip():
        raise ProcessorError('Intake agent rejected incomplete sample')
    if len(body)>10000 or len(subject)>255:
        raise ProcessorError('Intake agent rejected oversized sample')
    trace=[('intake_agent','Sample validated; no external lookup')]
    extraction, provider=(classifier or extract)(subject,body)
    trace.append(('classification_agent',f'Provider={provider}; category={extraction.category}; urgency={extraction.urgency}'))
    if extraction.category not in ALLOWED_CATEGORIES:
        raise ProcessorError('Classification category is not allowed')
    title=f'{extraction.category.replace("_"," ").title()}: {subject[:100]}'
    trace.append(('planning_agent','Task proposal created; no external actions'))
    requires_review=extraction.confidence < 0.75 or extraction.urgency=='high'
    if not extraction.summary.strip() or not extraction.draft.strip():
        raise ProcessorError('Quality review rejected empty output')
    trace.append(('quality_agent',f'Quality checks passed; manual_review={str(requires_review).lower()}; confidence={extraction.confidence:.2f}'))
    return AgentResult(extraction,provider,title,requires_review,trace)
