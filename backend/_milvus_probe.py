import time
t0 = time.time()
from app.services.vector_store import get_milvus
print(f"[{time.time()-t0:.1f}s] get_milvus() 构建成功")
db = get_milvus()
print(f"collection={db.collection_name} uri={db._uri}")
t1 = time.time()
docs = db.retrieve("FANUC 机器人急停报警", top_k=2)
print(f"[{time.time()-t1:.1f}s] retrieve 成功，{len(docs)} 条")
for d in docs[:2]:
    print("  -", d.page_content[:60].replace("\n"," "), "| brand=", d.metadata.get("brand"), "| doc_id=", d.metadata.get("document_id"))
