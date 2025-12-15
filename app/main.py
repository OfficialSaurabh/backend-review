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
async def review(req: ReviewRequest):
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

            return {
                "project": f"{req.owner}/{req.repo}@{req.ref}",
                "mode": "file",
                "filename": req.filename,
                "overallProjectScore": file_review.get("overallFileScore", 0),
                "topIssues": file_review.get("issues", []),
                "file": file_review,
            }

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
                content = base64.b64decode(file_data["content"]).decode()

                prompt = build_project_prompt(
                    owner=req.owner,
                    repo=req.repo,
                    ref=req.ref,
                    filename=path,
                    language=req.language,
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
