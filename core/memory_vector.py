import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# Optional dependencies for high-performance vector search
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    VECTOR_DEPS_OK = True
except ImportError:
    VECTOR_DEPS_OK = False

class VectorMemory:
    """
    ARAFURA v4.0 - Simple Vector Memory
    Implements:
    - Semantic storage of experiences
    - Fast retrieval using FAISS (or keyword fallback)
    - Experience categorization (Visual, Logic, Error)
    """
    def __init__(self, base_path: Path):
        self.memory_dir = base_path / "core" / "memory" / "vectors"
        self.snapshots_dir = self.memory_dir / "snapshots"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(exist_ok=True)
        self.db_path = self.memory_dir / "experience_db.json"
        
        self.experiences = self._load_db()
        self.last_id = "000000" # Trace for UI
        
        # Load embedding model if possible
        if VECTOR_DEPS_OK:
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2') # Good for Spanish/English
            self.index = self._build_index()
        else:
            self.model = None
            self.index = None

    def _load_db(self):
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding='utf-8'))
            except:
                return []
        return []

    def _save_db(self):
        self.db_path.write_text(json.dumps(self.experiences, indent=2, ensure_ascii=False), encoding='utf-8')

    def _build_index(self):
        if not self.experiences or not VECTOR_DEPS_OK:
            return None
        
        embeddings = [exp['embedding'] for exp in self.experiences]
        dim = len(embeddings[0])
        index = faiss.IndexFlatL2(dim)
        index.add(np.array(embeddings).astype('float32'))
        return index

    def store_experience(self, category: str, observation: str, action: str, outcome: str, image_pil=None):
        """Stores a new learning unit, optionally with a visual snapshot"""
        embedding = None
        image_relative_path = None
        
        # 1. Save Image if provided
        if image_pil:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            image_name = f"snap_{timestamp_str}.png"
            image_path = self.snapshots_dir / image_name
            image_pil.save(image_path)
            image_relative_path = f"snapshots/{image_name}"

        # 2. Embedding
        if VECTOR_DEPS_OK and self.model:
            embedding = self.model.encode(observation).tolist()

        exp = {
            "timestamp": datetime.now().isoformat(),
            "category": category, # "visual", "logic", "error"
            "observation": observation,
            "action": action,
            "outcome": outcome,
            "embedding": embedding,
            "id": datetime.now().strftime("%f"), # Unique ID for trace
            "image": image_relative_path
        }
        
        self.last_id = exp["id"]
        
        self.experiences.append(exp)
        self._save_db()
        
        # Rebuild index for real-time retrieval if needed
        if VECTOR_DEPS_OK:
            self.index = self._build_index()

    def query_experience(self, query_text: str, limit=3):
        """Retrieves similar past experiences to build context"""
        if not self.experiences:
            return []

        if VECTOR_DEPS_OK and self.index and self.model:
            # Semantic search
            query_vector = self.model.encode(query_text).astype('float32').reshape(1, -1)
            D, I = self.index.search(query_vector, min(limit, len(self.experiences)))
            
            results = []
            for idx in I[0]:
                if idx != -1:
                    exp = self.experiences[idx].copy()
                    exp.pop('embedding', None)
                    self.last_id = exp.get("id", "000000")
                    results.append(exp)
            return results
        else:
            # Simple keyword fallback
            results = []
            query_words = set(query_text.lower().split())
            for exp in sorted(self.experiences, key=lambda x: x['timestamp'], reverse=True):
                obs_words = set(exp['observation'].lower().split())
                if query_words.intersection(obs_words):
                    e = exp.copy()
                    e.pop('embedding', None)
                    results.append(e)
                    if len(results) >= limit: break
            return results

if __name__ == "__main__":
    # Test
    base = Path(__file__).parent.parent.parent
    vm = VectorMemory(base)
    vm.store_experience("visual", "Botón Comprar detectado en verde", "click x? y?", "Éxito: Operación abierta")
    print(f"Query Result: {vm.query_experience('¿Qué hacer si veo un botón verde?')}")
