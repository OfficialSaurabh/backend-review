from sqlalchemy.orm import Session
from app.models import (
    ReviewSession, ReviewFile,
    ReviewIssue, ReviewSuggestion, ReviewMetric
)

def save_file_review(db: Session, response: dict):
    session = ReviewSession(
        project=response["project"],
        mode=response["mode"],
        overall_score=response["overallProjectScore"],
        raw_response=response,
    )
    db.add(session)
    db.flush()  # get session.id

    file_data = response["file"]

    file = ReviewFile(
        session_id=session.id,
        filename=response["filename"],
        file_score=file_data.get("overallFileScore"),
        language="javascript",  # already detected earlier
    )
    db.add(file)
    db.flush()

    for issue in file_data.get("issues", []):
        db.add(ReviewIssue(
            file_id=file.id,
            line_number=issue.get("line"),
            severity=issue["severity"],
            issue_type=issue.get("type"),
            message=issue["message"],
        ))

    for sug in file_data.get("suggestions", []):
        db.add(ReviewSuggestion(
            file_id=file.id,
            title=sug["title"],
            explanation=sug["explanation"],
            diff_example=sug.get("diff_example"),
        ))

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
