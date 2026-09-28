from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .orchestrator.state import AnalysisRequest

JobStatus = Literal['PENDING', 'RUNNING', 'WAITING_APPROVAL', 'DONE', 'FAILED', 'REJECTED']


class TaskRequest(AnalysisRequest):
    save_result: StrictBool = False
    batch_id: str | None = Field(default=None, max_length=100)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    approved: bool
