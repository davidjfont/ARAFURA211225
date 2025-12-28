import os
import yaml
from pathlib import Path
from typing import List, Dict, Optional

class RAGManager:
    def __init__(self, base_path: Path):
        self.rag_path = base_path / "core" / "rag"
        self.knowledge_base = {}
        self.load_all()

    def load_all(self):
        """Pre-loads metadata from all MD files for fast lookup."""
        self.knowledge_base = {
            "global": self._scan_dir(self.rag_path / "global"),
            "companies": self._scan_dir(self.rag_path / "companies"),
            "experiences": self._scan_dir(self.rag_path / "experiences")
        }

    def _scan_dir(self, directory: Path) -> List[Dict]:
        results = []
        if not directory.exists():
            return results
        
        for file in directory.rglob("*.md"):
            try:
                content = file.read_text(encoding='utf-8')
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1])
                        results.append({
                            "path": file,
                            "name": file.stem,
                            "metadata": metadata,
                            "content": parts[2].strip()
                        })
                else:
                    results.append({
                        "path": file,
                        "name": file.stem,
                        "metadata": {},
                        "content": content.strip()
                    })
            except Exception as e:
                print(f"[RAG] Error loading {file.name}: {e}")
        return results

    def query(self, context: str, limit: int = 5) -> str:
        """Score-based semantic query."""
        scored_docs = []
        context_lower = context.lower()
        keywords = set(context_lower.split())
        
        # Filter insignificant words (basic stop words)
        stop_words = {'y', 'de', 'el', 'la', 'en', 'un', 'una', 'qué', 'que', 'los', 'las', 'por', 'para', 'con', 'hola', 'revisa', 'tus', 'md', 'dime', 'si', 'hay', 'algo', 'sobre'}
        keywords = {kw for kw in keywords if kw not in stop_words and len(kw) > 2}

        if not keywords:
            return ""

        # Search across all categories
        for category in self.knowledge_base:
            for doc in self.knowledge_base[category]:
                score = 0
                
                # 1. Search in Content
                content_lower = doc['content'].lower()
                for kw in keywords:
                    if kw in content_lower:
                        score += 1
                
                # 2. Search in Name (Higher weight)
                name_lower = doc['name'].lower()
                for kw in keywords:
                    if kw in name_lower:
                        score += 3
                
                # 3. Search in Metadata (Higher weight)
                val_str = " ".join([str(v) for v in doc['metadata'].values()]).lower()
                for kw in keywords:
                    if kw in val_str:
                        score += 3
                
                # 4. Search in full Path (for folder names)
                path_str = str(doc['path']).lower()
                for kw in keywords:
                    if kw in path_str:
                        score += 2

                if score > 0:
                    scored_docs.append((score, doc))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        if not scored_docs:
            return ""

        # Format for prompt injection
        output = "### RAG KNOWLEDGE BASE INJECTION:\n"
        for score, doc in scored_docs[:limit]:
            meta = doc['metadata']
            conf = meta.get('confidence', 'unknown')
            output += f"#### Source: {doc['name']} (Match Score: {score} | Conf: {conf.upper()})\n"
            output += f"{doc['content']}\n\n"
        
        return output

    def check_conflict(self, rag_suggestion: str, visual_reality: str) -> Optional[str]:
        """Implements the Conflict Protocol."""
        # This is a conceptual check to be called by the orchestrator
        # logic: if they are semantically opposite, return explaining message
        return None # Placeholder for complex logic

    def archive_experience(self, category: str, content: str, metadata: Dict):
        """Saves a new experience to the MD RAG layer."""
        filename = f"exp_{os.urandom(4).hex()}.md"
        target = self.rag_path / "experiences" / filename
        
        yaml_header = yaml.dump(metadata, default_flow_style=False)
        md_content = f"---\n{yaml_header}---\n\n{content}"
        
        target.write_text(md_content, encoding='utf-8')
        self.load_all() # Refresh
        return target
