"""Voyage embeddings adapter. Reads only VOYAGE_API_KEY."""
import os

import httpx
import requests
import voyageai as voyage_sdk
import voyageai.error as voyage_errors

from app.ai.types import AIOutputError, AIProviderError, ProviderEmbedding, Usage


class VoyageProvider:
    def __init__(self):
        self._client = voyage_sdk.Client(api_key=os.environ["VOYAGE_API_KEY"], max_retries=0)

    def embed(self, *, model, texts, kind, dim) -> ProviderEmbedding:
        try:
            response = self._client.embed(list(texts), model=model, input_type=kind, output_dimension=dim)
        except (voyage_errors.VoyageError, httpx.HTTPError, requests.RequestException) as exc:
            raise AIProviderError(f"voyage call failed: {type(exc).__name__}") from None
        if len(response.embeddings) != len(texts):
            raise AIOutputError("Voyage returned a different number of embeddings than inputs")
        return ProviderEmbedding(vectors=[list(v) for v in response.embeddings], usage=Usage(input_tokens=response.total_tokens))
