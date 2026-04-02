import math
from typing import List

class Vector:
    """First-principles vector for embeddings. Used in FAISS-flat search."""
    def __init__(self, data: List[float]):
        if not data:
            raise ValueError("Empty vector not allowed")
        self.data = data
        self.dim = len(data)
        # Pre-compute norm once at creation → O(d) amortized to O(1) per similarity
        self.norm = math.sqrt(sum(x * x for x in data))
        if self.norm == 0:
            self.norm = 1.0  # prevent div-by-zero

    def dot(self, other: 'Vector') -> float:
        """Dot product: core of cosine similarity. Time: O(d)"""
        if self.dim != other.dim:
            raise ValueError("Dimension mismatch")
        return sum(a * b for a, b in zip(self.data, other.data))

    def cosine_sim(self, other: 'Vector') -> float:
        """Cosine similarity = signal alignment in vector space.
        Physics: maximum projection overlap = minimum angle energy."""
        return self.dot(other) / (self.norm * other.norm)

    def to_list(self) -> List[float]:
        return self.data