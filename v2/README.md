# **Fuzzy Address Deduplication Pipeline**

This project provides a complete pipeline for deduplicating a large, fuzzy address [database](https://www.kaggle.com/datasets/yelp-dataset/yelp-dataset) from **yelp** using a combination of probabilistic record linkage (**dedupe**), rule-based classification, and a local RAG-style LLM for ambiguous cases.

---

## **Table of Contents**

1. [Overview](#overview)
2. [Prerequisites &amp; Installation](#prerequisites--installation)
3. [Project Structure](#project-structure)
4. [Pipeline Steps](#pipeline-steps)
   1. [Data Ingestion](#1-data-ingestion)
   2. [Preprocessing](#2-preprocessing)
   3. [Probabilistic Deduplication](#3-probabilistic-deduplication)
   4. [Automatic Classification](#4-automatic-classification)
   5. [Vector Database Upsert](#5-vector-database-upsert)
   6. [Contextual LLM Decisioning](#6-contextual-llm-decisioning)
5. [Modules Explained](#modules-explained)
6. [Configuration &amp; Customization](#configuration--customization)
7. [Outputs](#outputs)
8. [Tips &amp; Further Improvements](#tips--further-improvements)

---

## **Overview**

Addresses (and other “dirty” entities) rarely match exactly. This pipeline:

* **Normalizes** raw text to reduce variation
* **Clusters** likely duplicates with a probabilistic model (**dedupe**)
* **Auto-resolves** clear cases, flags ambiguous ones
* **Embeds** all records into a FAISS index for fast similarity lookups
* **Runs** a lightweight local LLM to resolve the toughest edge cases

The result is a small set of manual decisions, and three JSON files:

* **merge.json** — pairs to automatically merge
* **discard.json** — pairs to discard
* **final_decisions.json** — LLM-verified decisions on ambiguous pairs

---

## **Prerequisites & Installation**

```
pip install -r requirements.txt
```

*(You may need system packages for **libpostal** first: see https://github.com/openvenues/libpostal.)*

---

## **Project Structure**

```
├── preprocess.py         # Text and address normalization functions
├── dedupe_pipeline.py    # Model definition, training, and dedupe execution
├── classifier.py         # Rule-based auto-merge / auto-discard / ambiguous split
├── rag_llm.py            # FAISS vector store + local LLM decision function
└── run_pipeline.py       # Orchestrates the full end-to-end flow
```

---

## **Pipeline Steps**

### **1. Data Ingestion**

**In **run_pipeline.py**:**

* **Read** input JSON/GZIP file (**pandas.read_json**)
* **Filter** out blank/null rows
* **Select** & **rename** columns to a minimal format: **id**, **name**, **address**

*Why:* Focus on the essential fields reduces memory usage and noise.

### **2. Preprocessing**

**In **preprocess.py**:**

* normalize_text(text)**:**
  * Lowercases, strips accents (via **unidecode**), removes punctuation
  * Collapses whitespace
* parse_address(address)**:**
  * **Uses **postal.parser** to extract **house_number**, **road**, **city
  * Normalizes that combination into a consistent string

*Why:* Uniform tokens vastly improve both blocking and probabilistic matching.

### **3. Probabilistic Deduplication**

**In **dedupe_pipeline.py**:**

* **define_fields()** declares which record fields to compare (**name**, **address**).
* train_dedupe(records)**:**
  1. Converts records into Dedupe’s internal format
  2. Launches an **interactive labeling** session (**dedupe.console_label**) (optional—you can load a saved training file instead)
  3. Trains a **deduper** model
  4. Returns the trained model
* run_dedupe(deduper, records)**:**
  * Partitions the dataset into clusters using a fixed threshold
  * Produces a flat list of record‐pair + similarity scores

*Why:* Probabilistic linkage handles typographical errors, abbreviations, and missing data gracefully.

### **4. Automatic Classification**

**In **classifier.py**:**

* Defines two thresholds: **HIGH = 0.85**, **LOW = 0.60**.
* classify_pairs(pairs)** splits into:**
  * **Auto-merge** (score >= HIGH**)**
  * **Auto-discard** (**score <= LOW**)
  * **Ambiguous** (everything in between)
* Writes **ambiguous.json** for transparency, returns all three lists

*Why:* Auto-resolving clear cases reduces the workload on the LLM step.

### **5. Vector Database Upsert**

**In **rag_llm.py**:**

* Loads a sentence-transformer (**all-MiniLM-L6-v2**) for embeddings
* **Initializes a FAISS index with dimension **d = embed_model.get_sentence_embedding_dimension()
* upsert_to_vector_db(records)**:**
  1. Encodes each record’s combined **name + address**
  2. Adds resulting vectors to the FAISS index
  3. Stores raw record data in an in-memory map for retrieval

*Why:* Having all records in a vector store lets you retrieve nearest neighbors instantly—useful for any downstream analysis.

### **6. Contextual LLM Decisioning**

**Also in **rag_llm.py**:**

* Loads a small Seq2Seq model (**t5-small**) via Huggingface’s **pipeline**
* decide_with_llm(pair)**:**
  1. Formats a prompt showing both records
  2. Asks “Eles representam a mesma entidade? Responda apenas ‘sim’ ou ‘nao’.“
  3. Returns **True** for “sim”, **False** otherwise
* For each **ambiguous** pair, runs this decisioner and builds **final_decisions.json**

*Why:* A local LLM can often capture subtle context (e.g. business names in the same building) better than simple rules.

---

## **Configuration & Customization**

* **Thresholds:** Adjust **HIGH**/**LOW** in **classifier.py** to change sensitivity.
* **Dedupe threshold:** Tweak threshold_value** in **run_dedupe**.**
* **Blocking:** Add custom blocks in **dedupe_pipeline.py** (e.g. by ZIP code) to speed training and reduce pair candidates.
* **Model persistence:** Integrate **pickle** saves in **train_dedupe**, then load via **dedupe.StaticDedupe** to skip interactive labeling.

---

## **Outputs**

After running:

```
python run_pipeline.py
```

You’ll get:

* **merge.json** — high-confidence merges
* **discard.json** — high-confidence non-matches
* **ambiguous.json** — all mid-score pairs
* **final_decisions.json** — LLM-scored decisions for all ambiguous

---

## **Tips & Further Improvements**

* **Integrate a true RAG store:** Persist FAISS + metadata to disk or a service like Weaviate.
* **Enhanced blocking:** Use **libpostal**’s canonical components (e.g. **postcode**) to create more precise candidate sets.
* **Hybrid human-in-the-loop:** For ambiguous pairs, write them to a simple HTML form for human review instead of LLM.
* **Scaling:** For very large datasets, sample per-block and train multiple local Dedupe models in parallel.

---

Happy deduplicating! 🚀
