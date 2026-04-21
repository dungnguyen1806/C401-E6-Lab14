import json
import re
from pathlib import Path
from typing import Dict, List


class FileRetriever:
    """
    Lightweight retriever for JSON knowledge base.
    It ranks chunks by keyword overlap between question and chunk text.
    """

    def __init__(self, kb_path: str = "data/knowledge_base.json"):
        self.kb_path = Path(kb_path)
        self.chunks = self._load_kb()

    def _load_kb(self) -> List[Dict[str, str]]:
        if not self.kb_path.exists():
            return []
        with self.kb_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def retrieve(self, question: str, top_k: int = 3) -> List[Dict[str, str]]:
        q_tokens = set(self._tokenize(question))
        if not self.chunks:
            return []

        scored = []
        for idx, chunk in enumerate(self.chunks):
            chunk_text = chunk.get("text", "")
            chunk_tokens = set(self._tokenize(chunk_text))
            overlap = len(q_tokens.intersection(chunk_tokens))
            scored.append((overlap, idx, chunk))

        # Sort by overlap desc, then by original order for stable tie-break.
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in scored[:top_k]]
