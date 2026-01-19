from sqlalchemy.orm import Session
from app.models import (
    ReviewSession, ReviewFile,
    ReviewIssue, ReviewSuggestion, ReviewMetric
)

ALLOWED_SEVERITIES = {"critical", "major", "minor"}

def _validate_severity(value: str) -> str:
    if value not in ALLOWED_SEVERITIES:
        raise ValueError(f"Invalid severity '{value}' from AI")
    return value


def save_file_review(db: Session, response: dict):
    project = response["project"]
    filename = response["filename"]
    file_data = response["file"]

    # 1. Create session (history)
    session = ReviewSession(
        project=project,
        mode=response["mode"],
        overall_score=response["overallProjectScore"],
        raw_response=response,
    )
    db.add(session)
    db.flush()

    # 2. Find existing file for this project + filename
    existing_file = (
        db.query(ReviewFile)
        .join(ReviewSession)
        .filter(
            ReviewSession.project == project,
            ReviewFile.filename == filename,
        )
        .first()
    )

    if existing_file:
        file = existing_file
        file.session_id = session.id
        file.file_score = file_data.get("overallFileScore")
        language=file_data.get("language")

        db.query(ReviewIssue).filter_by(file_id=file.id).delete()
        db.query(ReviewSuggestion).filter_by(file_id=file.id).delete()
        db.query(ReviewMetric).filter_by(file_id=file.id).delete()
    else:
        file = ReviewFile(
            session_id=session.id,
            filename=filename,
            file_score=file_data.get("overallFileScore"),
            language="javascript",
        )
        db.add(file)
        db.flush()

    # 3. Issues (NEW SCHEMA)
    for issue in file_data.get("issues", []):
        db.add(ReviewIssue(
            file_id=file.id,
            start_line=issue.get("startLine"),
            end_line=issue.get("endLine"),
            severity=_validate_severity(issue["severity"]),
            issue_type=issue.get("type"),
            message=issue["message"],
            code_snippet=issue.get("codeSnippet"),
        ))

    # 4. Suggestions
    for sug in file_data.get("suggestions", []):
        db.add(ReviewSuggestion(
            file_id=file.id,
            title=sug["title"],
            explanation=sug["explanation"],
            diff_example=sug.get("diff_example"),
        ))

    # 5. Metrics
    metrics = file_data.get("metrics")
    if metrics:
        db.add(ReviewMetric(
            file_id=file.id,
            complexity=metrics.get("complexity"),
            readability=metrics.get("readability"),
            test_coverage_estimate=metrics.get("testCoverageEstimate"),
            documentation_score=metrics.get("documentationScore"),
        ))

    db.commit()


def save_full_review(db: Session, response: dict):
    project = response["project"]
    files = response["files"]

    # 1. Create session
    session = ReviewSession(
        project=project,
        mode=response["mode"],
        overall_score=response["overallProjectScore"],
        raw_response=response,
    )
    db.add(session)
    db.flush()

    for file_data in files:
        filename = file_data.get("filename") or file_data.get("path")
        normalized_filename = filename if filename.startswith("/") else f"/{filename}"

        existing_file = (
            db.query(ReviewFile)
            .join(ReviewSession)
            .filter(
                ReviewSession.project == project,
                ReviewFile.filename == normalized_filename,
            )
            .first()
        )

        if existing_file:
            file = existing_file
            file.session_id = session.id
            file.file_score = file_data.get("overallFileScore")
            file.language = "javascript"

            db.query(ReviewIssue).filter_by(file_id=file.id).delete()
            db.query(ReviewSuggestion).filter_by(file_id=file.id).delete()
            db.query(ReviewMetric).filter_by(file_id=file.id).delete()
        else:
            file = ReviewFile(
                session_id=session.id,
                filename=normalized_filename,
                file_score=file_data.get("overallFileScore"),
                language="javascript",
            )
            db.add(file)
            db.flush()

        # 2. Issues (NEW SCHEMA)
        for issue in file_data.get("issues", []):
            db.add(ReviewIssue(
                file_id=file.id,
                start_line=issue.get("startLine"),
                end_line=issue.get("endLine"),
                severity=_validate_severity(issue["severity"]),
                issue_type=issue.get("type"),
                message=issue["message"],
                code_snippet=issue.get("codeSnippet"),
            ))

        # 3. Suggestions
        for sug in file_data.get("suggestions", []):
            db.add(ReviewSuggestion(
                file_id=file.id,
                title=sug["title"],
                explanation=sug["explanation"],
                diff_example=sug.get("diff_example"),
            ))

        # 4. Metrics
        metrics = file_data.get("metrics")
        if metrics:
            db.add(ReviewMetric(
                file_id=file.id,
                complexity=metrics.get("complexity"),
                readability=metrics.get("readability"),
                test_coverage_estimate=metrics.get("testCoverageEstimate"),
                documentation_score=metrics.get("documentationScore"),
            ))

    db.commit()
