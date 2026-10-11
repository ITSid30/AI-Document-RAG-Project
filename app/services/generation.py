import ollama

SYSTEM_PROMPT = (
    "You answer questions using ONLY the provided context. "
    "If the answer is not in the context, reply exactly: "
    "\"I don't know based on the provided document.\" "
    "Do not use outside knowledge. Answer concisely, and do not repeat the question."
)

SUMMARY_SYSTEM_PROMPT = (
    "You summarize documents. Write a 3-4 sentence summary using ONLY the "
    "provided text. Do not add outside knowledge. Do not repeat the instructions."
)

def generate_answer(question, context_chunks, model="phi3"):
    # FILL: build a prompt string combining the question and the context_chunks' text
    
    context_text = "\n\n".join([chunk["chunk_text"] for chunk in context_chunks])
    
    user_message = f"Context:\n{context_text}\n\nQuestion: {question}"
    
    response = ollama.chat(model=model, messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
        ],
        options={
            "temperature": 0.0
        })
    # FILL: extract and return just the answer text from the response
    return response["message"]["content"]

def generate_summary(chunks, model="phi3"):
    text = "\n\n".join(c["chunk_text"] for c in chunks[:3])
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Text:\n{text}\n\nSummary:"}
        ],
        options={"temperature": 0},
    )
    
    return response["message"]["content"]



#### Testing code
from app.services.retrieval import retrieve_relevant_chunks

if __name__ == "__main__": 
    chunks = retrieve_relevant_chunks("What is Phase 3 about?", document_id=14, top_k=3)
    answer = generate_answer("What is Phase 3 about?", chunks)
    print("Answer: " + answer)