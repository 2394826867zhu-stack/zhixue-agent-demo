from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    studyspace_session_id: str | None = None
    # When set, Agent receives the course lesson as context (StudySpace mode)
