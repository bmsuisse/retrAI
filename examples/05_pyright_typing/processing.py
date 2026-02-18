"""Data processing module — full of type errors for pyright to catch."""

from __future__ import annotations

import json
from datetime import datetime


def parse_config(raw):
    """Parse a JSON config string."""
    data = json.loads(raw)
    host = data["host"]
    port = data["port"]
    timeout = data.get("timeout", 30)
    return {"host": host, "port": port, "timeout": timeout}


def process_records(records):
    """Process a list of records and return summaries."""
    results = []
    for record in records:
        name = record["name"]
        value = record["value"]
        if value > 100:
            status = "high"
        elif value > 50:
            status = "medium"
        else:
            status = "low"
        results.append({"name": name, "status": status, "processed_at": datetime.now()})
    return results


def merge_data(primary, secondary):
    """Merge two data sources by key."""
    merged = {}
    for item in primary:
        key = item["id"]
        merged[key] = item

    for item in secondary:
        key = item["id"]
        if key in merged:
            merged[key].update(item)
        else:
            merged[key] = item

    return list(merged.values())


class DataPipeline:
    """Simple ETL pipeline."""

    def __init__(self, source_path, output_path):
        self.source_path = source_path
        self.output_path = output_path
        self.transformations = []
        self.errors = []

    def add_transform(self, fn):
        self.transformations.append(fn)

    def run(self):
        with open(self.source_path) as f:
            data = json.load(f)

        for transform in self.transformations:
            data = transform(data)

        with open(self.output_path, "w") as f:
            json.dump(data, f)

        return {"records": len(data), "errors": self.errors}


def calculate_statistics(values):
    """Calculate basic statistics for a list of numbers."""
    if not values:
        return None

    total = sum(values)
    count = len(values)
    mean = total / count

    sorted_vals = sorted(values)
    mid = count // 2
    if count % 2 == 0:
        median = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    else:
        median = sorted_vals[mid]

    variance = sum((x - mean) ** 2 for x in values) / count
    std_dev = variance ** 0.5

    return {
        "mean": mean,
        "median": median,
        "std_dev": std_dev,
        "min": min(values),
        "max": max(values),
        "count": count,
    }


def validate_email(email):
    """Basic email validation."""
    if not isinstance(email, str):
        return False
    parts = email.split("@")
    if len(parts) != 2:
        return False
    local, domain = parts
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    return True


class Cache:
    """Simple in-memory cache with TTL."""

    def __init__(self, default_ttl=300):
        self._store = {}
        self._expiry = {}
        self.default_ttl = default_ttl

    def get(self, key):
        if key not in self._store:
            return None
        if datetime.now().timestamp() > self._expiry[key]:
            del self._store[key]
            del self._expiry[key]
            return None
        return self._store[key]

    def set(self, key, value, ttl=None):
        self._store[key] = value
        self._expiry[key] = datetime.now().timestamp() + (ttl or self.default_ttl)

    def clear(self):
        self._store.clear()
        self._expiry.clear()

    def size(self):
        return len(self._store)
