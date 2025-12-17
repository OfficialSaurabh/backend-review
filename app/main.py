from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import ReviewRequest
from app.github_service import get_file_content, get_repo_tree
from app.gemini_service import review_code
from app.review_builders import build_file_prompt, build_project_prompt
import base64
from pathlib import Path
from app.gemini_parser import extract_json_from_gemini
from pathlib import Path
from app.review_persistence import save_file_review
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import Base, get_db
from app.database import engine
from app.models import Base
from app.models import (
    Base,
    ReviewRequest,
    ReviewFile,
    ReviewSession,
)

Base.metadata.create_all(bind=engine)


from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Project Review API")

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔴 tighten this later
    allow_credentials=True,
    allow_methods=["*"],  # allows OPTIONS, POST, etc.
    allow_headers=["*"],
)


# Code + config files worth reviewing
REVIEWABLE_EXTENSIONS = {
    ".js", ".ts", ".jsx", ".tsx",
    ".py", ".java", ".kt", ".go",
    ".rs", ".cpp", ".c", ".cs",
    ".php", ".rb", ".swift",
    ".html", ".css", ".scss",
    ".json", ".yml", ".yaml",
    ".md", ".sh"
}

# Directories we NEVER want to review
EXCLUDED_DIRS = {
    "node_modules",
    "dist",
    "build",
    "out",
    "coverage",
    ".next",
    ".git",
    "vendor",
    "__pycache__",
}

EXTENSION_LANGUAGE_MAP = {
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".py": "python",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".md": "markdown",
    ".sh": "shell",
}

def detect_language(path: str) -> str:
    return EXTENSION_LANGUAGE_MAP.get(
        Path(path).suffix.lower(),
        "text",
    )

def is_reviewable_file(path: str) -> bool:
    p = Path(path)

    # Exclude junk directories
    for part in p.parts:
        if part in EXCLUDED_DIRS:
            return False

    # Exclude files without extensions (except known cases)
    if p.suffix == "":
        return False

    return p.suffix.lower() in REVIEWABLE_EXTENSIONS


@app.post("/review")
async def review(req: ReviewRequest, db: Session = Depends(get_db)):
    if req.action not in ("file", "full"):
        raise HTTPException(status_code=400, detail="Unsupported action")

    try:
        if req.action == "file":
            if not req.filename:
                raise HTTPException(status_code=400, detail="filename required")

            try:
                data = await get_file_content(req.owner, req.repo, req.ref, req.filename)
            except Exception as e:
                logger.exception("GitHub file fetch failed")
                raise HTTPException(
                    status_code=502,
                    detail="Failed to fetch file from GitHub"
                )

            try:
                content = base64.b64decode(data["content"]).decode()
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to decode file content"
                )

            prompt = build_file_prompt(
                owner=req.owner,
                repo=req.repo,
                ref=req.ref,
                filename=req.filename,
                language="javascript",
                content=content,
            )

            try:
                raw_review = review_code(prompt)
                file_review = extract_json_from_gemini(raw_review)
            except Exception:
                logger.exception("Gemini processing failed")
                raise HTTPException(
                    status_code=502,
                    detail="AI review service failed"
                )

            response = {
                "project": f"{req.owner}/{req.repo}@{req.ref}",
                "mode": "file",
                "filename": req.filename,
                "overallProjectScore": file_review.get("overallFileScore", 0),
                "topIssues": file_review.get("issues", []),
                "file": file_review,
            }

            save_file_review(db, response)

            return response

        # ---------- FULL PROJECT REVIEW ----------
        try:
            tree = await get_repo_tree(req.owner, req.repo, req.ref)
        except Exception:
            logger.exception("GitHub repo tree fetch failed")
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch repository tree"
            )

        results = []
        all_issues = []
        scores = []

        for item in tree:
            if item["type"] != "blob":
                continue

            path = item["path"]
            if not is_reviewable_file(path):
                continue

            try:
                file_data = await get_file_content(req.owner, req.repo, req.ref, path)
                content = base64.b64decode(file_data["content"]).decode("utf-8", errors="ignore")
                language = detect_language(path)

                prompt = build_project_prompt(
                    owner=req.owner,
                    repo=req.repo,
                    ref=req.ref,
                    filename=path,
                    language=language,
                    content=content,
                )

                raw = review_code(prompt)
                parsed = extract_json_from_gemini(raw)

                results.append(parsed)
                all_issues.extend(parsed.get("issues", []))
                if "overallFileScore" in parsed:
                    scores.append(parsed["overallFileScore"])

            except Exception:
                # IMPORTANT: skip failed file, don't kill whole review
                logger.exception(f"Failed reviewing file: {path}")
                continue

        overall_project_score = sum(scores) // len(scores) if scores else 0

        return {
            "project": f"{req.owner}/{req.repo}@{req.ref}",
            "mode": "full",
            "overallProjectScore": overall_project_score,
            "filesReviewed": len(results),
            "topIssues": all_issues[:20],
            "files": results,
        }

    except HTTPException:
        # rethrow clean API errors
        raise

@app.get("/reviews/last")
def get_last_review(
    project: str,
    filename: str,
    db: Session = Depends(get_db),
):
    file = (
        db.query(ReviewFile)
        .join(ReviewSession)
        .filter(
            ReviewSession.project == project,
            ReviewFile.filename == filename,
        )
        .order_by(ReviewSession.created_at.desc())
        .first()
    )

    if not file:
        return {"exists": False, "message": "No previous review found for this file."}

    return {
        "exists": True,
        "createdAt": file.created_at,
        "filename": file.filename,
        "fileScore": file.file_score,
        "issues": [
            {
                "line": i.line_number,
                "severity": i.severity,
                "type": i.issue_type,
                "message": i.message,
            }
            for i in file.issues
        ],
        "metrics": {
            "complexity": file.metrics.complexity if file.metrics else None,
            "readability": file.metrics.readability if file.metrics else None,
            "testCoverageEstimate": file.metrics.test_coverage_estimate if file.metrics else None,
            "documentationScore": file.metrics.documentation_score if file.metrics else None,
        },
    }
