import math
import operator
from typing import Annotated, Any, Literal, Self

from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AgentName = Literal["research", "analysis"]
Destination = Literal["research", "analysis", "synthesis", "clarification"]


class SampleGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=40)
    values: list[float] = Field(min_length=2, max_length=1000)

    @field_validator("name", "unit", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("values", mode="before")
    @classmethod
    def check_numbers(cls, values: Any) -> list[int | float]:
        if not isinstance(values, list):
            raise ValueError("values must be a list")
        if any(
            type(v) not in (int, float) or abs(v) > 1e12 or not math.isfinite(v)
            for v in values
        ):
            raise ValueError("values must contain finite numbers bounded by 1e12")
        return values


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=8000)
    groups: list[SampleGroup] = Field(default_factory=list, max_length=2)

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def consistent_groups(self) -> Self:
        if len({g.name.casefold() for g in self.groups}) != len(self.groups):
            raise ValueError("group names must be distinct")
        if len({g.unit for g in self.groups}) > 1:
            raise ValueError("units must match explicitly")
        return self


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https?://")
    text: str = Field(min_length=1)


class GroupStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str
    unit: str
    n: int = Field(ge=2, le=1000)
    mean: float = Field(ge=-1e12, le=1e12)
    median: float = Field(ge=-1e12, le=1e12)
    stdev: float = Field(ge=0, le=3e12)


class Contribution(BaseModel):
    agent: AgentName
    status: Literal["complete", "incomplete", "error"]
    narrative: str
    sources: list[Source] = Field(default_factory=list)
    stats: list[GroupStatistics] = Field(default_factory=list)


class SupervisorDecision(BaseModel):
    next_agent: Destination
    instruction: str = Field(min_length=1, max_length=2000)
    rubric: str = Field(min_length=1, max_length=2000)


class SynthesisDecision(BaseModel):
    explanation: str = Field(min_length=1, max_length=4000)
    lower_mean: Literal["first", "second", "tie"]
    lower_dispersion: Literal["first", "second", "tie"]


class AnalysisState(MessagesState):
    request: AnalysisRequest
    next_agent: Destination
    instruction: str
    feedback: str
    contributions: Annotated[list[Contribution], operator.add]
    events: Annotated[list[dict], operator.add]
    delegations: int
    decisions: int
    completed: bool
    response: str
