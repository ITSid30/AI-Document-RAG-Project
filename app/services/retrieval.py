from app.services.embeddings import collection, embedding_model

def retrieve_relevant_chunks(question, document_id, top_k=3):
    # FILL: embed the question using embedding_model.encode(...).tolist()
    question_embedding = embedding_model.encode(question).tolist()
    # FILL: call collection.query()
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results= top_k,
        where= {"document_id": document_id} # <-- restricts search to THIS document only
    )
    
    # FILL: return the results in a clean, usable shape
    if results and "documents" in results and results["documents"]:
        combined_results = []
        
        documents = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []
        
        for doc, meta, dist in zip(documents, metadatas, distances):
            combined_results.append({
                "chunk_text": doc,
                "page_number": meta.get("page_number") if meta else None,
                "distance": dist
            })
        
        ### TO NOTE: In results - the chunk with least distance from 0 such as 0.67, 0.3 is appropriate than 1.18 distance
        return combined_results
    
    return []

### For Testing Purposes only...
if __name__ == "__main__":
    # result = retrieve_relevant_chunks("In what phase is Cloud and Kubernetes basics covered?", document_id=13, top_k=3)
    result = retrieve_relevant_chunks("Phase 3 Git Linux Docker CI/CD ?", document_id=13, top_k=3) ## Irrelevant question testing
    for r in result:
        print(r["page_number"], r["distance"], r["chunk_text"])