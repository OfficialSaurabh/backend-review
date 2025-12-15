from pydantic import BaseModel
from typing import Optional

class ReviewRequest(BaseModel):
    action: str  # "file" | "full"
    owner: str
    repo: str
    ref: str
    filename: Optional[str] = None
