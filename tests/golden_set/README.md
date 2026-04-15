# Golden Set - 测试基准集

## 目的

Golden Set 是 Phase 4 验收的基准测试集，用于验证 docx-normalizer-ai-v2 在各种极端情况下的零丢失能力。

## 样本类型

| 类型 | 说明 | 数量 | 测试目标 |
|------|------|------|----------|
| **Type A** | 纯文字长文档 | ~15 | 内存稳定性、V-03 长文本处理 |
| **Type B** | 大量嵌套列表 | ~15 | 层级抓取、列表识别 |
| **Type C** | 表格+内联图片 | ~10 | 锚点隔离、复杂对象 |
| **Type D** | 极致乱码风 | ~10 | V-03 强韧度、空格/换行处理 |

## 目录结构

```
golden_set/
├── type_a_pure_text/       # 纯文字长文档
│   ├── README.md
│   └── *.docx
├── type_b_nested_lists/    # 嵌套列表
│   ├── README.md
│   └── *.docx
├── type_c_tables_images/   # 表格+图片
│   ├── README.md
│   └── *.docx
├── type_d_messy_format/    # 乱码风
│   ├── README.md
│   └── *.docx
└── metadata.json           # 样本元数据
```

## 命名规范

文件命名格式：`[类型]_[序号]_[简短描述].docx`

示例：
- `a_001_政府报告长文.docx`
- `b_001_嵌套列表示范.docx`
- `c_001_表格内联图片.docx`
- `d_001_手动空格乱码.docx`

## 收集要求

每个样本需包含 `metadata.json` 中的标注：
```json
{
  "filename": "a_001_政府报告长文.docx",
  "type": "A",
  "title": "政府报告长文",
  "paragraph_count": 150,
  "complex_objects": [],
  "known_issues": [],
  "ground_truth_label": "已验证"
}
```

## 验收标准

- 所有 Type A 样本：V-03 必须 ALL_PASS
- 所有 Type B 样本：列表层级识别正确率 ≥ 90%
- 所有 Type C 样本：复杂对象锚点完整
- 所有 Type D 样本：V-03 Hash 比对通过（允许空白符规范化）

## 报告输出

批处理完成后，生成 `Phase1_Final_Report.md`，包含：
- 总体通过率
- 各类型分项成绩
- 失败样本分析与 block_id 记录
