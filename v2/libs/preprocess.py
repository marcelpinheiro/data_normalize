import re
from unidecode import unidecode
import postal.parser

def normalize_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = unidecode(text)
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def parse_address(address: str) -> str:
    parsed = postal.parser.parse_address(address or "")
    components = {comp: value for value, comp in parsed}
    street = components.get("road", "")
    house = components.get("house_number", "")
    city = components.get("city", "")
    return normalize_text(f"{house} {street} {city}")
