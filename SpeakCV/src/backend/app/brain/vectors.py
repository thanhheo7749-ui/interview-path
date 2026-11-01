import numpy as np


def encode(values) -> bytes:
    return np.asarray(values, dtype="<f4").tobytes()


def decode(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")


def cosine_matrix(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return np.zeros(0, dtype="<f4")
    query_norm = np.linalg.norm(query) or 1.0
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    return (matrix @ query) / (norms * query_norm)
