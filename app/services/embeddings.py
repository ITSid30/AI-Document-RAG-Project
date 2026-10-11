import chromadb
from sentence_transformers import SentenceTransformer

chroma_client = chromadb.PersistentClient(path="storage/chroma_db")
collection = chroma_client.get_or_create_collection(name="documents")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_and_store_chunks(chunks, document_id):
    for index, chunk in enumerate(chunks):
        # FILL: generate the embedding for chunk["chunk_text"]
        embedding = embedding_model.encode(chunk["chunk_text"]).tolist()
        # FILL: build the unique chunk_id using document_id and index
        chunk_id = f"{document_id}_chunk_{index}"
        
        # FILL: call collection.add(...)
        collection.add(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[chunk["chunk_text"]],
            metadatas=[{"document_id": document_id, "chunk_index": index, "page_number": chunk["page_number"]}]
        )
        pass
    