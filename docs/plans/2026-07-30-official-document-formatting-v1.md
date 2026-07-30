# 公文格式规范合规改造 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 依据 `临时文件/公文格式化配置/公文格式规范.docx` 正文所列规则，重构纯 DOCX
格式化内核，在不改写正文和表格内容的前提下完成主体、附件、版记、页面、页码和文号格式。

**Architecture:** 保留现有 LangGraph、统一文件接口和平台文件输出协议；把格式化内核拆为
“内容快照 → 角色分析 → 格式应用 → 结构校验”四层。第一期不调用 LLM；无法确定或涉及
文字纠错的规则只生成验证结果，不自动修改文字。

**Tech Stack:** Python 3.11、python-docx、OOXML、LangGraph、pytest、Ruff。

---

## 1. 规范来源与冲突处理

规范正文是本方案的最高优先级来源。该文件自身现有样式仅用于验证规则含义，不能覆盖
正文明确写出的数值。

- 规范正文规定右边距 `2.6 cm`，文件当前节属性为 `2.5 cm`：采用 `2.6 cm`。
- 规范正文建议固定行距 `28 pt`，文件当前 `docGrid` 的 `linePitch` 不是 28 pt：采用
  `28 pt / 560 twips`。
- 规范正文规定每行 28 字、每页 22 行：写入文档网格，并以结构检查和 Word/WPS 实际
  分页复核；不能仅从段落数量推断页数。
- 规范没有规定表格样式：现有三线表作为公司扩展保留，但与国家公文规则分开测试。
- “空一行/二行/三行”通过段前间距或分页属性表达，不向正文插入空白字符，不新增空文本
  段落。

## 2. 完整规则矩阵

### 2.1 公文主体

| 角色 | 自动格式 | 只校验、不改文字 |
| --- | --- | --- |
| 主标题 | 方正小标宋简体 22 pt，居中；存在红色分隔线时下空二行；多行居中 | 回行是否保持词义完整 |
| 主送机关 | 仿宋_GB2312 16 pt，居左顶格；标题后空一行 | 是否使用全角冒号 |
| 正文 | 仿宋_GB2312 16 pt，两端对齐，首行缩进 2 字符，固定 28 pt | 无 |
| 一级标题 `一、` | 黑体 16 pt，首行缩进 2 字符 | 编号是否连续 |
| 二级标题 `（一）` | 楷体_GB2312 16 pt，首行缩进 2 字符 | 编号是否连续 |
| 三级标题 `1.` | 仿宋_GB2312 16 pt，首行缩进 2 字符 | 标点是否为半角点号 |
| 四级标题 `（1）` | 仿宋_GB2312 16 pt，首行缩进 2 字符 | 编号是否连续 |
| 阿拉伯数字 | Latin/ASCII/HAnsi 字体 Times New Roman | 数字内容不改写 |

所有 2 字符缩进同时写入 `w:firstLine="640"` 和 `w:firstLineChars="200"`。主标题与
主送机关不缩进。

### 2.2 附件说明、署名、日期和附注

- 附件说明使用仿宋_GB2312 16 pt，在正文后空一行，左空 2 字。
- 多附件保留阿拉伯数字序号，名称后不自动添加标点。
- 附件名称换行使用悬挂缩进，使续行与附件名称首字对齐；不能依赖正文中的空格数量。
- 发文机关署名使用仿宋_GB2312 16 pt，距正文 3 行；以成文日期的水平中心为准编排。
- 成文日期使用仿宋_GB2312 16 pt，位于署名下方，右空 4 字。
- 日期格式只验证 `YYYY年M月D日`，发现 `01月` 等虚位时报告，不自动改写。
- 印章对象原样保留；只检查其锚点是否与日期块相邻，不移动或缩放印章。
- 附注位于日期下一行，左空 2 字，并检查是否使用圆括号。

### 2.3 正式附件

- 正式附件在版记前另面开始，使用段落分页属性，不插入文本分页符。
- “附件”及顺序号使用黑体 16 pt，版心左上角第一行顶格。
- 附件标题使用方正小标宋简体 22 pt，在本页第三行居中。
- 附件正文继续使用主体正文和层级规则。
- 无法确认某个“附件”是附件说明还是正式附件页时，不重排，只在结果报告中标记。

### 2.4 版记

