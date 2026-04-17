"""
DFGP Manager - 文档格式基因图谱管理器
SRS-2026-002 V11.2 | Phase 2 (Style-based Refactor)

职责：
1. 加载 DFGP YAML 配置
2. 根据 label 输出格式参数
3. 动态计算 Twips 值（字符缩进、行距等）
4. 支持 GB/T 9704-2012 公文格式标准
5. 提供 Word 样式定义（用于纯样式方案）
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PageMargin:
    """页面边距（Twips 单位）"""
    top_twips: int
    bottom_twips: int
    left_twips: int
    right_twips: int
    
    @classmethod
    def from_cm(cls, top_cm: float, bottom_cm: float, left_cm: float, right_cm: float) -> 'PageMargin':
        """从厘米值创建（1cm = 567 Twips）"""
        return cls(
            top_twips=int(top_cm * 567),
            bottom_twips=int(bottom_cm * 567),
            left_twips=int(left_cm * 567),
            right_twips=int(right_cm * 567)
        )


@dataclass
class StyleParams:
    """样式参数（Twips 单位 + Word 样式名）"""
    # 字体
    font_family: str          # 中文字体（英文名，Word用）
    font_size_pt: int         # 磅值
    
    # 对齐
    alignment: str            # LEFT, CENTER, RIGHT, JUSTIFY
    
    # 段落格式
    first_line_indent_twips: Optional[int] = None
    right_indent_twips: Optional[int] = None
    line_spacing_twips: Optional[int] = None
    space_before_twips: int = 0
    space_after_twips: int = 0
    
    # Word 样式（用于 paragraph.style）
    word_style_name: Optional[str] = None   # 如 'Heading 1', 'Normal'
    
    # 分页控制
    keep_with_next: bool = False
    page_break_before: bool = False
    outline_level: Optional[int] = None     # 用于 TOC 识别
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "font_family": self.font_family,
            "font_size_pt": self.font_size_pt,
            "alignment": self.alignment,
            "first_line_indent_twips": self.first_line_indent_twips,
            "right_indent_twips": self.right_indent_twips,
            "line_spacing_twips": self.line_spacing_twips,
            "word_style_name": self.word_style_name,
            "keep_with_next": self.keep_with_next,
            "page_break_before": self.page_break_before,
            "outline_level": self.outline_level
        }


# =============================================================================
# Word 样式定义 - 纯样式方案使用
# 注意：这些是 Word 内置样式的名称，不是自定义样式
# =============================================================================
WORD_STYLE_MAPPING = {
    # 标签 → Word 样式配置
    'MAIN_TITLE': {
        'word_style': None,            # 无内置样式，用字体实现
        'font_name': 'FangSong',        # 方正小标宋简体 → FangSong
        'font_size_pt': 22,
        'alignment': 'CENTER',
        'outline_level': 0,             # 用于 TOC
    },
    'TITLE_L1': {
        'word_style': 'Heading 1',
        'font_name': '黑体',
        'font_size_pt': 16,
        'alignment': 'LEFT',
        'first_line_indent_chars': 2,  # 首行缩进两字
        'outline_level': 1,
    },
    'CHAPTER': {
        'word_style': 'Heading 1',     # 章节用标题1
        'font_name': '黑体',
        'font_size_pt': 16,
        'alignment': 'CENTER',
        'first_line_indent_chars': 0,
        'outline_level': 1,
    },
    'TITLE_L2': {
        'word_style': 'Heading 2',
        'font_name': '楷体_GB2312',
        'font_size_pt': 16,
        'alignment': 'LEFT',
        'first_line_indent_chars': 2,  # 首行缩进两字
        'outline_level': 2,
    },
    'TITLE_L3': {
        'word_style': 'Heading 3',
        'font_name': '楷体_GB2312',
        'font_size_pt': 16,
        'alignment': 'LEFT',
        'first_line_indent_chars': 2,  # 首行缩进两字
        'outline_level': 3,
    },
    'SALUTATION': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'LEFT',
        'first_line_indent_chars': 0,
    },
    'TEXT_BODY': {
        'word_style': 'Normal',        # 正文用 Normal 样式
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'JUSTIFY',
        'first_line_indent_chars': 2,  # 首行缩进两字
        'line_spacing_pt': 28,
        'keep_with_next': True,
    },
    'CONCLUSION': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'CENTER',
        'space_before_pt': 8,
    },
    'SIGNATURE_NAME': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'RIGHT',
        'right_indent_chars': 2,       # 右空两字
    },
    'SIGNATURE_DATE': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'RIGHT',
        'right_indent_chars': 4,       # 严格右空四字
    },
    'DOC_NUMBER': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'CENTER',
        'first_line_indent_chars': 0,
    },
    'LIST_ITEM': {
        'word_style': 'List Bullet',
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'JUSTIFY',
        'line_spacing_pt': 28,
        'keep_with_next': True,
    },
    'CC_UNIT': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'LEFT',
    },
    'PUBLISHER_INFO': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'RIGHT',
    },
    'THEME_KEYWORD': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'LEFT',
    },
    'ATTACHMENT': {
        'word_style': None,
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'LEFT',
    },
    'UNKNOWN': {
        'word_style': 'Normal',
        'font_name': '仿宋_GB2312',
        'font_size_pt': 16,
        'alignment': 'LEFT',
        'first_line_indent_chars': 2,
    },
}


class DFGPManager:
    """
    文档格式基因图谱 (DFGP) 管理器
    
    设计原则：配置与计算分离
    - DFGP 配置是声明式的（声明"右空几字"、"首行缩进几字符"）
    - 计算能力由管理器提供（动态换算为 Twips）
    - 即使临时修改正文字号，缩进也会自动随之缩放
    
    对外暴露的计算能力：
    - calculate_right_indent(chars, font_size_pt): 动态计算右侧缩进
    - calculate_first_line_indent(chars, font_size_pt): 动态计算首行缩进
    """
    
    def __init__(self, yaml_path: Optional[str] = None):
        """
        初始化 DFGP 管理器
        
        Args:
            yaml_path: 可选 YAML 配置文件路径
        """
        if yaml_path and Path(yaml_path).exists():
            self.config = self._load_from_yaml(yaml_path)
            logger.info(f"从 {yaml_path} 加载 DFGP 配置")
        else:
            # 使用 WORD_STYLE_MAPPING 作为默认配置
            self.config = self._build_config_from_style_mapping()
            logger.info("使用 WORD_STYLE_MAPPING 默认配置（纯样式方案）")
        
        # GB/T 9704-2012 页面边距
        self.page_margin = PageMargin.from_cm(
            top_cm=3.7,
            bottom_cm=3.5,
            left_cm=2.8,
            right_cm=2.6
        )
        
        # 验证配置
        self._validate_config()
    
    def _build_config_from_style_mapping(self) -> Dict:
        """从 WORD_STYLE_MAPPING 构建配置字典"""
        config = {}
        for label, params in WORD_STYLE_MAPPING.items():
            config[label] = dict(params)
        return config
    
    def _load_from_yaml(self, yaml_path: str) -> Dict:
        """从 YAML 文件加载配置"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data.get('dfgp', data)
    
    def _validate_config(self) -> None:
        """验证配置完整性"""
        required_labels = ['MAIN_TITLE', 'TITLE_L1', 'TITLE_L2', 'TEXT_BODY', 
                           'SIGNATURE_NAME', 'SIGNATURE_DATE', 'DOC_NUMBER']
        for label in required_labels:
            if label not in self.config:
                logger.warning(f"缺少标签 {label}，将使用默认配置")
                self.config[label] = WORD_STYLE_MAPPING.get(label, {})
        
        # 验证必需字段
        for label, params in self.config.items():
            if 'font_name' not in params and 'font_family' not in params:
                logger.warning(f"标签 '{label}' 缺少字体字段，将使用默认值")
    
    def get_style_params(self, label: str) -> StyleParams:
        """
        获取标签对应的样式参数（已转换为 Twips）
        
        Args:
            label: 语义标签 (MAIN_TITLE, TEXT_BODY 等)
            
        Returns:
            StyleParams: 包含 Twips 值的样式参数
        """
        # 兜底逻辑
        base = self.config.get(label, self.config.get('UNKNOWN', WORD_STYLE_MAPPING['UNKNOWN']))
        
        # 记录未找到的标签
        if label not in self.config:
            logger.warning(f"标签 '{label}' 未在配置中找到，使用 UNKNOWN 兜底")
        
        # 统一使用 font_name 字段（WORD_STYLE_MAPPING 使用 font_name）
        font_family = base.get('font_name', base.get('font_family', '仿宋_GB2312'))
        font_size_pt = base.get('font_size_pt', 16)
        alignment = base.get('alignment', 'LEFT')
        word_style_name = base.get('word_style')
        
        # 动态计算字符缩进
        first_line_indent_twips = None
        if 'first_line_indent_chars' in base:
            chars = base['first_line_indent_chars']
            first_line_indent_twips = self._chars_to_twips(chars, font_size_pt)
        elif 'first_line_indent_twips' in base:
            first_line_indent_twips = base['first_line_indent_twips']
        
        # 动态计算右侧缩进（落款右空两字）
        right_indent_twips = None
        if 'right_indent_chars' in base:
            chars = base['right_indent_chars']
            right_indent_twips = self._chars_to_twips(chars, font_size_pt)
        elif 'right_indent_twips' in base:
            right_indent_twips = base['right_indent_twips']
        
        # 行距
        line_spacing_twips = None
        if 'line_spacing_pt' in base:
            line_spacing_twips = self._pt_to_twips(base['line_spacing_pt'])
        elif 'line_spacing_twips' in base:
            line_spacing_twips = base['line_spacing_twips']
        
        # 间距
        space_before_twips = self._pt_to_twips(base.get('space_before_pt', 0))
        space_after_twips = self._pt_to_twips(base.get('space_after_pt', 0))
        
        return StyleParams(
            font_family=font_family,
            font_size_pt=font_size_pt,
            alignment=alignment,
            first_line_indent_twips=first_line_indent_twips,
            right_indent_twips=right_indent_twips,
            line_spacing_twips=line_spacing_twips,
            space_before_twips=space_before_twips,
            space_after_twips=space_after_twips,
            word_style_name=word_style_name,
            keep_with_next=base.get('keep_with_next', False),
            page_break_before=base.get('page_break_before', False),
            outline_level=base.get('outline_level')
        )
    
    def calculate_right_indent(self, chars: int, font_size_pt: float) -> int:
        """
        动态计算右侧缩进（"右空X字"）
        
        计算公式: Twips = 字符数 × 字号(pt) × 20
        
        Args:
            chars: 字符数
            font_size_pt: 当前字号（磅值）
            
        Returns:
            int: Twips 值
        """
        if chars < 0 or font_size_pt < 0:
            raise ValueError(f"字符数和字号不能为负: chars={chars}, font_size_pt={font_size_pt}")
        return int(chars * font_size_pt * 20)
    
    def _pt_to_twips(self, pt: float) -> int:
        """磅值转 Twips (1pt = 20 Twips)"""
        return int(pt * 20)
    
    def _chars_to_twips(self, chars: float, font_size_pt: float) -> int:
        """
        字符数转 Twips
        
        计算公式: Twips = 字符数 × 字号(pt) × 20
        
        Args:
            chars: 字符数（可以是小数）
            font_size_pt: 字号（磅值）
            
        Returns:
            Twips 值
        """
        if chars < 0 or font_size_pt < 0:
            raise ValueError(f"字符数和字号不能为负: chars={chars}, font_size_pt={font_size_pt}")
        return int(chars * font_size_pt * 20)
    
    def get_all_labels(self) -> List[str]:
        """获取所有可用标签"""
        return list(self.config.keys())
    
    def __repr__(self) -> str:
        return f"DFGPManager(labels={len(self.config)})"


# === 便捷函数 ===

def load_gb9704() -> DFGPManager:
    """加载 GB/T 9704-2012 标准配置"""
    return DFGPManager()


def get_style(label: str) -> StyleParams:
    """一行代码获取样式参数"""
    manager = DFGPManager()
    return manager.get_style_params(label)
