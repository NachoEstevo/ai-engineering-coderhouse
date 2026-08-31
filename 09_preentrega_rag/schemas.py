from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    source: str
    chunk: int = Field(ge=0)


class RAGResponse(BaseModel):
    answer: str = Field(min_length=1)
    references: list[SourceReference]
