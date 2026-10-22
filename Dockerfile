FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config libtirpc-dev rpcsvc-proto rpcbind \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY Makefile ./
COPY server ./server
RUN make && make test

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir .

ENV PATH="/app/build:${PATH}" PYTHONUNBUFFERED=1
