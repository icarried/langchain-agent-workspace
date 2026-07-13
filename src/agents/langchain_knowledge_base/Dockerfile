FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md* ./
COPY kb_api ./kb_api
COPY prompts ./prompts
COPY evals ./evals

RUN pip install --no-cache-dir .

EXPOSE 8008

CMD ["uvicorn", "kb_api.main:app", "--host", "0.0.0.0", "--port", "8008"]

