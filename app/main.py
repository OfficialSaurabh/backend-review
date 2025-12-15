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

app = FastAPI(title="AI Project Review API")
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
        raise HTTPException(400, "Unsupported action")

    if req.action == "file":
        if not req.filename:
            raise HTTPException(400, "filename required")

        data = await get_file_content(req.owner, req.repo, req.ref, req.filename)
        content = base64.b64decode(data["content"]).decode()
        prompt = build_file_prompt(
            owner=req.owner,
            repo=req.repo,
            ref=req.ref,
            filename=req.filename,
            language="javascript",  # or detect dynamically
            content=content,
        )
        print("Generated Prompt:", prompt[:500])
        raw_review = review_code(prompt)
        file_review = extract_json_from_gemini(raw_review)
        issues = file_review.get("issues", [])
        overall = file_review.get("overallFileScore", 0)
        return {
          "project": f"{req.owner}/{req.repo}@{req.ref}",
          "mode": "file",
          "filename": req.filename,
          "overallProjectScore": overall,
          "topIssues": issues,
          "file": file_review,
    }

        # prompt = build_file_prompt(req.filename, content)
        # result = review_code(prompt)

        # return {"type": "file", "review": result}
        

    # FULL PROJECT REVIEW
    tree = await get_repo_tree(req.owner, req.repo, req.ref)

    results = []

    for item in tree:
        if item["type"] != "blob":
            continue

        path = item["path"]

        # skip non-code files if you want
        if not is_reviewable_file(path):
            continue

        file_data = await get_file_content(req.owner, req.repo, req.ref, path)
        content = base64.b64decode(file_data["content"]).decode()

        # language = detect_language(path)

        prompt = build_project_prompt(
            owner=req.owner,
            repo=req.repo,
            ref=req.ref,
            filename=path,
            language="javascript",  # or detect dynamically
            content=content,
        )

        raw = review_code(prompt)
        parsed = extract_json_from_gemini(raw)

        results.append(parsed)

        all_issues = []
        scores = []

        for r in results:
            all_issues.extend(r.get("issues", []))
            if "overallFileScore" in r:
                scores.append(r["overallFileScore"])

        overall_project_score = (
            sum(scores) // len(scores) if scores else 0
        )

    return {
        "project": f"{req.owner}/{req.repo}@{req.ref}",
        "mode": "full",
        "overallProjectScore": overall_project_score,
        "filesReviewed": len(results),
        "topIssues": all_issues[:20],
        "files": results,
    }


