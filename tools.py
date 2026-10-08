from pydantic import BaseModel

class Source(BaseModel):
    title: str
    url: str

class Position(BaseModel):
    company: str
    role: str
    period: str

class PersonReport(BaseModel):
    full_name: str
    summary: str
    confidence: str
    career: list[Position]
    notable_work: list[str]
    public_appearances: list[Source]
    interview_questions: list[str]
    sources: list[Source]