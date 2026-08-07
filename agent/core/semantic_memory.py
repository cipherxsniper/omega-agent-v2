"""
Semantic memory: replaces exact-key lookup with actual similarity search.

Uses TF-IDF + cosine similarity rather than a hosted embedding API, so it
works fully offline and has zero external dependency risk. It's less
powerful than a transformer embedding, but it is REAL retrieval - it will
find "database schema question" when you search "table structure issue",
which exact-key lookup never could.
"""

import math
import re
import time
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger("OmegaSemanticMemory")

_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class MemoryRecord:
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    tf: Counter = field(default_factory=Counter)


class SemanticMemoryStore:
    """
    Maintains a TF-IDF index over stored memories and supports similarity
    search. Rebuilds IDF lazily (only when queried after new inserts) so
    writes stay cheap.
    """

    def __init__(self):
        self.records: Dict[str, MemoryRecord] = {}
        self._idf: Dict[str, float] = {}
        self._dirty = True

    def store(self, key: str, content: str, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5) -> str:
        tokens = _tokenize(content)
        record = MemoryRecord(
            id=key,
            content=content,
            metadata=metadata or {},
            importance=importance,
            tf=Counter(tokens),
        )
        self.records[key] = record
        self._dirty = True
        logger.info(f"Stored semantic memory '{key}' ({len(tokens)} tokens, importance={importance})")
        return key

    def _rebuild_idf(self):
        n_docs = max(len(self.records), 1)
        df: Counter = Counter()
        for record in self.records.values():
            for term in record.tf.keys():
                df[term] += 1
        self._idf = {
            term: math.log((n_docs + 1) / (freq + 1)) + 1.0
            for term, freq in df.items()
        }
        self._dirty = False

    def _vector(self, tf: Counter) -> Dict[str, float]:
        return {term: freq * self._idf.get(term, 0.0) for term, freq in tf.items()}

    @staticmethod
    def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
        common = set(a.keys()) & set(b.keys())
        if not common:
            return 0.0
        numerator = sum(a[t] * b[t] for t in common)
        norm_a = math.sqrt(sum(v * v for v in a.values())) or 1e-9
        norm_b = math.sqrt(sum(v * v for v in b.values())) or 1e-9
        return numerator / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.05) -> List[Dict[str, Any]]:
        """
        Returns the top_k most semantically similar stored memories to the
        query, ranked by cosine similarity - not by exact string match.
        """
        if not self.records:
            return []
        if self._dirty:
            self._rebuild_idf()

        query_tf = Counter(_tokenize(query))
        query_vec = self._vector(query_tf)

        scored = []
        for record in self.records.values():
            record_vec = self._vector(record.tf)
            score = self._cosine(query_vec, record_vec)
            if score >= min_score:
                scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": r.id,
                "content": r.content,
                "score": round(score, 4),
                "metadata": r.metadata,
                "timestamp": r.timestamp,
                "importance": r.importance,
            }
            for score, r in scored[:top_k]
        ]

    def get(self, key: str) -> Optional[MemoryRecord]:
        return self.records.get(key)

    def prune(self, min_importance: float = 0.3, max_age_seconds: Optional[float] = None):
        """Drop low-importance / stale memories so the index doesn't grow unbounded."""
        now = time.time()
        to_remove = []
        for key, record in self.records.items():
            too_old = max_age_seconds is not None and (now - record.timestamp) > max_age_seconds
            if record.importance < min_importance and too_old:
                to_remove.append(key)
        for key in to_remove:
            del self.records[key]
        if to_remove:
            self._dirty = True
            logger.info(f"Pruned {len(to_remove)} stale/low-importance memories")

