# 智能体独立打包指南

本指南用于把 `src/agents/<agent_name>/` 封装为可脱离当前多智能体工作区安装、运行和交付的 ZIP。打包产物不应依赖工作区的 `src.agents`、共享数据目录或本机绝对路径。

## 独立边界

准备打包的智能体必须满足：

- Python 模块只使用包内相对导入或第三方依赖，不导入工作区 `src.*`。
- prompt、审查规则、静态参考数据、示例和默认配置均放在智能体目录内。
- 包内资源通过 `Path(__file__)` 定位；用户输入、输出和 `.env.local` 相对当前工作目录定位。
- 临时上传使用系统临时目录，并在调用结束后清理。
- 不打包 `.env.local`、真实密钥、真实业务文件、审查输出、缓存或字节码。

## 目录约定

```text
src/agents/<agent_name>/
  standalone_manifest.json
  standalone/
    README.md
    .env.example
    mcp-config.example.json
    mcp_client_example.py
  review_guide/
  references/
  examples/
  ...智能体源码
```

`standalone_manifest.json` 定义发行名称、包名、版本、Python 版本、控制台命令、第三方依赖和需要纳入 wheel 的资源模式。`standalone/` 保存压缩包根目录模板，不进入最终 Python 包。

## 构建

```powershell
python scripts\package_agent_standalone.py `
  --agent batch_resume_review `
  --output-dir dist
```

打包器会先拒绝仍含 `from src...` 或 `import src...` 的智能体，然后生成：

```text
dist/<distribution>-<version>.zip
  <distribution>-<version>/
    pyproject.toml
    README.md
    .env.example
    mcp-config.example.json
    mcp_client_example.py
    MANIFEST.sha256.json
    src/<package_name>/...
```

`MANIFEST.sha256.json` 可用于交付后检查文件是否变化。发布新规则、模型协议或参考数据时应提升清单版本并重新打包，不覆盖已交付的旧版本。

## 验证清单

1. 在新的临时目录解压 ZIP，清空 `PYTHONPATH`，仅将压缩包的 `src` 加入模块路径。
2. 导入顶层包，并执行至少一次 `dry_run`。
3. 使用 FastMCP in-process client 发现并调用 MCP tool。
4. 检查 ZIP 不含 `.env.local`、密钥、真实简历、输出报告、`__pycache__`。
5. 在干净虚拟环境执行 `pip install -e .`，再验证 CLI、API、stdio MCP 和 HTTP MCP。

## MCP 文档要求

每个独立智能体的 `standalone/README.md` 至少说明：

- stdio 与 Streamable HTTP 启动命令和端点。
- tool 名称、完整输入结构、上传格式、大小与数量限制。
- 主要响应字段、互斥或重叠关系，以及 `dry_run` 语义。
- 模型、密钥和 provider 由客户端还是服务端管理。
- 一份可直接运行的客户端示例和一份 MCP 客户端配置模板。
- 临时文件、外发模型数据、扫描件/OCR 等安全与能力边界。

## 复用步骤

为其他智能体复用时，只需消除其跨包导入、补齐内部资源和 `standalone/` 模板，再创建 `standalone_manifest.json`。通用脚本不应增加某个智能体的专用复制逻辑；任何额外文件都应由智能体目录和清单本身声明。
