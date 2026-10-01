from typing import List, Dict, Any

class RecursiveTextChunker:
    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        chunks: List[Dict[str, Any]] = []
        words = text.split()
        
        # Simple word-based chunking with overlap
        step = max(1, self.chunk_size - self.overlap)
        idx = 0
        chunk_count = 0
        
        while idx < len(words):
            chunk_words = words[idx : idx + self.chunk_size]
            chunk_str = " ".join(chunk_words)
            
            chunk_meta = dict(metadata)
            chunk_meta["chunk_index"] = chunk_count
            
            chunks.append({
                "content": chunk_str,
                "metadata": chunk_meta
            })
            
            chunk_count += 1
            idx += step

        return chunks
