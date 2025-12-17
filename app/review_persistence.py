from sqlalchemy.orm import Session
from app.models import (
    ReviewSession, ReviewFile,
    ReviewIssue, ReviewSuggestion, ReviewMetric
)

def save_file_review(db: Session, response: dict):
    project = response["project"]
    filename = response["filename"]
    file_data = response["file"]

    # 1. Always create a new session (history)
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
        # UPDATE existing file
        file = existing_file
        file.session_id = session.id
        file.file_score = file_data.get("overallFileScore")
        file.language = "javascript"

        # Remove old children
        db.query(ReviewIssue).filter_by(file_id=file.id).delete()
        db.query(ReviewSuggestion).filter_by(file_id=file.id).delete()
        db.query(ReviewMetric).filter_by(file_id=file.id).delete()
    else:
        # INSERT new file
        file = ReviewFile(
            session_id=session.id,
            filename=filename,
            file_score=file_data.get("overallFileScore"),
            language="javascript",
        )
        db.add(file)
        db.flush()

    # Insert issues
    for issue in file_data.get("issues", []):
        db.add(ReviewIssue(
            file_id=file.id,
            line_number=issue.get("line"),
            severity=issue["severity"],
            issue_type=issue.get("type"),
            message=issue["message"],
        ))

    # Insert suggestions
    for sug in file_data.get("suggestions", []):
        db.add(ReviewSuggestion(
            file_id=file.id,
            title=sug["title"],
            explanation=sug["explanation"],
            diff_example=sug.get("diff_example"),
        ))

    # Insert metrics
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
