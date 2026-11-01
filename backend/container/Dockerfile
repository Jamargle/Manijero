# syntax=docker/dockerfile:1
#
# Manijero answer service image (docs/specs/backend_container_image.md).
#
# Built only by ./scripts/init.sh --container-build, which passes every argument below:
#   BASE_IMAGE  <tag>@<index digest> from backend/container/base-image.json
#   RELEASE_ID  the published knowledge release copied from the build context "knowledge-release"
#   LOCAL_MODEL the reviewed drafting-model tag from backend/config/local_generation_model.json
# The pin-verified search model comes from the build context "embedding-model". The main
# context is the repository root, filtered by the allowlist in Dockerfile.dockerignore.
# Drafting stays on the host Mac; the image holds no drafting model, settings file, or secret.

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG RELEASE_ID
ARG LOCAL_MODEL

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system --gid 10001 manijero \
 && useradd --system --uid 10001 --gid 10001 --create-home --home-dir /home/manijero \
      --shell /usr/sbin/nologin manijero

# Pinned Python packages. torch comes only from the CPU wheel index so no GPU libraries enter
# the image. The production pins are installed as requirements (pip refuses extras such as
# uvicorn[standard] in a constraints file), which narrows the ranges in requirements.txt to them.
WORKDIR /tmp/manijero-requirements
COPY backend/requirements.txt backend/requirements-embeddings.txt backend/requirements-hybrid.txt ./
COPY backend/deploy/requirements-production.txt ./requirements-production.txt
RUN grep -E '^torch==' requirements-embeddings.txt > requirements-torch.txt \
 && pip install --index-url https://download.pytorch.org/whl/cpu --requirement requirements-torch.txt \
 && pip install --requirement requirements-hybrid.txt --requirement requirements-production.txt \
 && mkdir -p /opt/manijero \
 && pip freeze > /opt/manijero/pip-freeze.txt \
 && cd / && rm -rf /tmp/manijero-requirements

# The unchanged service code and its reviewed configuration.
COPY backend/app/ /opt/manijero/backend/app/
COPY backend/config/ /opt/manijero/backend/config/
COPY backend/container/ /opt/manijero/backend/container/

# The published knowledge release (with its vector store, which the service opens in place and
# must be able to write) and the pin-verified search model.
COPY --from=knowledge-release --chown=10001:10001 . /opt/manijero/knowledge-releases/releases/${RELEASE_ID}/
COPY --from=embedding-model . /opt/manijero/models/bge-m3/
RUN test -n "${RELEASE_ID}" && test -n "${LOCAL_MODEL}" \
 && ln -s "releases/${RELEASE_ID}" /opt/manijero/knowledge-releases/current

# The fixed service environment (the same keys as ./scripts/init.sh --local-rag-start, with
# image paths). MANIJERO_ACTIVE_CAMPAIGN comes from the settings file at start.
ENV MANIJERO_KNOWLEDGE_RELEASE_ROOT=/opt/manijero/knowledge-releases \
    MANIJERO_RETRIEVAL_MODE=hybrid \
    MANIJERO_VECTOR_STORE=/opt/manijero/knowledge-releases/releases/${RELEASE_ID}/vector-store \
    MANIJERO_EMBEDDING_ARTIFACT=/opt/manijero/models/bge-m3 \
    MANIJERO_GENERATION_PROVIDER=local \
    MANIJERO_LOCAL_MODEL=${LOCAL_MODEL}

USER 10001:10001
WORKDIR /opt/manijero/backend
EXPOSE 8000
ENTRYPOINT ["python", "/opt/manijero/backend/container/entrypoint.py"]
