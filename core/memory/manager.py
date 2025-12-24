import json
from pathlib import Path
from datetime import datetime

class MemoryManager:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.sessions_dir = base_path / "sessions"
        self.memory_dir = base_path / "core" / "memory"
        self.sessions_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.current_log = []
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.evolution_file = self.memory_dir / "evolution.jsonl"
        
        # Load evolution history (optional)
        self.evolution_summary = []
        # self._load_evolution()

    def log(self, role: str, content: str):
        """Append entry to current session file"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }
        self.current_log.append(entry)
        try:
            # Daily Session File
            date_str = datetime.now().strftime('%Y-%m-%d')
            path = self.sessions_dir / f"session_{date_str}.jsonl"
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Memory Error] Logging failed: {e}")

    def get_recent_history(self, limit=10):
        # Could be used to cold-start context_history
        return self.current_log[-limit:]
