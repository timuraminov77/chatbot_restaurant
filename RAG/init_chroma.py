import sys
sys.path.insert(0, ".")

from RAG.chroma_store import get_collection, populate_collection

if __name__ == "__main__":
    collection = get_collection()
    populate_collection(collection)
    print("Готово!")
