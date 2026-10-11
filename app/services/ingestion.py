
from pypdf import PdfReader
import unicodedata

from app.config import MAX_PAGES

def extract_text_by_page(file_path):
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        raise ValueError(f"Unable to open PDF file. It may be corrupted or encrypted.") from e

    if len(reader.pages) > MAX_PAGES:
        raise ValueError(f"Document has {len(reader.pages)} pages; the maximum is {MAX_PAGES}.")
    pages_data = []
    
    for index, page in enumerate(reader.pages):
        extracted_text = unicodedata.normalize("NFKC", page.extract_text() or "")
        cleaned_text = extracted_text.split()
        
        is_scanned = len(cleaned_text) < 20
        
        pages_data.append(
            {
                "page_number": index + 1,
                "text": extracted_text,
                "is_scanned": is_scanned
            }
        )

    # after processing all pages, check: did EVERY page come back empty?
    if all(page["is_scanned"] for page in pages_data):
        raise ValueError("Document contains no extractable text across all pages. It might be scanned or image-only.")

    return pages_data
    
def chunk_text(pages, chunk_size=300, overlap=50):
    if(overlap >= chunk_size):
        raise ValueError("Chunk size must be strictly greater than overlap to avoid infinite loops")
    
    all_chunks = []
    step = chunk_size - overlap
    
    for page in pages:
        words = page["text"].split()
        
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            chunk_str = " ".join(chunk_words)
            
            all_chunks.append({
                "chunk_text": chunk_str,
                "page_number": page["page_number"]
            })
            
            if end >= len(words):
                break
            
            start += step
    
    return all_chunks

#### This is used to manually test any uploaded file for Checking extraction and chunking capability
# if __name__ == '__main__':
#     # pages = extract_text_by_page("storage/uploads/fullstack-java-springboot-study-plan.md.pdf_6")
#     pages = extract_text_by_page("storage/uploads/Music page (1).pdf_4")
#     chunks = chunk_text(pages, chunk_size=300, overlap=50)
#     print(f"Total Pages: {len(pages)}")
#     print(f"Total chunks: {len(chunks)}")
#     print(chunks[0]) # inspect first chunk
#     print(chunks[-1]) # inspect last chunk

from app.db.session import SessionLocal
from app.models.document import Document

db = SessionLocal()
for i in (3, 8):
    d = db.query(Document).filter(Document.id == i).first()
    print(i, d.status, d.error_message)
db.close()