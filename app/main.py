from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import ReviewRequest
from app.github_service import get_file_content, get_repo_tree
from app.gemini_service import review_code
from app.review_builders import build_file_prompt, build_project_prompt
from app.providers.factory import get_provider
import base64
import base64
from pathlib import Path
from app.gemini_parser import extract_json_from_gemini
from pathlib import Path
from app.review_persistence import save_file_review, save_full_review
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import Base, get_db
from app.database import engine
from app.models import Base
import time
from app.models import (
    Base,
    ReviewRequest,
    ReviewFile,
    ReviewSession,
)
from app.deps import (
    hash_content,
    get_cached_review,
    set_cached_review,
    rate_limit,
    r
)
from fastapi import Depends
from contextlib import asynccontextmanager


Base.metadata.create_all(bind=engine)


from fastapi.responses import JSONResponse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        r.ping()
        logger.info("✅ Upstash Redis connected successfully")
    except Exception as e:
        logger.error("❌ Upstash Redis connection failed: %s", str(e))

    yield

    # Shutdown (optional)
    try:
        r.close()
        logger.info("🛑 Redis connection closed")
    except Exception:
        pass

app = FastAPI(
    title="AI Project Review API",
    lifespan=lifespan
)

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

@app.get("/health/redis")
def redis_health_debug():
    try:
        start = time.time()
        r.ping()
        latency_ms = round((time.time() - start) * 1000, 2)

        info = r.info()

        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "used_memory": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/review")
