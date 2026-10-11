
from app.db.session import SessionLocal

def summarize_document(document_id, chunks):
    db = SessionLocal()
    try:
        # FILL: fetch the Document by id
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f"Summary skipped: document {document_id} not found")
            return
        
        summary = generate_summary(chunks)
        
        document.summary = summary
        document.summary_status = "ready"
        db.commit()
    except Exception as e:
        db.rollback()
        
        try:
            # 5. Retry updating the status in a fresh transaction block
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.summary_status = "failed"
                db.commit()
        except Exception as nested_e:
            # If the database is completely down, this will catch it
            print(f"Failed to save error status to database: {nested_e}")
            db.rollback()
            
        print(f"Summary failed for document {document_id}: {e}")
    finally:
        db.close()
  