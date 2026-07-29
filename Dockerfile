FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends fontconfig libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-linux.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-linux.txt

COPY . .
RUN mkdir -p /usr/local/share/fonts/official-document \
    && cp /app/src/agents/official_document_formatting/fonts/* /usr/local/share/fonts/official-document/ \
    && fc-cache -f \
    && mkdir -p /app/data/knowledge_bases /app/tmp \
    && useradd --create-home --uid 10001 agent \
    && chown -R agent:agent /app/data /app/tmp

USER agent
EXPOSE 8080

CMD ["python", "-m", "src.agent_gateway", "serve", "--host", "0.0.0.0", "--port", "8008"]
