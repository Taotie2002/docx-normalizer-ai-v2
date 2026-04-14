"""
DFGP Schema 验证模型
SRS-2026-002 V11.2

DFGP = Document Format Gene Pattern (文档格式基因图谱)
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
import yaml


@dataclass
class FontSpec:
    """字体规范"""
    name: str              # 字体名称 (如 "方正小标宋简体")
    size_pt: float         # 字号 (pt)
    bold: bool = False     # 是否加粗
    italic: bool = False   # 是否斜体


@dataclass
class ParagraphSpec:
    """段落规范"""
    alignment: str         # LEFT | CENTER | RIGHT | JUSTIFY
    first_line_indent_pt: float  # 首行缩进 (pt)
    line_spacing_pt: float = 28  # 行距 (pt)
    space_before: float = 0
    space_after: float = 0


@dataclass
class DFGPBlockSpec:
    """单个块类型的格式规范"""
    label: str            # MAIN_TITLE, TEXT_BODY, etc.
    font: FontSpec
    paragraph: ParagraphSpec
    keep_with_next: bool = False
    page_break_before: bool = False


@dataclass 
class DFGPConfig:
    """完整的 DFGP 配置"""
    template_id: str
    document_type: str
    page_margin: Dict[str, float]  # top, bottom, left, right (cm)
    paper_size: str = "A4"
    footer_format: Optional[str] = None  # e.g., "—{page}—"
    specs: Dict[str, DFGPBlockSpec] = field(default_factory=dict)
    
    @classmethod
    def from_yaml(cls, path: str) -> 'DFGPConfig':
        """从 YAML 文件加载"""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)
    
    @classmethod
    def _from_dict(cls, data: dict) -> 'DFGPConfig':
        """从字典加载"""
        specs = {}
        for label, spec_data in data.get('specs', {}).items():
            font_data = spec_data['font']
            para_data = spec_data['paragraph']
            
            font = FontSpec(
                name=font_data['name'],
                size_pt=font_data['size_pt'],
                bold=font_data.get('bold', False),
                italic=font_data.get('italic', False)
            )
            
            para = ParagraphSpec(
                alignment=para_data['alignment'],
                first_line_indent_pt=para_data['first_line_indent_pt'],
                line_spacing_pt=para_data.get('line_spacing_pt', 28),
                space_before=para_data.get('space_before', 0),
                space_after=para_data.get('space_after', 0)
            )
            
            specs[label] = DFGPBlockSpec(
                label=label,
                font=font,
                paragraph=para,
                keep_with_next=spec_data.get('keep_with_next', False),
                page_break_before=spec_data.get('page_break_before', False)
            )
        
        return cls(
            template_id=data['template_id'],
            document_type=data['document_type'],
            page_margin=data.get('page_margin', {}),
            paper_size=data.get('paper_size', 'A4'),
            footer_format=data.get('footer_format'),
            specs=specs
        )


# === GB/T 9704-2012 标准配置 ===
GB9704_STANDARD = DFGPConfig(
    template_id="gb9704-2012",
    document_type="政府公文",
    page_margin={"top": 3.7, "bottom": 3.5, "left": 2.8, "right": 2.6},
    paper_size="A4",
    footer_format="—{page}—",
    specs={
        "MAIN_TITLE": DFGPBlockSpec(
            label="MAIN_TITLE",
            font=FontSpec(name="方正小标宋简体", size_pt=22, bold=False),
            paragraph=ParagraphSpec(alignment="CENTER", first_line_indent_pt=0)
        ),
        "TITLE_L1": DFGPBlockSpec(
            label="TITLE_L1",
            font=FontSpec(name="黑体", size_pt=16, bold=False),
            paragraph=ParagraphSpec(alignment="LEFT", first_line_indent_pt=0)
        ),
        "TITLE_L2": DFGPBlockSpec(
            label="TITLE_L2",
            font=FontSpec(name="楷体_GB2312", size_pt=16, bold=False),
            paragraph=ParagraphSpec(alignment="LEFT", first_line_indent_pt=0)
        ),
        "TEXT_BODY": DFGPBlockSpec(
            label="TEXT_BODY",
            font=FontSpec(name="仿宋_GB2312", size_pt=16, bold=False),
            paragraph=ParagraphSpec(alignment="JUSTIFY", first_line_indent_pt=32, line_spacing_pt=28)
        ),
        "SALUTATION": DFGPBlockSpec(
            label="SALUTATION",
            font=FontSpec(name="仿宋_GB2312", size_pt=16, bold=False),
            paragraph=ParagraphSpec(alignment="LEFT", first_line_indent_pt=0)
        ),
        "CONCLUSION": DFGPBlockSpec(
            label="CONCLUSION",
            font=FontSpec(name="仿宋_GB2312", size_pt=16, bold=False),
            paragraph=ParagraphSpec(alignment="CENTER", first_line_indent_pt=0)
        ),
        "SIGNATURE": DFGPBlockSpec(
            label="SIGNATURE",
            font=FontSpec(name="仿宋_GB2312", size_pt=16, bold=False),
            paragraph=ParagraphSpec(alignment="RIGHT", first_line_indent_pt=0)
        )
    }
)
