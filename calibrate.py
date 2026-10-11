from app.services.retrieval import retrieve_relevant_chunks

DOC_ID = 14  # change to your clean document's id

relevant = [
    "What is covered in Phase 3?",
    "Which tools are used for containerization and CI/CD?",
    "What is the weekend project for the Spring Boot phase?",
    "Which AWS services should I learn?",
    "What resources are recommended for system design?",
    "How many weeks does the whole plan take?",
]

irrelevant = [
    "What is the capital of France?",
    "How do I bake a chocolate cake?",
    "Who won the 2018 football World Cup?",
    "What is the average salary of a Java developer?",
    "How do I learn to play the guitar?",
]

def best_distance(question):
    chunks = retrieve_relevant_chunks(question, document_id=DOC_ID, top_k=4)
    if not chunks:
        return None, None
    best = min(chunks, key=lambda c: c["distance"])
    return best["distance"], best["page_number"]

def run(label, questions):
    print(f"\n=== {label} ===")
    results = []
    for q in questions:
        dist, page = best_distance(q)
        results.append(dist)
        print(f"{dist:.3f}  (page {page})  {q}")
    return results

if __name__ == "__main__":
    rel = run("RELEVANT (should be answerable)", relevant)
    irr = run("IRRELEVANT (should be 'not found')", irrelevant)

    print("\n--- Summary ---")
    print(f"Relevant:   min={min(rel):.3f}  max={max(rel):.3f}")
    print(f"Irrelevant: min={min(irr):.3f}  max={max(irr):.3f}")
    if max(rel) < min(irr):
        print(f"Clean gap: a threshold between {max(rel):.3f} and {min(irr):.3f} works.")
    else:
        print("Groups overlap: no single threshold separates them.")