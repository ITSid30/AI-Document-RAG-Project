from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from app.db.session import Base

class Document(Base):
    __tablename__ = "documents"

    # TODO: define columns here
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    upload_time = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    page_count = Column(Integer, nullable=True)
    status = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    
    summary = Column(String, nullable=True)
    summary_status = Column(String, nullable=True) # "pending" | "ready" | "failed"
    
    
# from sqlalchemy import inspect
# from app.db.session import engine

# if __name__ == "__main__":
#     print([c["name"] for c in inspect(engine).get_columns("documents")])