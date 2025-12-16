from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

DATABASE_URL = "mysql+pymysql://root:Saurabh%40202507@localhost:3306/ai_review"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
