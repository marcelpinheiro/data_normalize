import os
import json
import pandas as pd
import numpy as np

# add libs/ to path if the script is at the project root
env_libs = os.path.join(os.path.dirname(__file__), 'libs')
if os.path.isdir(env_libs):
        import sys; sys.path.append(env_libs)

from preprocess import normalize_text, parse_address
from dedupe_pipeline import train_dedupe, run_dedupe
from classifier import classify_pairs
from rag_llm import upsert_to_vector_db, decide_with_llm


def main(input_file):
        # 1. Read
        df = pd.read_json(input_file, compression='gzip', lines=True)
        # Keep only non blank/null values in the relevant columns
        df = (df.replace('', np.nan).dropna(how='any'))

        df = df.assign(
                id = df.business_id,
                name = df.name.str.lower(),
                address = (df.address + ", " + df.city + ", " + df.state + " " + df.postal_code)
        )[['id','name','address']]

        # 2. Preprocessing
        records = []
        for _, row in df.iterrows():
                rec = {
                        'id': row['id'],  
                        'name': normalize_text(row['name']),  
                        'address': parse_address(row['address'])  
                }
                records.append(rec)

        # 3. Deduplication
        deduper = train_dedupe(records)
        pairs = run_dedupe(deduper, records)

        # 4. Classification
        auto_merge, auto_discard, ambiguous = classify_pairs(pairs)

        # save merge and discard
        merge_list = [
                {'record_1': r1, 'record_2': r2, 'score': score}
                for r1, r2, score in auto_merge
        ]
        discard_list = [
                {'record_1': r1, 'record_2': r2, 'score': score}
                for r1, r2, score in auto_discard
        ]
        with open('merge.json', 'w', encoding='utf-8') as f:
                json.dump(merge_list, f, ensure_ascii=False, indent=2)
        with open('discard.json', 'w', encoding='utf-8') as f:
                json.dump(discard_list, f, ensure_ascii=False, indent=2)

        # 5. Upsert to FAISS (all records) for vector search
        upsert_to_vector_db(records)

        # contextual analysis with local model
        decisions = []
        for pair in ambiguous:
                merge_decision = decide_with_llm(pair)
                decisions.append({
                        'record_1': pair['record_1'],
                        'record_2': pair['record_2'],
                        'score': pair['score'],
                        'merge': merge_decision
                })
        with open('final_decisions.json', 'w', encoding='utf-8') as f:
                json.dump(decisions, f, ensure_ascii=False, indent=2)

        print("Pipeline completed! Files generated: merge.json, discard.json, final_decisions.json")


if __name__ == '__main__':
        main('./v2/data/yelp_academic_dataset_business.json.gz')

