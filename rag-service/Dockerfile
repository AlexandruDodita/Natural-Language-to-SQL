FROM python:3.12-slim

WORKDIR /app

# Set to "false" for a small image without torch; the service then uses the
# deterministic hashing embedder instead of a sentence-transformer.
ARG WITH_EMBEDDINGS=true
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

COPY requirements.txt requirements-embeddings.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
RUN if [ "$WITH_EMBEDDINGS" = "true" ]; then \
        pip install --no-cache-dir -r requirements-embeddings.txt; \
    fi

# Bake the embedding model into the image so startup needs no network.
ENV HF_HOME=/app/.cache/huggingface
RUN if [ "$WITH_EMBEDDINGS" = "true" ]; then \
        python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('${EMBEDDING_MODEL}')"; \
    fi

COPY *.py policy.yaml ./
COPY eval ./eval

# Schema catalog, embedding index and telemetry live here; mount a volume to
# keep them across restarts.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
