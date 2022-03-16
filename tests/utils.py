from src.common.database import db


def count_docs(collection: str) -> int:
    """
    Count documents in a collection.
    """
    docs_stream = db.collection(collection).stream()
    counter = 0

    for doc in docs_stream:
        counter += 1

    return counter
