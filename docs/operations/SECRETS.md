# Secrets

## 已整理变量

| 变量名 | 用途 | 本地来源 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 阿里云百炼 / DashScope 模型调用；`batch-resume-review` 扫描件 OCR 也复用此变量 | `.env.local` |
| `DEEPSEEK_API_KEY` | DeepSeek API 调用 | `.env.local` |
| `KB_OPENAI_API_KEY` | `langchain_knowledge_base` 知识库智能体的 OpenAI-compatible chat 和 embedding 调用 | `src/agents/langchain_knowledge_base/.env` |
| `KB_OPENAI_BASE_URL` | `langchain_knowledge_base` 使用的 OpenAI-compatible base URL | `src/agents/langchain_knowledge_base/.env` |
| `KB_CHAT_MODEL` | `langchain_knowledge_base` 问答模型 | `src/agents/langchain_knowledge_base/.env` |
| `KB_EMBEDDING_API_KEY` | `langchain_knowledge_base` 入库向量化使用的 OpenAI-compatible embedding key，可使用百炼 / DashScope key | `src/agents/langchain_knowledge_base/.env` |
| `KB_EMBEDDING_BASE_URL` | `langchain_knowledge_base` 入库向量化使用的 OpenAI-compatible embedding base URL | `src/agents/langchain_knowledge_base/.env` |
| `KB_EMBEDDING_MODEL` | `langchain_knowledge_base` 入库 embedding 模型 | `src/agents/langchain_knowledge_base/.env` |

## 文件位置

- 真实开发密钥: `.env.local`
- 知识库智能体真实配置: `src/agents/langchain_knowledge_base/.env`
- 可提交模板: `.env.example`
- 知识库智能体模板: `src/agents/langchain_knowledge_base/.env.example`
- 原始归档文件: `secrets/raw/unorganized-api-keys/`

## 安全规则

- 不在文档、issue、提交信息或聊天回复中粘贴真实 key。
- 新增密钥时先更新 `.env.example`，再只在本机 `.env.local` 填入真实值。
- 如果 key 曾经被公开提交或外泄，应立即去对应平台轮换。
- `secrets/` 和 `.env.local` 已在 `.gitignore` 中忽略。
