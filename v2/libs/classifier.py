import json

HIGH = 0.85
LOW  = 0.60

def classify_pairs(pairs: list[tuple], output_path="ambiguous.json"):
    auto_merge, auto_discard, ambiguous = [], [], []
    for r1, r2, score in pairs:
        if score >= HIGH:
            auto_merge.append((r1, r2, score))
        elif score <= LOW:
            auto_discard.append((r1, r2, score))
        else:
            ambiguous.append({"record_1": r1, "record_2": r2, "score": score})
    with open(output_path, "w") as f:
        json.dump(ambiguous, f, indent=2)
    return auto_merge, auto_discard, ambiguous