async def review(req: ReviewRequest, ctx=Depends(rate_limit), db: Session = Depends(get_db)):
    if req.action not in ("file", "full"):
        raise HTTPException(status_code=400, detail="Unsupported action")
    # ---------- LOCAL FILE REVIEW ----------
    if req.action == "file" and req.mode == "local":
        if not req.files or len(req.files) == 0:
            raise HTTPException(status_code=400, detail="files required for local review")

        results = []

        for f in req.files:
            content_hash = hash_content(f.content, ctx["user_id"])
            cached = get_cached_review(content_hash)
            if cached:
                results.append(cached)
                continue
            language = detect_language(f.filename)

            prompt = build_file_prompt(
                owner="local",
                repo="local",
                ref="local",
                filename=f.filename,
                language=language,
                content=f.content,
            )

            try:
                raw_review = review_code(prompt)
                parsed = extract_json_from_gemini(raw_review)
            except Exception:
                logger.exception("Gemini processing failed")
                raise HTTPException(status_code=502, detail="AI review service failed")

            response = {
                "project": "local",
                "mode": "file",
                "filename": f.filename,
                "path": f.path,
                "overallProjectScore": parsed.get("overallFileScore", 0),
                "topIssues": parsed.get("issues", []),
                "file": parsed,
            }

            set_cached_review(content_hash, response) 
            results.append(response)

        return results if len(results) > 1 else results[0]

    provider = get_provider(req.provider, req.accessToken)

    try:
        # ---------- SINGLE FILE REVIEW ----------
        if req.action == "file":
            if not req.filename:
                raise HTTPException(status_code=400, detail="filename required")

            try:
                raw = await provider.get_file_content(
                    req.owner, req.repo, req.ref, req.filename
                )

                # GitHub returns base64 JSON, Bitbucket returns raw text
                if req.provider == "github":
                    content = base64.b64decode(raw["content"]).decode()
                else:  # bitbucket
                    content = raw
                content_hash = hash_content(content, ctx["user_id"])
                cached = get_cached_review(content_hash)
                if cached:
                    print("Returning cached review")
                    return cached


            except Exception:
                logger.exception("File fetch failed")
                raise HTTPException(status_code=502, detail="Failed to fetch file")

            language = detect_language(req.filename)

            prompt = build_file_prompt(
                owner=req.owner,
                repo=req.repo,
                ref=req.ref,
                filename=req.filename,
                language=language,
                content=content,
            )

            try:
                raw_review = review_code(prompt)
                file_review = extract_json_from_gemini(raw_review)
            except Exception:
                logger.exception("Gemini processing failed")
                raise HTTPException(status_code=502, detail="AI review service failed")

            response = {
                "project": f"{req.provider}:{req.owner}/{req.repo}@{req.ref}",
                "mode": "file",
                "filename": req.filename,
                "language": language,
                "overallProjectScore": file_review.get("overallFileScore", 0),
                "topIssues": file_review.get("issues", []),
                "file": file_review,
            }

            set_cached_review(content_hash, response)
            save_file_review(db, response)
            return response

        # ---------- FULL PROJECT REVIEW ----------
        # ---------- FULL PROJECT REVIEW ----------
        try:
            tree = await provider.get_repo_tree(req.owner, req.repo, req.ref)
        except Exception:
            logger.exception("Repo tree fetch failed")
            raise HTTPException(status_code=502, detail="Failed to fetch repository tree")

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
                raw = await provider.get_file_content(req.owner, req.repo, req.ref, path)

                if req.provider == "github":
                    content = base64.b64decode(raw["content"]).decode("utf-8", errors="ignore")
                else:
                    content = raw

                content_hash = hash_content(content, ctx["user_id"])
                cached = get_cached_review(content_hash)

                if cached:
                    parsed = cached["file"]
                else:
                    language = detect_language(path)

                    prompt = build_project_prompt(
                        owner=req.owner,
                        repo=req.repo,
                        ref=req.ref,
                        filename=path,
                        language=language,
                        content=content,
                    )

                    raw_review = review_code(prompt)
                    parsed = extract_json_from_gemini(raw_review)

                    cache_payload = {
                        "project": f"{req.provider}:{req.owner}/{req.repo}@{req.ref}",
                        "mode": "file",
                        "filename": path,
                        "overallProjectScore": parsed.get("overallFileScore", 0),
                        "topIssues": parsed.get("issues", []),
                        "file": parsed,
                    }

                    set_cached_review(content_hash, cache_payload)

                results.append(parsed)
                all_issues.extend(parsed.get("issues", []))
                if "overallFileScore" in parsed:
                    scores.append(parsed["overallFileScore"])

            except Exception:
                logger.exception(f"Failed reviewing file: {path}")
                continue

        overall_project_score = sum(scores) // len(scores) if scores else 0

        def avg(values):
            return round(sum(values) / len(values)) if values else 0

        metrics_list = [f.get("metrics", {}) for f in results]

        full_metrics = {
            "complexity": avg([m.get("complexity", 0) for m in metrics_list]),
            "readability": avg([m.get("readability", 0) for m in metrics_list]),
            "testCoverageEstimate": avg([m.get("testCoverageEstimate", 0) for m in metrics_list]),
            "documentationScore": avg([m.get("documentationScore", 0) for m in metrics_list]),
        }

        full_response = {
            "project": f"{req.provider}:{req.owner}/{req.repo}@{req.ref}",
            "mode": "full",
            "overallProjectScore": overall_project_score,
            "filesReviewed": len(results),
            "file": {"metrics": full_metrics},
            "topIssues": all_issues[:20],
            "files": results,
        }

        save_full_review(db, full_response)
        return full_response

        # try:
        #     tree = await provider.get_repo_tree(req.owner, req.repo, req.ref)
        # except Exception:
        #     logger.exception("Repo tree fetch failed")
        #     raise HTTPException(status_code=502, detail="Failed to fetch repository tree")

        # results = []
        # all_issues = []
        # scores = []

        # for item in tree:
        #     if item["type"] != "blob":
        #         continue

        #     path = item["path"]
        #     if not is_reviewable_file(path):
        #         continue

        #     try:
        #         raw = await provider.get_file_content(req.owner, req.repo, req.ref, path)

        #         if req.provider == "github":
        #             content = base64.b64decode(raw["content"]).decode("utf-8", errors="ignore")
        #         else:
        #             content = raw

        #         language = detect_language(path)

        #         prompt = build_project_prompt(
        #             owner=req.owner,
        #             repo=req.repo,
        #             ref=req.ref,
        #             filename=path,
        #             language=language,
        #             content=content,
        #         )

        #         raw_review = review_code(prompt)
        #         parsed = extract_json_from_gemini(raw_review)

        #         results.append(parsed)
        #         all_issues.extend(parsed.get("issues", []))
        #         if "overallFileScore" in parsed:
        #             scores.append(parsed["overallFileScore"])

        #     except Exception:
        #         logger.exception(f"Failed reviewing file: {path}")
        #         continue

        # overall_project_score = sum(scores) // len(scores) if scores else 0

        # def avg(values):
        #     return round(sum(values) / len(values)) if values else 0

        # metrics_list = [f.get("metrics", {}) for f in results]

        # full_metrics = {
        #     "complexity": avg([m.get("complexity", 0) for m in metrics_list]),
        #     "readability": avg([m.get("readability", 0) for m in metrics_list]),
        #     "testCoverageEstimate": avg([m.get("testCoverageEstimate", 0) for m in metrics_list]),
        #     "documentationScore": avg([m.get("documentationScore", 0) for m in metrics_list]),
        # }

        # full_response = {
        #     "project": f"{req.provider}:{req.owner}/{req.repo}@{req.ref}",
        #     "mode": "full",
        #     "overallProjectScore": overall_project_score,
        #     "filesReviewed": len(results),
        #     "file": {"metrics": full_metrics},
        #     "topIssues": all_issues[:20],
        #     "files": results,
        # }

        # save_full_review(db, full_response)
        # return full_response

    except HTTPException:
        raise


# Last Review Retrieval Endpoint
# @app.get("/reviews/last")
# def get_last_review(
#     provider: str,
#     owner: str,
#     repo: str,
#     ref: str,
#     filename: str,
#     db: Session = Depends(get_db),
# ):
#     project = f"{provider}:{owner}/{repo}@{ref}"

