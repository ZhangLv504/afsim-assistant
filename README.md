# AFSIM Local Assistant

本目录是本地 AFSIM 脚本助手的应用层。第一阶段先建立可验证的知识检索基础：

- `afsim-projectskill`：模板、代码块和参考资料。
- AFSIM 官方 `demos`：官方案例。
- `AFSIM_MCP`：查询真实类型、运行 Mission 并分析结果。
- Ollama：把自然语言需求转换为受约束的 `ScenarioSpec`；脚本组装仍由确定性代码完成。

当前不使用向量数据库。检索采用元数据状态过滤和 SQLite FTS5 全文检索。

## 快速开始

```powershell
$env:PYTHONPATH = "src"
python -m afsim_assistant doctor
python -m afsim_assistant build-index
python -m afsim_assistant search "SAM radar processor"
python -m afsim_assistant ollama
python -m afsim_assistant prepare "生成一个地空导弹拦截单架飞机的场景"
python -m afsim_assistant mcp
python -m afsim_assistant resolve "生成一个地空导弹拦截单架飞机的场景"
python -m afsim_assistant prototype "生成一个蓝方地空导弹阵地拦截一架红方飞机的场景，仿真10分钟，需要雷达探测、跟踪和导弹交战"
```

需要查看尚未验证的 `afsim-projectskill/blocks` 时：

```powershell
python -m afsim_assistant search "SAM radar processor" --include-unverified
```

## 知识状态

- `official`：AFSIM 官方 Demo。
- `validated`：已由当前 AFSIM 2.9 `mission.exe` 验证。
- `verified`：后续经完整业务场景验证并归档的成果。
- `unverified`：可供参考，但生成后必须经过 Mission 验证。
- `excluded`：暂不参与检索，例如可能依赖自定义类型的 LEO 模板。

默认搜索只返回 `official/validated/verified`。

`prepare` 只进行需求结构化和知识检索，不会直接生成或运行 AFSIM 脚本。

`resolve` 在 `prepare` 基础上调用 `AFSIM_MCP.afsim_types`，按角色、域和真实组件
能力为每支力量列出候选类型。它只提供候选与评分依据，不会在没有用户选择或后续
确定性策略的情况下自动选定类型。

`prototype` 当前只接受“一座 SAM 阵地对一架飞机，包含探测、跟踪和交战”的需求。
它从本机官方 `demos/launcher` 复制上下文到 `workspace/staging/`，生成新的入口和布设
文件并调用 Mission 验证。其他需求会明确拒绝，不会退化为自由生成。
验证不仅要求 Mission 正常退出和跑满时长，还要求事件输出中存在需求对应的能力证据；
例如探测/跟踪必须建立或更新航迹，交战必须出现 `WEAPON_FIRED`。

