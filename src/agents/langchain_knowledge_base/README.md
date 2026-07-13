# LangChain Knowledge Base

Code-first local RAG knowledge base. The API owns the behavior; Langflow is only a demo/debug surface.

This is a workspace-managed agent. It shares the parent multi-agent workspace's Git repository and documentation conventions. Run all commands below from the workspace root; the application resolves its `.env`, documents, and Chroma data under this agent directory automatically.

```powershell
cd E:\My_sorcode\--创建智能体工作空间--
```

## Setup

1. Create `.env` from `.env.example`.
2. Put source docs under `data/docs/`.
3. Run the API locally or through Docker Compose.

The vector store uses local Chroma `PersistentClient` storage. There is no separate Chroma server in the default runtime.

Chat and embedding providers can be configured separately. A common local setup is:

- Chat: DeepSeek OpenAI-compatible API through `KB_OPENAI_*`
- Embedding: Bailian/DashScope OpenAI-compatible API through `KB_EMBEDDING_*`

Default paths:

- Source documents: `data/docs/`
- Primary knowledge base documents: `data/docs/primary/`
- Secondary knowledge base documents: `data/docs/secondary/`
- Chroma persistence: `data/chroma/`

## Ingest

```powershell
Invoke-RestMethod -Method Post http://localhost:8008/ingest
Invoke-RestMethod -Method Post http://localhost:8008/ingest -ContentType 'application/json' -Body '{"knowledge_base":"secondary"}'
```

Ingest writes embeddings and chunk metadata to `KB_CHROMA_PERSIST_DIR`, which defaults to `data/chroma`. Re-running ingest upserts stable chunk IDs, so edited source files can update existing chunks.

If `KB_EMBEDDING_API_KEY` is set, ingest uses `KB_EMBEDDING_BASE_URL` and `KB_EMBEDDING_MODEL`. If it is empty, ingest falls back to `KB_OPENAI_API_KEY` and `KB_OPENAI_BASE_URL`.

## Retrieval

Use retrieval when you only need evidence chunks and citations, without asking the chat model to synthesize an answer:

```powershell
Invoke-RestMethod -Method Post http://localhost:8008/v1/retrieval `
  -ContentType 'application/json' `
  -Body '{"question":"群众性活动要管什么","top_k":4}' |
  ConvertTo-Json -Depth 8
```

`/v1/retrieval` returns the query, citations, relevance scores, source file names, chunk ids, and a `refused` flag. Use `/v1/chat/completions` for answer synthesis and `/v1/retrieval` for retrieval-only integrations.

## Chat

```powershell
Invoke-RestMethod -Method Post http://localhost:8008/v1/chat/completions `
  -ContentType 'application/json' `
  -Body '{"model":"langchain-knowledge-base-agent","messages":[{"role":"user","content":"What is the vector store?"}],"stream":false}' |
  ConvertTo-Json -Depth 8
```

Set `knowledge_base` when you want to query a named knowledge base such as `primary` or `secondary`:

```powershell
Invoke-RestMethod -Method Post http://localhost:8008/v1/chat/completions `
  -ContentType 'application/json' `
  -Body '{"model":"langchain-knowledge-base-agent","messages":[{"role":"user","content":"群众性活动要管什么"}],"knowledge_base":"primary","stream":false}' |
  ConvertTo-Json -Depth 8
```

## OpenAI-compatible API

The normal FastAPI app is also the OpenAI-compatible API. Start one service:

```powershell
uvicorn kb_api.main:app --app-dir src/agents/langchain_knowledge_base --host 0.0.0.0 --port 8008
```

Model provider settings:

- Base URL: `http://<host>:8008/v1`
- Model: `langchain-knowledge-base-agent`
- API Key: any placeholder if the platform requires one
- Stream: supported

If FastGPT/Dify runs in Docker under WSL while this API runs on Windows, expose it through a WSL relay:

```bash
setsid -f socat -d -d \
  TCP-LISTEN:18008,bind=172.24.0.1,reuseaddr,fork \
  TCP:127.0.0.1:8008 \
  </dev/null >/tmp/windows-kb-api-relay-18008.log 2>&1
```

Then configure the platform Base URL as `http://172.24.0.1:18008/v1`.

Probe the model list:

```powershell
Invoke-RestMethod http://127.0.0.1:8008/v1/models
```

Non-streaming chat completion:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8008/v1/chat/completions `
  -ContentType 'application/json' `
  -Body '{"model":"langchain-knowledge-base-agent","messages":[{"role":"user","content":"群众性活动要管什么"}],"stream":false}' |
  ConvertTo-Json -Depth 8
```

The chat completions endpoint calls the same RAG answer service and appends citation sources to the generated content. It does not replace `/ingest` or `/v1/retrieval`.

## Test

```powershell
python -m compileall src/agents/langchain_knowledge_base/kb_api src/agents/langchain_knowledge_base/evals
$env:PYTHONPATH = (Resolve-Path "src/agents/langchain_knowledge_base").Path
python -m pytest src/agents/langchain_knowledge_base/tests -q
ruff check src/agents/langchain_knowledge_base
```

## Eval

```powershell
$env:PYTHONPATH = (Resolve-Path "src/agents/langchain_knowledge_base").Path
python -m evals.run
```

The eval harness defaults to fixture mode, so it does not need a paid model call. Use `--mode live --base-url http://localhost:8008` only when you explicitly want to exercise the API.

## Docker Compose

```powershell
# 在 WSL Ubuntu 中、工作区根目录执行
docker compose -f src/agents/langchain_knowledge_base/docker-compose.yml config
docker compose -f src/agents/langchain_knowledge_base/docker-compose.yml up --build
```

Compose starts:

- `kb-api` on `http://localhost:8008`
- `langflow` on `http://localhost:7860`

The API container stores Chroma data through the named volume `kb_chroma_data`, mounted at `/app/data/chroma`. Source documents are mounted from `./data/docs`.

Stop services without deleting the vector store:

```powershell
docker compose -f src/agents/langchain_knowledge_base/docker-compose.yml down
```

Reset the persisted vector store only when you intentionally want a clean knowledge base:

```powershell
docker compose -f src/agents/langchain_knowledge_base/docker-compose.yml down -v
```

For a local, non-Docker run, `data/chroma/` is the persisted vector store directory. Stop the API with `Ctrl+C`; delete `data/chroma/` only when you intentionally want to rebuild the local vector store from source documents.

## Langflow

Langflow is demo-only. The flow should call `POST /v1/chat/completions` and display the response; it should not recreate retrieval, prompt logic, or citation rules.

