from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

# Modelo de embeddings
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

d = embed_model.get_sentence_embedding_dimension()
faiss_index = faiss.IndexFlatL2(d)
store = {}


def upsert_to_vector_db(records: list[dict]):
    vectors = []
    ids = []
    for rec in records:
        text = f"{rec['name']} {rec.get('address','')}"
        vec = embed_model.encode(text)
        ids.append(rec['id'])
        vectors.append(vec)
        store[rec['id']] = rec
    vectors = np.vstack(vectors).astype('float32')
    faiss_index.add(vectors)
    return ids


def query_similar(record, top_k=5):
    text = f"{record['name']} {record.get('address','')}"
    vec = embed_model.encode(text).astype('float32')
    distances, indices = faiss_index.search(np.expand_dims(vec,0), top_k)
    results = []
    for idx in indices[0]:
        rid = list(store.keys())[idx]
        results.append(store[rid])
    return results

# Modelo LLM open-source (ex: t5-small)
tokenizer = AutoTokenizer.from_pretrained("t5-small")
model = AutoModelForSeq2SeqLM.from_pretrained("t5-small")
classifier = pipeline("text2text-generation", model=model, tokenizer=tokenizer)


def decide_with_llm(pair: dict) -> bool:
    prompt = (
        f"Registro A: {pair['record_1']}\n"
        f"Registro B: {pair['record_2']}\n"
        "Eles representam a mesma entidade? Responda apenas 'sim' ou 'nao'."
    )
    resp = classifier(prompt, max_length=10)[0]['generated_text']
    return resp.lower().strip().startswith("sim")
