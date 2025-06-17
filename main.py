#!/usr/bin/env python3
import sys
import os
import re
import pandas as pd
from postal.parser import parse_address
from postal.expand import expand_address
from fuzzywuzzy import fuzz  

# --------------------------------------------------------------------------- #
# 1. Company‑name normalisation
# --------------------------------------------------------------------------- #
SUFFIX_RE = re.compile(
    r"\b(llc|l\.l\.c|l\s+l\s+c|inc|corporation|corp|co|company|ltd|plc|construction|const)\b",
    flags=re.IGNORECASE,
)
PUNCT_RE = re.compile(r"[&\-\.,]")
SPACED_ABBR_RE_3 = re.compile(r"\b([a-z])\s+([a-z])\s+([a-z])\b", re.I)
SPACED_ABBR_RE_2 = re.compile(r"\b([a-z])\s+([a-z])\b", re.I)
STOPWORDS = {"and", "the", "of"}


def normalize_name(name: str) -> str:
    """Return canonical form of a company name for fuzzy matching."""
    s = (name or "").lower().replace("&", " and ")
    s = SPACED_ABBR_RE_3.sub(lambda m: "".join(m.groups()), s)
    s = SPACED_ABBR_RE_2.sub(lambda m: "".join(m.groups()), s)
    s = PUNCT_RE.sub(" ", s)
    s = SUFFIX_RE.sub("", s)
    tokens = [tok for tok in s.split() if tok not in STOPWORDS]
    return " ".join(tokens)

# --------------------------------------------------------------------------- #
# 2. Address canonicalisation (component‑level, direction‑agnostic)
# --------------------------------------------------------------------------- #
COMPONENT_ORDER = ["house_number", "road", "unit", "city", "state", "postcode"]
NON_ALNUM = re.compile(r"[^a-z0-9 ]")
STATE_ABBR = {
    "alabama": "al",
    "alaska": "ak",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "district of columbia": "dc",
    "florida": "fl",
    "georgia": "ga",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}
DIR_TOKENS = {"n", "s", "e", "w", "north", "south", "east", "west"}
# normalise common road‑type abbreviations *and* libpostal expansions
ROAD_TYPES = {
    "st": "street",
    "street": "street",      # ensure “street” stays as canonical form
    "saint": "street",       # libpostal sometimes expands “St.” → “saint”
    "ave": "avenue",
    "av": "avenue",
    "boulevard": "boulevard",
    "blvd": "boulevard",
    "rd": "road",
    "road": "road",
}


def canonical_address(address: str) -> str:
    """Return a canonical single‑string address suitable for fuzzy matching."""
    src = address or ""
    # 1  Expand abbreviations (libpostal)
    try:
        expanded = expand_address(src)[0]
    except Exception:
        expanded = src
    expanded = expanded.lower()

    # 2  Parse into components
    comps = {comp: val.lower() for val, comp in parse_address(expanded)}

    # 3  Merge road_prefix + road + road_type into one field
    prefix = comps.pop("road_prefix", "")
    road_type = comps.pop("road_type", "")
    road = comps.get("road", "")
    if prefix and prefix not in road.split():
        road = f"{prefix} {road}".strip()
    if road_type and road_type not in road.split():
        road = f"{road} {road_type}".strip()
    comps["road"] = road

    # 4  State → 2‑letter code if spelled out
    st = comps.get("state", "")
    comps["state"] = STATE_ABBR.get(st, st)

    # 5  Token‑level normalisation of road: drop leading directional, expand type tokens
    tokens = comps["road"].split()
    if tokens and tokens[0] in DIR_TOKENS:
        tokens = tokens[1:]  # remove leading direction
    tokens = [ROAD_TYPES.get(t, t) for t in tokens if t not in DIR_TOKENS]
    comps["road"] = " ".join(tokens)

    # 6  Assemble canonical string in fixed order
    parts: list[str] = []
    for key in COMPONENT_ORDER:
        val = NON_ALNUM.sub(" ", comps.get(key, "")).strip()
        if val:
            parts.append(val)
    return " ".join(parts)

# --------------------------------------------------------------------------- #
# 3. Disjoint‑set helpers
# --------------------------------------------------------------------------- #

def _find(i: int, parent: list[int]) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _union(i: int, j: int, parent: list[int]):
    ri, rj = _find(i, parent), _find(j, parent)
    if ri != rj:
        parent[rj] = ri

# --------------------------------------------------------------------------- #
# 4. Entity resolution workflow
# --------------------------------------------------------------------------- #
NAME_THR = int(os.getenv("NAME_THRESHOLD", 85))
ADDR_THR = int(os.getenv("ADDR_THRESHOLD", 75))  # 80 → 75 to allow minor token differences


def resolve_entities(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["norm_name"] = df["PartyName"].apply(normalize_name)
    df["norm_addr"] = df["Address"].apply(canonical_address)

    n = len(df)
    parent = list(range(n))

    for i in range(n):
        for j in range(i + 1, n):
            if parent[j] == parent[i]:
                continue
            # ---- DEBUG: print similarity for Alpha & Omega rows ----
            if set(df.loc[[i, j], "PartyId"]).issuperset({14, 15}):
                name_score = fuzz.token_sort_ratio(df.at[i, "norm_name"], df.at[j, "norm_name"])
                addr_score = fuzz.token_sort_ratio(df.at[i, "norm_addr"], df.at[j, "norm_addr"])
                print(
                    f"DEBUG comparison PartyId {df.at[i,'PartyId']} vs {df.at[j,'PartyId']}: "
                    f"name_score={name_score}, addr_score={addr_score}\n"
                    f"  name_i='{df.at[i,'norm_name']}'\n  name_j='{df.at[j,'norm_name']}'\n"
                    f"  addr_i='{df.at[i,'norm_addr']}'\n  addr_j='{df.at[j,'norm_addr']}'"
                )
            else:
                name_score = fuzz.token_sort_ratio(df.at[i, "norm_name"], df.at[j, "norm_name"])
                addr_score = fuzz.token_sort_ratio(df.at[i, "norm_addr"], df.at[j, "norm_addr"])
            if name_score >= NAME_THR and addr_score >= ADDR_THR:
                _union(i, j, parent)

    df["entity_id"] = [f"entity_{_find(i, parent)}" for i in range(n)]

    canonical = (
        df.groupby("entity_id", as_index=False)
        .agg(
            PartyId=("PartyId", "first"),
            PartyName=("PartyName", lambda x: max(x, key=len)),
            Address=("Address", lambda x: max(x, key=len)),
        )
        .sort_values("PartyId")
    )
    return canonical

# --------------------------------------------------------------------------- #
# 5. CLI entry point (for Docker CMD)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    csv_path = os.getenv("CSV_PATH", "sample.csv")
    if not os.path.isfile(csv_path):
        print(f"ERROR: CSV path '{csv_path}' not found", file=sys.stderr)
        sys.exit(1)
    result = resolve_entities(csv_path)
    print("\nCanonical entities:")
    print(result.to_string(index=False))
