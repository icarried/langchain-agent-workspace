# Langflow Demo

This repo treats Langflow as a demo/debug surface only.

## What the flow should do

- Accept a user question.
- Send it to `POST /v1/chat/completions` on the FastAPI service.
- Show `choices[0].message.content`.

## What the flow should not do

- It should not contain retrieval logic.
- It should not duplicate the core prompt.
- It should not implement citation assembly or RAG state management.

## Artifact

`langflow/flows/kb_chat_demo.json` is a conservative starter artifact. Treat it as a handoff aid, not as a verified import target.

## Manual setup

If Langflow version differences prevent import, create a simple HTTP request component by hand:

1. Add a text input for the question.
2. Add an HTTP request node that posts an OpenAI-compatible chat completion payload to `http://kb-api:8008/v1/chat/completions`.
3. Render `choices[0].message.content`.

The demo should remain thin even if the flow layout changes.

