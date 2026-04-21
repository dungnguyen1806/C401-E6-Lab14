import json
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_knowledge_base(raw_text_file: str, output_file: str):
    with open(raw_text_file, "r", encoding="utf-8") as f:
        text = f.read()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,     
        chunk_overlap=50,   
        separators=["\n\n", "\n", ".", " ", ""]
    )
    
    raw_chunks = splitter.split_text(text)
    
    knowledge_base = []
    for chunk in raw_chunks:
        chunk_id = f"chunk_{uuid.uuid4().hex[:8]}" 
        knowledge_base.append({
            "chunk_id": chunk_id,
            "text": chunk
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Đã tạo thành công {len(knowledge_base)} chunks. Lưu tại {output_file}")
    return knowledge_base

kb = create_knowledge_base("raw_data.txt", "knowledge_base.json")