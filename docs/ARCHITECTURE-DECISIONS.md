# 架构决策记录 (Architecture Decision Records)
## SRS-2026-002 V11.2 | 2026-04-14

---

## ADR-001: Classifier 定位与接口契约

**状态**: 已采纳

### 决策

Classifier **不是独立 Agent**，而是 Architect 调用的**原子函数库**。

### 接口明文

| 维度 | 说明 |
|---|---|
| **调用者** | Architect Agent (在脱骨解析后、灌注重构前调用) |
| **输入** | DocumentIRBlock (label="UNPROCESSED") + 上下文窗口 (前后各 2 个 Blocks) |
| **逻辑过程** | L1(Rule) → L2(RAG) → L3(Spatial) 决策树 |
| **输出** | 原地更新后的 DocumentIRBlock (填充 label, confidence, classifier_source) |
| **失败处理** | 三层均未命中 → label="UNKNOWN" → Auditor 后期标记 |

### 数据流契约

```
Classifier(block, context_window) -> updated_block
```

> Classifier 不产生新对象，只通过"语义发现"补全 IR Block 的元数据。

---

## ADR-002: 三 Agent 与 五模块 对应关系矩阵

**状态**: 已采纳

### 核心原则

**Agent 是"指挥官"，Module 是"武器库"。**

| Agent (角色) | 对应核心模块 | 核心动作 | 交付物 |
|---|---|---|---|
| **Architect** | Extractor + Classifier + Compiler | 1. 脱骨提取<br>2. 调用分类器贴标<br>3. 物理重写 XML | target.docx (初稿) |
| **Validator** | Auditor_Core (物理断言部分) | 1. 检查文件损坏<br>2. 校验 rId 关系链<br>3. 执行 V-03 Hash 强对比 | Validation_Report (Pass/Fail) |
| **Auditor** | Auditor_Core (视觉/语义部分) | 1. 视觉截屏比对<br>2. 语义逻辑反思 | Audit_Report (修正建议) |

### 模块职责定位

| 模块 | 定位 | 属于谁 |
|---|---|---|
| Extractor | 脱骨器 | Architect 的武器 |
| Classifier | 分类函数库 | Architect 调用的原子服务 |
| Compiler | 重构编译器 | Architect 的武器 |
| Agent_Hub | 状态机+消息总线 | 三 Agent 共用基础设施 |
| Auditor_Core | 断言+视觉审计 | Validator + Auditor 共享 |

---

## ADR-003: V-03 失败模式定义

**状态**: 已采纳

### 三重验证回顾

1. **完整字符串 Hash 比对**: hash(RawText) == hash(NewText)
2. **Token 级 Diff 扫描**: 防止相似字形静默替换
3. **结构顺序比对**: source_para_idx 必须严格递增

### 失败处理协议

| 失败模式 | 场景定义 | 处理策略 |
|---|---|---|
| **All-Pass** (完美通过) | Hash 完全一致，Token 差异为 0 | 流程终止，直接交付成品 |
| **Partial-Fail** (局部丢失) | 文字无丢失，但空格/换行符缺失 | 触发一次重构，尝试空行补偿<br>二次仍不一致 → 带 [Warning] 强行放行 |
| **All-Fail** (致命丢失) | Hash 严重不符 (掉字、幻觉加字) | Validator 立即拦截<br>回退至原文档备份<br>发出 [Fatal Error] + block_id 记录 |

### 决策理由

- **All-Pass 直接交付**: 避免不必要的处理
- **Partial-Fail 一次重试**: 焦土清洗导致的格式问题通常可补偿
- **All-Fail 硬阻断**: 任何内容丢失都是不可接受的

---

## ADR-004: 模块边界交接协议

**状态**: 已采纳

### Extraction → Classification → Compilation 交接契约

1. **Extraction 输出**: DocumentIRBlock[] (label="UNPROCESSED")
2. **Classification 输入**: DocumentIRBlock + context_window
3. **Classification 输出**: DocumentIRBlock (label 已填充)
4. **Compilation 输入**: DocumentIRBlock[] + DFGPConfig

### 契约保障

- 每段交接必须校验 `source_para_idx` 严格递增
- `is_complex_obj=True` 的 Block 必须携带完整 `xml_payload`
- 类型标错时，由 Auditor 在视觉审计阶段发现并打回
