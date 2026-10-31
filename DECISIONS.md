# 第一阶段设计决策

1. `afsim2.9en-src` 不作为部署时的大模型上下文，只从其中使用官方 demos 和 AFSIM 可执行程序。
2. `afsim-projectskill` 是主要模板/代码块知识源，但不默认信任其“verified”文字说明。
3. LEO 相关 projectskill 资源暂时标记为 `excluded`，不进入默认索引。
4. `afsim-skill` 不作为运行组件；后续只选择性迁移错误经验和 staging/verified 工作流。
5. 第一版不使用向量数据库，采用结构化状态过滤、元数据和 SQLite FTS5。
6. Mission 实际运行结果是最终正确性依据；仅“返回码为 0、跑满时长”不够，必须同时检查需求能力对应的事件证据。

