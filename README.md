# Contractor Entity Resolution

This project shows how to collapse messy contractor records (company + address)
into unique “canonical entities” using **Python, libpostal, and fuzzy
matching** inside Docker.

---

## 1  Problem

Given a CSV with **PartyName** and **Address**, create a single `entity_id`
per real-world business even when:

* Names differ by punctuation, “&” vs “and”, corporate suffixes, etc.
* Addresses mix abbreviations and full words
  (*“E Oak St.”* vs *“East Oak Street”*), reorder components, or add / drop
  country tokens.

---

## 2  Key Challenges & Fixes

| # | Issue                                                        | Fix                                                                                                             |
| - | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| 1 | Punctuation & suffix noise                                   | `normalize_name()` strips `& . , -`, collapses spaced letters (“L L C”), drops suffixes (LLC, Inc, Corp). |
| 2 | Stop-words keep*“Alpha & Omega”* vs*“Alpha Omega”* apart | Filter a small set `{and, the, of}`.                                                                          |
| 3 | libpostal splits road into prefix / base / type              | Merge `road_prefix` + `road` + `road_type` back together.                                                 |
| 4 | Leading directions (“E/N…”) cause mismatches              | Strip a leading direction token during road normalisation.                                                      |
| 5 | “St.” expands to “saint”                                 | Map `"saint" → "street"` in `ROAD_TYPES`.                                                                  |
| 6 | One record lacks road type, similarity drops                 | Lower `ADDR_THR` from 85 → 75 after robust normalisation.                                                    |
| 7 | Greedy one-pass clustering not transitive                    | Adopt**union-find** (disjoint-set) clustering.                                                            |
| 8 | Needed insight into stubborn duplicates                      | Added temporary debug print for PartyIds 14 & 15.                                                               |

---

## 3  Pipeline

sample.csv ──▶ main.py

├─ normalize_name() **    **─▶ fuzz.token_sort_ratio

├─ canonical_address()**  **─▶ fuzz.token_sort_ratio

└─ union-find **          **─▶ entity_id

└─ longest name + longest address

* **Name normalisation:** lower-case → “&”→“and” → collapse spaced letters →
  strip punctuation → drop suffixes → remove stop-words.
* **Address:** `expand_address` → `parse_address` → merge prefix/type →
  state→abbr → strip leading direction → expand road-type tokens →
  assemble `house road unit city state postcode`.
* **Similarity rule:**`NAME_THR = 85`, `ADDR_THR = 75`; if both scores clear the bar, rows merge.
* **Union-find** guarantees transitivity.

---

## **5 Next Steps**

* Replace **fuzzywuzzy → rapidfuzz** for LGPL-free speed.
* Persist results to a database instead of console print.
* Add unit tests for each normalisation step.
* Make thresholds & stop-word list configurable.
* Switch to probabilistic deduping (**dedupe** library) for very noisy data.

## **6 A very robust solution for noisy and huge datasets - dedupe**

When I rely on hard-threshold fuzzy matching, I’m forced to pick a single cut-off—say a token-sort score of 85 percent—and hope it fits every case. By switching to the open-source **dedupe** library, I let the model learn the optimal weights for each field from a handful of examples I label myself. After that, it uses smart blocking and clustering so I can scale the deduplication to millions of records without constantly tuning those thresholds.

```
import dedupe, csv, pandas as pd

# 1. Read data ---------------------------------------------------------
df = pd.read_csv("sample.csv")
records = df.to_dict(orient="index")         # {rowID: {field: value}}

# 2. Tell dedupe about each field -------------------------------------
fields = [
    {"field" : "PartyName", "type": "String"},
    {"field" : "Address",   "type": "String"},
    {"field" : "PartyId",   "type": "Categorical", "has_missing": True},
]

deduper = dedupe.Dedupe(fields)

# 3. Sample + label ----------------------------------------------------
deduper.sample(records, 15000)  # draw candidate pairs

# This line starts an interactive console session that shows pairs and
# asks y/n/?    (there’s also a simple Flask/Streamlit web UI)
dedupe.console_label(deduper)

deduper.train()                 # learns weights & blocking rules
deduper.write_training("training.json")
settings = deduper.write_settings("dedupe_settings")

# 4. Blocking + clustering --------------------------------------------
threshold = deduper.threshold(records, recall_weight=2.0)  # auto
clustered, scores = deduper.match(records, threshold)

# 5. Assign entity_id --------------------------------------------------
for cluster_id, (row_ids, score) in enumerate(clustered):
    df.loc[row_ids, "entity_id"] = f"entity_{cluster_id}"

df.to_csv("canonical.csv", index=False)
```

*(Once you have **training.json** and **dedupe_settings**, you can skip the*

*label-and-train step on future runs.)*

## **7 How to run this project**

```
docker buildx build --platform=linux/amd64 -t contractor-resolver:latest --load .
docker run --rm -it contractor-resolver:latest   
```
