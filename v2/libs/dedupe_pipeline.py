import dedupe
import os
import pickle
from dedupe.variables import String, Exact

def define_fields():
    """Define fields for deduplication using Dedupe 3.0 syntax"""
    return [
        String('name', has_missing=True),
        String('address', has_missing=True)
    ]

def train_dedupe(records):
    fields = define_fields()
    # Convert list to dictionary with enumerated keys
    data = {i: record for i, record in enumerate(records)}
    
    # Initialize deduper with your fields
    deduper = dedupe.Dedupe(fields)
    
    # Now this will work
    sample = deduper.prepare_training(data, sample_size=15000)
    deduper.uncertain_pairs()
    
    # Label uncertain pairs interactively before training
    dedupe.console_label(deduper)
    deduper.train()

    return deduper


def run_dedupe(deduper, data: list[dict]):
    # Map records by ID for Dedupe API
    records = {rec['id']: rec for rec in data}
    # Use a fixed threshold for clustering duplicates (adjust threshold_value as needed)
    threshold_value = 0.5
    clustered = deduper.partition(records, threshold=threshold_value)
    pairs = []
    for record_ids, scores in clustered:
        for i in range(len(record_ids)):
            for j in range(i+1, len(record_ids)):
                r1, r2 = record_ids[i], record_ids[j]
                # Use threshold as a proxy score
                score = threshold_value
                pairs.append((records[r1], records[r2], score))
    return pairs

def dedupe_records(df):
    """Run deduplication process on dataframe"""
    
    fields = define_fields()
    deduper = dedupe.Dedupe(fields)
    
    # Convert DataFrame to dictionary for dedupe
    data_d = df.to_dict('index')
    
    # Train model
    deduper.prepare_training(data_d)
    
    return df

def train_model(deduper, data_d):
    """Train the deduplication model"""
    print('Starting active learning...')
    dedupe.console_label(deduper)
    deduper.train()
    print('Training complete')
