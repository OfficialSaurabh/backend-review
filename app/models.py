from pydantic import BaseModel, model_validator
from typing import Optional, Literal, List
import enum
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, ForeignKey,
    Enum, TIMESTAMP, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


# ---------- ENUM DEFINITIONS (portable) ----------

class ReviewMode(enum.Enum):
    file = "file"
    full = "full"

class SeverityLevel(enum.Enum):
    critical = "critical"
    major = "major"
    minor = "minor"


# ---------- TABLES ----------

class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project = Column(String(255), nullable=False)

    mode = Column(Enum(ReviewMode, name="review_mode_enum"), nullable=False)

    overall_score = Column(Integer)
    raw_response = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    files = relationship("ReviewFile", back_populates="session", cascade="all, delete")


class ReviewFile(Base):
    __tablename__ = "review_files"
    __table_args__ = (
        UniqueConstraint("session_id", "filename", name="uq_session_filename"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("review_sessions.id"), nullable=False)

    filename = Column(String(500), nullable=False)
    language = Column(String(50))
    file_score = Column(Integer)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    session = relationship("ReviewSession", back_populates="files")
    issues = relationship("ReviewIssue", cascade="all, delete")
    suggestions = relationship("ReviewSuggestion", cascade="all, delete")
    metrics = relationship("ReviewMetric", uselist=False, cascade="all, delete")


class ReviewIssue(Base):
    __tablename__ = "review_issues"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_id = Column(BigInteger, ForeignKey("review_files.id"), nullable=False)

    line_number = Column(Integer)

    severity = Column(Enum(SeverityLevel, name="severity_enum"), nullable=False)

    issue_type = Column(String(100))
    message = Column(Text, nullable=False)


class ReviewSuggestion(Base):
    __tablename__ = "review_suggestions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_id = Column(BigInteger, ForeignKey("review_files.id"), nullable=False)

    title = Column(String(255))
    explanation = Column(Text)
    diff_example = Column(Text)


class ReviewMetric(Base):
    __tablename__ = "review_metrics"

    file_id = Column(BigInteger, ForeignKey("review_files.id"), primary_key=True)

    complexity = Column(Integer)
    readability = Column(Integer)
    test_coverage_estimate = Column(Integer)
    documentation_score = Column(Integer)

class LocalReviewFile(BaseModel):
    filename: str
    path: str  
    content: str
# class ReviewRequest(BaseModel):
#     action: Literal["file", "full"]
#     owner: Optional[str] = None
#     # localProjectId: Optional[str]
#     repo: Optional[str] = None
#     ref: Optional[str] = None
#     filename: Optional[str] = None
#     mode: Optional[str] = None
#     files: Optional[List[LocalReviewFile]] = None

class ReviewFileInput(BaseModel):
    filename: str
    path: str
    content: str
class ReviewRequest(BaseModel):
    provider: Optional[Literal["github", "bitbucket"]] = None
    action: Literal["file", "full"]
    accessToken: Optional[str] = None
    mode: Optional[Literal["local"]] = None
    owner: str
    repo: Optional[str] = None
    ref: Optional[str] = None
    filename: Optional[str] = None
    files: Optional[List[ReviewFileInput]] = None
    localProjectId: Optional[str] = None

    @model_validator(mode="after")
    def validate_context(self):
        # Local file review
        if self.mode == "local":
            if not self.files:
                raise ValueError("files are required for local review")
            return self

        # Remote (GitHub / Bitbucket)
        if not self.provider:
            raise ValueError("provider is required")
        if not self.accessToken:
            raise ValueError("accessToken is required")
        if not self.repo or not self.ref:
            raise ValueError("repo and ref are required")

        return self

