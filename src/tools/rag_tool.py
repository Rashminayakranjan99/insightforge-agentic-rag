# src/tools/rag_tool.py
from ingestion.document_ingestor import DocumentIngestor
from core.vector import Vector
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import numpy as np

class RAGTool:
    """Production RAG tool – zero frameworks.
    Pipeline: query → embed → cosine search → return chunks + scores + metadata."""
    
    def __init__(self):
        # Reuse the exact ingestor you built on Day 1
        self.ingestor = DocumentIngestor()
        # Embedder: Siamese BERT with contrastive loss (384-dim). 
        # Internal: trained to push similar sentences closer in vector space.
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Core retrieval method.
        1. Embed query → O(d) time (d=384)
        2. Create Vector (pre-normalized)
        3. FAISS search (inner product = cosine because we normalized at ingest)
        4. Return structured results for Planner/Executor"""
        
        # Step 1: Embedding (what it does: turns text into 384-dim float vector)
        # Why: LLM cannot read raw text for similarity; must be in same vector space as chunks
        # Time: O(d) – single forward pass
        # System impact: Bottleneck if called 1000×/sec → we cache queries later with Redis
        q_emb = self.embedder.encode(query)
        
        # Step 2: Wrap in our first-principles Vector class (your Day-1 code)
        # Why: Forces us to understand cosine math instead of black-box sklearn
        q_vec = Vector(q_emb.tolist())
        
        # Step 3: FAISS search – uses IndexFlatIP (inner product)
        # Why IndexFlatIP: after normalization, dot product == cosine. Faster on CPU than cosine index.
        # Math: distances[i] = q · d_i (already cosine score)
        # Time complexity: O(n · d) worst case (flat scan). System impact: acceptable <50k chunks
        distances, indices = self.ingestor.index.search(
            np.array([q_emb], dtype=np.float32), top_k
        )
        
        # Step 4: Build clean JSON output for downstream agents
        # Edge case handled: if index empty or idx=-1 → skip
        results: List[Dict[str, Any]] = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            score = float(distances[0][i])   # already cosine (0.0 to 1.0)
            results.append({
                "score": score,
                "text": self.ingestor.chunks[idx],
                "metadata": self.ingestor.metadata[idx]
            })
        
        return results