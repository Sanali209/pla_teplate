from config import BLUEPRINT_ROOT
import chromadb
from chromadb.utils import embedding_functions

docs = ["test doc 1", "test doc 2"]
ids = ["id1", "id2"]
metadatas = [{"source": "test", "type": "test"}, {"source": "test", "type": "test"}]

# Initialize ChromaDB
db_path = BLUEPRINT_ROOT / ".vectordb"
client = chromadb.PersistentClient(path=str(db_path))
ef = embedding_functions.DefaultEmbeddingFunction()
collection = client.get_or_create_collection(name="blueprint_knowledge", embedding_function=ef)

try:
    collection.upsert(
        documents=docs,
        metadatas=metadatas,
        ids=ids
    )
    print("Upsert succeeded")
except Exception as e:
    import traceback
    traceback.print_exc()
