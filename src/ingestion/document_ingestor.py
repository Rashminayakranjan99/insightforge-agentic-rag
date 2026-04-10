from sentence_transformers import SentenceTransformer
from core.vector import Vector
import faiss
import numpy as np
from typing import List, Tuple

class DocumentIngestor:
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim, explain: contrastive Siamese BERT
        self.index = None
        self.chunks: List[str] = []
        self.metadata: List[dict] = []
    
    def ingest(self, text: str, source: str):
        # Semantic chunking (simple version first)
        sentences = text.split('. ')
        embeddings = self.embedder.encode(sentences)
        
        for i, emb in enumerate(embeddings):
            vec = Vector(emb.tolist())
            if self.index is None:
                self.index = faiss.IndexFlatIP(384)  # Inner Product = cosine after normalization
            self.index.add(np.array([emb], dtype=np.float32))
            
            self.chunks.append(sentences[i])
            self.metadata.append({"source": source, "chunk_idx": i})