#     file = (
#         db.query(ReviewFile)
#         .join(ReviewSession)
#         .filter(
#             ReviewSession.project == project,
#             ReviewFile.filename == filename,
#         )
#         .order_by(ReviewSession.created_at.desc())
#         .first()
#     )

#     if not file:
#         return {"exists": False, "message": "No previous review found for this file."}

#     return {
#         "exists": True,
#         "createdAt": file.created_at,
#         "filename": file.filename,
#         "fileScore": file.file_score,
#         "language": file.language,
#         "issues": [
#             {
#                 "startLine": i.start_line,
#                 "endLine": i.end_line,
#                 "severity": i.severity,
#                 "type": i.issue_type,
#                 "message": i.message,
#                 "codeSnippet": i.code_snippet,
#             }
#             for i in file.issues
#         ],
#         "metrics": {
#             "complexity": file.metrics.complexity if file.metrics else None,
#             "readability": file.metrics.readability if file.metrics else None,
#             "testCoverageEstimate": file.metrics.test_coverage_estimate if file.metrics else None,
#             "documentationScore": file.metrics.documentation_score if file.metrics else None,
#         },
#     }
@app.get("/reviews/last")
def get_last_review(
    provider: str,
    owner: str,
    repo: str,
    ref: str,
    filename: str,
    db: Session = Depends(get_db),
):
    project = f"{provider}:{owner}/{repo}@{ref}"
    latest_session = (
        db.query(ReviewSession)
        .filter(ReviewSession.project == project)
        .order_by(ReviewSession.created_at.desc())
        .first()
    )

    file = (
        db.query(ReviewFile)
        .join(ReviewSession)
        .filter(
            ReviewFile.session_id == latest_session.id,
            # ReviewSession.project == project,
            ReviewFile.filename == filename,
        )
        .order_by(ReviewSession.created_at.desc())
        .first()
    )

    if not file:
        return {"exists": False, "message": "No previous review found for this file."}

    # Build issue map
    issue_map = {}
    for issue in file.issues:
        issue_map[issue.id] = {
            "id": issue.id,
            "startLine": issue.start_line,
            "endLine": issue.end_line,
            "severity": issue.severity,
            "type": issue.issue_type,
            "message": issue.message,
            "codeSnippet": issue.code_snippet,
            "suggestions": []
        }

    # Attach suggestions to issues
    for sug in file.suggestions:
        target = issue_map.get(sug.issue_id)
        if target is not None:
            target["suggestions"].append({
                "id": sug.id,
                "title": sug.title,
                "explanation": sug.explanation,
                "diff_example": sug.diff_example,
            })

    return {
        "exists": True,
        "createdAt": file.created_at,
        "filename": file.filename,
        "fileScore": file.file_score,
        "language": file.language,
        "issues": list(issue_map.values()),
        "metrics": {
            "complexity": file.metrics.complexity if file.metrics else None,
            "readability": file.metrics.readability if file.metrics else None,
            "testCoverageEstimate": file.metrics.test_coverage_estimate if file.metrics else None,
            "documentationScore": file.metrics.documentation_score if file.metrics else None,
        },
    }


@app.get("/reviews/full/last")
def get_last_full_review(
    provider: str,
    owner: str,
    repo: str,
    ref: str,
    db: Session = Depends(get_db),
):
    project = f"{provider}:{owner}/{repo}@{ref}"

    session = (
        db.query(ReviewSession)
        .filter(
            ReviewSession.project == project,
            ReviewSession.mode == "full"
        )
        .order_by(ReviewSession.created_at.desc())
        .first()
    )

    if not session or not session.raw_response:
        return {"exists": False, "message": "No previous full review found."}

    raw = session.raw_response

    metrics = raw.get("file", {}).get("metrics", {})
    top_issues = raw.get("topIssues", [])
    overall = raw.get("overallProjectScore", 0)

    return {
        "exists": True,
        "createdAt": session.created_at,
        "filename": "FULL_PROJECT",
        "fileScore": overall,
        "issues": top_issues,
        "metrics": {
            "complexity": metrics.get("complexity", 0),
            "readability": metrics.get("readability", 0),
            "testCoverageEstimate": metrics.get("testCoverageEstimate", 0),
            "documentationScore": metrics.get("documentationScore", 0),
        },
    }


@app.get("/reviews/files")
def list_reviewed_files(
    provider: str,
    owner: str,
    repo: str,
    ref: str,
    db: Session = Depends(get_db),
):
    project = f"{provider}:{owner}/{repo}@{ref}"
    files = (
        db.query(ReviewFile.filename)
        .join(ReviewSession)
        .filter(ReviewSession.project == project)
        .distinct()
        .all()
    )

    return {
        "project": project,
        "files": [f.filename for f in files],
    }