- 版记包含抄送机关、印发机关和印发日期，使用仿宋_GB2312 14 pt。
- 左右各空 1 字；抄送机关回行与冒号后的首字对齐。
- 版记必须处于公文最后一面，最后一个要素位于最后一行，并最终落在偶数页。
- 多抄送机关的顿号、逗号和末尾句号只校验，不自动改写。
- 第一版可以确定性设置版记字体、缩进、边框和保持同页；“最后一行、偶数页”必须经过
  Word/WPS 或 LibreOffice 重新分页后验证。没有渲染器时返回“未验证”，不能声称合规。

### 2.5 页面、网格和页码

- A4 纵向：21.0 × 29.7 cm。
- 页边距：上 3.7、下 3.5、左 2.8、右 2.6 cm。
- 页脚距边界 2.5 cm，开启奇偶页不同。
- 文档网格目标为每行 28 字、每页 22 行；正文固定行距 28 pt。
- 页码使用宋体 14 pt 的 `PAGE` 域，显示为 `－{PAGE}－`。
- 奇数页页码右对齐并右空 1 字，偶数页左对齐并左空 1 字。
- 不把页码写成静态数字；输出后由 Word/WPS 更新域。

### 2.6 文号

- 平行文、下行文文号：仿宋_GB2312 16 pt，居中，位于发文机关标识下空二行。
- 上行文文号：仿宋_GB2312 16 pt，左空 1 字。
- “签发人”使用仿宋_GB2312 16 pt；签发人姓名使用楷体_GB2312 16 pt，右空 1 字。
- 文号必须使用六角括号 `〔〕`；发现方括号等形式时只报告，不自动替换。

## 3. 自动化边界

采用“确定性规则优先、歧义不猜测”的方案：

1. 自动执行字体、字号、缩进、对齐、间距、页面、页脚、页码域、分页和三线表。
2. 自动识别有稳定文本特征的主标题、主送机关、四级标题、附件说明、署名和日期。
3. 对冒号、日期虚位、编号连续性、附件末尾标点、抄送标点和六角括号只给出问题清单。
4. 对印章位置、版记最后一行/偶数页、标题回行词义和特殊情况下的行距/字距调整，必须
   通过渲染结果或人工复核。
5. LLM 不进入第一期写入链路。未来如增加，只能返回段落角色和置信度，不能生成正文。

## 4. 实施任务

### Task 1: 固化规范模型和角色模型

**Files:**
- Create: `src/agents/official_document_formatting/standards.py`
- Create: `src/agents/official_document_formatting/roles.py`
- Test: `tests/agents/test_official_document_formatting_roles.py`

**Step 1:** 为页面、字体、字号、缩进、间距、页码和版记建立不可变配置对象。

**Step 2:** 编写主标题、主送机关、四级标题、附件说明、正式附件、署名、日期、附注、
版记、文号和签发人的纯函数分类测试。

**Step 3:** 运行：

```powershell
python -m pytest tests/agents/test_official_document_formatting_roles.py -q
```

预期：新测试先失败，再以最小分类规则实现至通过。

**Step 4:** 提交：

```text
feat: model official document standard roles
```

### Task 2: 重构段落格式化内核

**Files:**
- Modify: `src/agents/official_document_formatting/formatter.py`
- Test: `tests/agents/test_official_document_formatting.py`

**Step 1:** 将当前长条件分支替换为“角色 → 格式规格”映射。

**Step 2:** 为正文和四级标题写入 2 字符缩进，为主送机关清除缩进，并为阿拉伯数字写入
Times New Roman。

**Step 3:** 用段前间距实现空一至三行；用悬挂缩进实现附件名称续行对齐。

**Step 4:** 增加标题、附件、署名、日期、附注、文号和签发人属性测试。

**Step 5:** 运行格式化测试并提交：

```text
feat: apply role based official document formatting
```

### Task 3: 实现页面网格和奇偶页码

**Files:**
- Create: `src/agents/official_document_formatting/page_layout.py`
- Modify: `src/agents/official_document_formatting/formatter.py`
- Test: `tests/agents/test_official_document_formatting_layout.py`

**Step 1:** 显式写入 A4、四边距、页脚距离、奇偶页不同和文档网格。

**Step 2:** 创建奇偶页 footer，插入动态 `PAGE` 域和全角连接号；奇数页右空 1 字，偶数
页左空 1 字。

**Step 3:** 测试 `settings.xml`、`sectPr`、footer relationship、字段指令、字体字号和缩进。

**Step 4:** 运行布局测试并提交：

```text
feat: add official document grid and page numbers
```

