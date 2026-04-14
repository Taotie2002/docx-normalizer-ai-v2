# docx-normalizer-ai-v2

Doc/Docx 语义重构标准化引擎 (Document Compiler)

## 系统概述

基于 SRS V11.2 规范的语义驱动文档编译器，将传统 OOXML 物理节点修补范式升级为：

```
[Raw Docx] → (脱骨解析器) → [DocumentIRBlock 序列] → (重构引擎 + DFGP) → [New Docx]
```

## 核心特性

- **语义驱动**：而非物理节点修补
- **DocumentIRBlock**：模块间唯一通信协议
- **三 Agent 协作**：Architect / Validator / Auditor
- **V-03 零丢失验证**：Hash 比对 + Token 级 Diff + 结构顺序

## 目录结构

```
docx-normalizer-ai-v2/
├── src/
│   ├── core/           # 核心数据结构
│   │   ├── ir_block.py      # DocumentIRBlock 定义
│   │   ├── dfgp_schema.py    # DFGP 验证模型
│   │   └── exceptions.py    # 异常树
│   ├── extractor/     # 脱骨器模块
│   ├── classifier/    # 混合分类器模块
│   ├── compiler/      # 重构编译器
│   └── agents/         # OpenClaw 协同模块
│       ├── architect.py     # Architect
│       ├── validator.py     # Validator
│       └── auditor.py       # Auditor
├── dfgp_configs/       # DFGP 格式基因图谱库
├── tests/
│   ├── unit/          # 单元测试
│   └── e2e/           # 端到端测试
└── batch_manifest.json # 批量处理状态机
```

## 模块职责

| 模块 | 职责 |
|------|------|
| Extractor | 解析源 .docx，提取文本、层级、分页约束 |
| Classifier | 运行 Rule/RAG/Spatial 仲裁树，为 IR Block 标注 label |
| Compiler | 消费 IR 序列与 DFGP 规范，重构空白文档 |
| Agent_Hub | 桥接 OpenClaw，管理状态机和消息总线 |
| Auditor_Core | 执行 XML 断言及多模态视觉比对 |

## 开发阶段

- **Phase 1**: 物理基建 - 脱骨提取→IR构建→空白重构
- **Phase 2**: 语义规则 - DFGP解析+rule_engine
- **Phase 3**: 复杂对象+RAG - 介质提取+ChromaDB
- **Phase 4**: 多Agent闭环+Golden Set验收

## 技术栈

- Python 3.11+
- python-docx
- lxml
- ChromaDB

## 相关文档

- [SRS V11.2](./docs/SRS-V11.2.md) - 需求规格说明书
- [实施计划 V1](./docs/IMPLEMENTATION-PLAN-V1.md) - 详细实施计划
