# Conda LangChain Environment

## 环境名称

推荐环境名：`langchain`

当前状态：用户已创建好 conda 环境 `langchain`。后续开发通常只需要激活环境。

## 创建环境

在工作空间根目录运行：

```powershell
conda env create -f environment.yml
conda activate langchain
```

如果环境已创建，直接运行：

```powershell
conda activate langchain
```

如果环境已存在并需要更新：

```powershell
conda env update -f environment.yml --prune
conda activate langchain
```

## 验证安装

```powershell
python -c "import langchain, langgraph; print('langchain/langgraph ok')"
python -m pytest
```

## 依赖说明

- `langchain`: LangChain 主包。
- `langgraph`: 构建有状态、多节点 Agent 图。
- `langchain-openai`: OpenAI 兼容模型接入，也可用于 DeepSeek 等 OpenAI-compatible endpoint。
- `langsmith`: tracing 和调试。
- `python-dotenv`: 加载 `.env.local`。
- `pytest` / `pytest-asyncio`: 测试同步和异步 Agent。
- `ruff`: 代码检查和格式化。

## API Key

真实密钥位于根目录 `.env.local`，模板见 `.env.example`。不要把 `.env.local` 提交到版本库。