### Task 4: 实现附件、版记和分页约束

**Files:**
- Create: `src/agents/official_document_formatting/backmatter.py`
- Modify: `src/agents/official_document_formatting/formatter.py`
- Test: `tests/agents/test_official_document_formatting_backmatter.py`

**Step 1:** 区分附件说明和正式附件页，正式附件设置另面开始和标题第三行位置。

**Step 2:** 识别版记段落，设置仿宋 14 pt、左右 1 字、悬挂缩进和保持同页属性。

**Step 3:** 对不能从 OOXML 静态确认的偶数页/最后一行要求记录 `unverified`，不伪造通过。

**Step 4:** 增加附件和版记夹具，运行测试并提交：

```text
feat: format official document attachments and imprint
```

### Task 5: 增加规范校验结果且保持平台兼容

**Files:**
- Modify: `src/agents/official_document_formatting/schemas.py`
- Modify: `src/agents/official_document_formatting/graph.py`
- Modify: `src/agents/official_document_formatting/service.py`
- Modify: `src/agents/official_document_formatting/openai_compatible_api.py`
- Test: `tests/agents/test_official_document_formatting_llm.py`

**Step 1:** 增加不改变正文的校验项：严重级别、规则 ID、段落索引、说明和是否已验证。

**Step 2:** 保持现有 `message.file` / `delta.file` 不变，在报告字段中附加警告摘要。

**Step 3:** 确保 readiness、非流式、SSE、远程附件和 dry-run 兼容。

**Step 4:** 运行平台接口测试并提交：

```text
feat: report official document compliance findings
```

### Task 6: 建立金标准和内容不变回归

**Files:**
- Modify: `tests/agents/test_official_document_formatting.py`
- Create: `tests/agents/test_official_document_formatting_golden.py`
- Use: `临时文件/公文格式化配置/公文格式规范.docx`
- Use: `临时文件/公文格式化配置/关于采购多场景机器人及具身智能技术研发及能力建设项目配套设备的请示-原版.docx`

**Step 1:** 对规范文件建立正文要求快照，不把它自身不一致的右边距和网格属性当成期望值。

**Step 2:** 对采购请示验证标题、主送机关、六个一级标题、正文、附件、署名、日期、A4、
页码和表格。

**Step 3:** 比较所有正文段落和表格单元格值，保证格式化前后完全一致。

**Step 4:** 在有 Word/WPS 或 LibreOffice 和规定字体的环境渲染全部页面，人工确认分页、
标题回行、表格、附件、署名、日期、页码和版记。

**Step 5:** 运行完整聚焦回归并提交：

```text
test: add official document standard golden coverage
```

### Task 7: 更新运行文档和任务记录

**Files:**
- Modify: `src/agents/official_document_formatting/README.md`
- Modify: `docs/development/RUN_AND_DEBUG.md`
- Modify: `docs/workspace/AGENT_REGISTRY.md`
- Modify: `docs/workspace/DECISIONS.md`
- Modify: `.agents/tasks/TASK_BOARD.md`

**Step 1:** 文档化自动格式化、只校验和必须渲染复核的边界。

**Step 2:** 记录规范正文优先于样例文件内部不一致属性的决策。

**Step 3:** 执行最终验证：

```powershell
python -m pytest tests/agents/test_official_document_formatting.py `
  tests/agents/test_official_document_formatting_roles.py `
  tests/agents/test_official_document_formatting_layout.py `
  tests/agents/test_official_document_formatting_backmatter.py `
  tests/agents/test_official_document_formatting_golden.py `
  tests/agents/test_official_document_formatting_llm.py `
  tests/agents/test_remote_files.py `
  tests/agent_gateway/test_gateway.py -q
ruff check src/agents/official_document_formatting tests/agents
git diff --check
```

预期：全部测试与静态检查通过；没有渲染器时，分页相关状态必须为 `unverified`。

**Step 4:** 提交：

```text
docs: document official document standard compliance
```

## 5. 验收结论

完成本方案后，智能体只能在以下条件同时满足时报告“格式化完成且结构规则通过”：

1. 输出 DOCX 可重新打开。
2. 正文段落和表格内容与输入完全一致。
3. 可静态检查的字体、字号、缩进、行距、页面、页码和结构规则通过。
4. 需要分页或视觉判断的规则已经渲染验证；没有渲染器时明确标为未验证。

第一期不应继续使用“所有规则均已符合”这种笼统表述。
