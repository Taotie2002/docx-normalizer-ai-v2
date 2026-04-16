"""
DocumentIRBlock - 核心数据结构
SRS-2026-002 V11.2

语义驱动的文档编译器中，模块间通信的唯一数据结构。
禁止在模块间传递原生 python-docx Document 对象。
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class DocumentIRBlock:
    """
    每一个物理段落或独立对象，必须被转化为严格的 DocumentIRBlock 对象。
    
    Attributes:
        block_id: 唯一区块 UUID，用于多 Agent 审查回溯
        text: 纯文本（复杂对象填 "[COMPLEX_ANCHOR]"）
        label: 语义标签，必须属于 BlockLabel 枚举
        confidence: 判定置信度 (0.0 ~ 1.0)
        source_para_idx: 原始文档的绝对段落序号 (严格递增，用于零丢失审计)
        classifier_source: 判定来源枚举: RULE | RAG | SPATIAL | FALLBACK | SYSTEM
        
        # 逻辑层级与结构特征
        heading_level: 大纲级别 (如: 1, 2, 3)
        list_level: 列表嵌套层级
        is_list_item: 是否为列表项
        
        # 复杂对象物理挂载点
        is_complex_obj: 是否包含表格、图片、公式
        is_unsupported_obj: 是否为当前版本不支持的浮动对象
        complex_type: TABLE | INLINE_PICTURE | OMATH
        xml_payload: 完整底层 XML 字符串 (深拷贝)
        rid_dependency_map: 依赖的 rId 映射表
        
        # 分页与视觉约束
        pagination: 分页控制字典
        metadata: 扩展元数据
    """
    
    # === 核心标识 ===
    block_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    label: str = "UNPROCESSED"  # Phase 1 默认标签
    confidence: float = 1.0
    source_para_idx: int = 0
    classifier_source: str = "SYSTEM"  # SYSTEM | RULE | RAG | SPATIAL | FALLBACK
    
    # === 逻辑层级与结构特征 ===
    heading_level: Optional[int] = None
    list_level: Optional[int] = None
    is_list_item: bool = False
    
    # === 复杂对象物理挂载点 ===
    is_complex_obj: bool = False
    is_unsupported_obj: bool = False
    complex_type: Optional[str] = None  # TABLE | INLINE_PICTURE | OMATH
    xml_payload: Optional[str] = None
    rid_dependency_map: Dict[str, str] = field(default_factory=dict)
    
    # === 分页与视觉约束 ===
    pagination: Dict[str, bool] = field(default_factory=lambda: {
        "keep_with_next": False,
        "page_break_before": False,
        "widow_control": True
    })
    
    # === 扩展元数据 ===
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # ---------------------------------------------------------
    # V2 Roadmap: 预留行内格式扩展点 (响应评审建议 1)
    # 目的: 支持 Bold/Italic 等 inline markup 的精确重建
    # inline_runs: Optional[List["InlineRun"]] = None
    # ---------------------------------------------------------
    
    def __post_init__(self):
        """数据校验"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0~1.0, got {self.confidence}")
        if self.source_para_idx < 0:
            raise ValueError(f"source_para_idx must be non-negative, got {self.source_para_idx}")
        if self.classifier_source not in ('SYSTEM', 'RULE', 'RAG', 'SPATIAL', 'FALLBACK'):
            raise ValueError(f"classifier_source must be SYSTEM|RULE|RAG|SPATIAL|FALLBACK, got {self.classifier_source}")
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "block_id": self.block_id,
            "text": self.text,
            "label": self.label,
            "confidence": self.confidence,
            "source_para_idx": self.source_para_idx,
            "classifier_source": self.classifier_source,
            "heading_level": self.heading_level,
            "list_level": self.list_level,
            "is_list_item": self.is_list_item,
            "is_complex_obj": self.is_complex_obj,
            "is_unsupported_obj": self.is_unsupported_obj,
            "complex_type": self.complex_type,
            "xml_payload": self.xml_payload,
            "rid_dependency_map": self.rid_dependency_map,
            "pagination": self.pagination,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentIRBlock':
        """反序列化"""
        return cls(**data)
    
    def with_label(self, label: str, confidence: float = 1.0, source: str = "SYSTEM") -> 'DocumentIRBlock':
        """链式调用：更新分类结果"""
        self.label = label
        self.confidence = confidence
        self.classifier_source = source
        return self


# === Label 枚举定义 (DFGP 语义标签) ===
class BlockLabel:
    """DFGP 定义的语义标签枚举"""
    # 段落类型
    UNPROCESSED = "UNPROCESSED"         # Phase 1 默认值
    MAIN_TITLE = "MAIN_TITLE"           # 主标题
    TITLE_L1 = "TITLE_L1"               # 一级标题 (一、)
    CHAPTER = "CHAPTER"               # 章节标题（第X章）
    TITLE_L2 = "TITLE_L2"               # 二级标题 (（一）)
    TITLE_L3 = "TITLE_L3"               # 三级标题
    SALUTATION = "SALUTATION"          # 称谓行
    TEXT_BODY = "TEXT_BODY"             # 正文
    CONCLUSION = "CONCLUSION"          # 结语
    # 落款分两级
    SIGNATURE_NAME = "SIGNATURE_NAME"     # 发文机关署名（居右对齐）
    SIGNATURE_DATE = "SIGNATURE_DATE"       # 成文日期（严格右空四字）
    ATTACHMENT = "ATTACHMENT"           # 附件说明
    DOC_NUMBER = "DOC_NUMBER"           # 文号（合政办〔2017〕1号）
    LIST_ITEM = "LIST_ITEM"             # 列表项
    CC_UNIT = "CC_UNIT"                 # 抄送单位
    PUBLISHER_INFO = "PUBLISHER_INFO"   # 印发机关和日期
    THEME_KEYWORD = "THEME_KEYWORD"     # 主题词
    
    # 复杂对象
    TABLE = "TABLE"                     # 表格
    INLINE_PICTURE = "INLINE_PICTURE"   # 嵌入式图片
    PAGE_BREAK = "PAGE_BREAK"           # 分页符
    
    # 特殊
    UNKNOWN = "UNKNOWN"                 # 未知/未分类
    
    @classmethod
    def is_valid(cls, label: str) -> bool:
        """验证标签是否合法"""
        return label in (
            cls.UNPROCESSED, cls.MAIN_TITLE, cls.TITLE_L1, cls.TITLE_L2, cls.TITLE_L3,
            cls.SALUTATION, cls.TEXT_BODY, cls.CONCLUSION, cls.SIGNATURE_NAME, cls.SIGNATURE_DATE,
            cls.ATTACHMENT, cls.LIST_ITEM, cls.CC_UNIT, cls.PUBLISHER_INFO, cls.THEME_KEYWORD,
            cls.TABLE, cls.INLINE_PICTURE, cls.PAGE_BREAK, cls.UNKNOWN
        )
    
    @classmethod
    def is_paragraph_type(cls, label: str) -> bool:
        """是否为纯段落类型（不含复杂对象）"""
        return label in (
            cls.UNPROCESSED, cls.MAIN_TITLE, cls.TITLE_L1, cls.TITLE_L2, cls.TITLE_L3,
            cls.SALUTATION, cls.TEXT_BODY, cls.CONCLUSION, cls.SIGNATURE_NAME, cls.SIGNATURE_DATE,
            cls.ATTACHMENT, cls.LIST_ITEM, cls.CC_UNIT, cls.PUBLISHER_INFO, cls.THEME_KEYWORD,
            cls.UNKNOWN
        )
