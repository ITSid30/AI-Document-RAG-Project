from fastapi import APIRouter, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.models.document import Document
import os
from datetime import datetime, timezone
from app.services.ingestion import extract_text_by_page, chunk_text
from app.services.embeddings import collection, embed_and_store_chunks
from app.services.generation import generate_answer, generate_summary
from app.services.retrieval import retrieve_relevant_chunks
from app.services.summary import summarize_document
from fastapi import BackgroundTasks

router = APIRouter()

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB
UPLOAD_DIR = "storage/uploads"
NOT_FOUND_THRESHOLD = 1.5 ## Adjust this based on your actual threshold configuration

@router.post("/documents/upload")
async def upload_document(file: UploadFile, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 1. Check file.filenameew ends with .pdf → else raise HTTPException(400, ...)
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file extension. Only PDFs allowed.")

    # 2. Read file contents: contents = await file.read()
    #    Check len(contents) against MAX_FILE_SIZE → else raise HTTPException(400, ...)
    contents = await file.read()
    if(len(contents) > MAX_FILE_SIZE):
        raise HTTPException(status_code=400, detail=f"File size exceeds the maximum limit of {MAX_FILE_SIZE // (1024 * 1024)} MB.") 
    
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    # Step 2: insert row FIRST with placeholder path, to get an auto-generated id
    db_document = Document(status="processing", filename=os.path.basename(file.filename),
                           file_path="", upload_time=datetime.now(timezone.utc))
    db.add(db_document)
    db.commit()
    db.refresh(db_document)  # now db_document.id is populated

    # Step 3: build the real unique path using db_document.id
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{db_document.id}.pdf")

    # Step 4: try saving the file; on failure, mark status="failed" instead of raising immediately
    try:
        with open(file_path, "wb") as f:
            f.write(contents)
        pass
    except Exception as e:
        db_document.status = "failed"
        db_document.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to save file.")

    # Step 5: update the row now that file_path and save succeeded
    db_document.file_path = file_path
    db.commit()
    
    # Step 6:
    try:
        pages = extract_text_by_page(file_path)
        chunks = chunk_text(pages, chunk_size=150, overlap=30)
       
        ## Embeding the chunk of text
        embed_and_store_chunks(chunks, db_document.id)
        
        chunk_count = len(chunks)
        print(f"Total chunks: {chunk_count}")
        
        db_document.status = "ready"
        db_document.summary_status = "pending"
        db_document.page_count = len(pages)
        db.commit()
    
    except Exception as e:
        try:
            collection.delete(where={"document_id": db_document.id})
        except Exception as cleanup_error:
            print(f"Vector cleanup failed for document {db_document.id}: {cleanup_error}")
        db_document.status = "failed"
        db_document.summary_status = None
        db_document.error_message = str(e)
        db.commit()
        
    if db_document.status == "ready":
        background_tasks.add_task(summarize_document, db_document.id, chunks)

    return {
        "document_id": db_document.id, 
        "status": db_document.status,
        "error_message": db_document.error_message
    }
    
@router.get("/documents/{document_id}/status")
def get_status(document_id: int, db: Session = Depends(get_db)):
    # FILL: query the Document table by id
    document = db.query(Document).filter(Document.id == document_id).first()
    # FILL: if not found, raise HTTPException(404, ...)
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with id {document_id} not found"
        )
    
    # FILL: return status, error_message, page_count
    return {
        "status": document.status,
        "error_message": document.error_message,
        "page_count": document.page_count
    }
    
@router.post("/documents/{document_id}/question")
def ask_question(document_id: int, question: str, db: Session = Depends(get_db)):
    # FILL Step 1: look up the document by id; 404 if not found
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
         raise HTTPException(status_code=404, detail=f"Document with ID {document_id} not found")
     
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question.strip()) > 500:
        raise HTTPException(status_code=400, detail="Question is too long to process")
    
    # FILL Step 2: if document.status != "ready", return a clear error 
    if document.status != "ready":
        raise HTTPException(status_code=409, detail=f"Document is not ready for questions. Current status: {document.status}")
    
    # FILL Step 3: call retrieve_relevant_chunks(question, document_id)
    chunks = retrieve_relevant_chunks(question=question, document_id=document_id, top_k=3)
    for c in chunks:
        print(c["page_number"], c["distance"], c["chunk_text"][:100])
    print("Distances: ", [c["distance"] for c in chunks])
    
    # FILL Step 4: check the best (minimum) distance among retrieved chunks
    if not chunks:
        return { "answer": "I don't know based on the provided document.", "sources": [] }
    
    best_distance = min(chunk["distance"] for chunk in chunks)
    
    if(best_distance > NOT_FOUND_THRESHOLD):
        return  { "answer": "I don't know based on the provided document.", "sources": [] }
    
    # FILL Step 5: otherwise, call generate_answer(question, chunks)
    try:
        answer = generate_answer(question=question, context_chunks=chunks)
    except Exception as e:
        print(f"Generation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="The answer service is unavailable. Make sure Ollama is running.",
        )
    
    NOT_FOUND_ANSWER = "I don't know based on the provided document."

    if NOT_FOUND_ANSWER in answer:
        return {"answer": NOT_FOUND_ANSWER, "sources": []}
    
    # FILL Step 6: build a "sources" list — unique page numbers from the retrieved chunks
    unique_pages = sorted(list(set(chunk["page_number"] for chunk in chunks)))    
    # FILL Step 7: return {"answer": ..., "sources": [...]}
    return {"answer": answer, "sources": unique_pages}
      
        
@router.get("/documents/{document_id}/summary")
def get_summary(document_id: int, db: Session = Depends(get_db)):
    # FILL: fetch the document, raise 404 if missing
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail=f"Document with id {document_id} not found")
    
    return {"summary_status": document.summary_status, "summary": document.summary}
    

# ### Just to check Invalid document status and error message in DB
# from app.db.session import SessionLocal
# from app.models.document import Document
# if __name__ == "__main__":
#     db = SessionLocal()
#     doc = db.query(Document).filter(Document.id == 11).first()
#     print(doc.status, doc.error_message)
    
from app.services.embeddings import collection
if __name__ == '__main__':
#     results = collection.get(limit=5, include=["documents", "metadatas"])
#     print(results)

    chunks = retrieve_relevant_chunks("What is covered in Phase 3?", document_id=15, top_k=20)
    for rank, c in enumerate(chunks, 1):
        if "Docker: images vs containers" in c["chunk_text"] or "GitHub Actions" in c["chunk_text"]:
            print(rank, round(c["distance"], 3), c["page_number"])