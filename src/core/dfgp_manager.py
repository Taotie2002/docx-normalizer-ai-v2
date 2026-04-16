"""
DFGP Manager - 文档格式基因图谱管理器
SRS-2026-002 V11.2 | Phase 2

职责：
1. 加载 DFGP YAML 配置
2. 根据 label 输出格式参数
3. 动态计算 Twips 值（字符缩进、行距等）
4. 支持 GB/T 9704-2012 公文格式标准
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
    """样式参数（Twips 单位）"""
    font_family: str
    font_size_pt: int  # 磅值（用于计算 w:sz 半磅）
    font_size_twips: int
    alignment: str  # LEFT, CENTER, RIGHT, JUSTIFY
    
    # 段落格式
    first_line_indent_twips: Optional[int] = None
    right_indent_twips: Optional[int] = None
    line_spacing_twips: Optional[int] = None
    space_before_twips: int = 0
    space_after_twips: int = 0
    
    # 分页控制
    keep_with_next: bool = False
    page_break_before: bool = False
    outline_level: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "font_family": self.font_family,
            "font_size_pt": self.font_size_pt,
            "font_size_twips": self.font_size_twips,
            "alignment": self.alignment,
            "first_line_indent_twips": self.first_line_indent_twips,
            "right_indent_twips": self.right_indent_twips,
            "line_spacing_twips": self.line_spacing_twips,
            "keep_with_next": self.keep_with_next,
            "page_break_before": self.page_break_before,
            "outline_level": self.outline_level
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
    
    GB/T 9704-2012 公文格式标准预设配置：
    - 主标题：方正小标宋简体 22pt 居中
    - 一级标题：黑体 16pt
    - 二级标题：楷体_GB2312 16pt
    - 正文：仿宋_GB2312 16pt 首行缩进32pt
    - 落款：仿宋_GB2312 16pt 右空两字
    """
    
    # GB/T 9704-2012 默认配置
    DEFAULT_CONFIG = {
        "MAIN_TITLE": {
            "font_family": "方正小标宋简体",
            "font_size_pt": 22,  # 二号
            "alignment": "CENTER",
            "space_after_pt": 8,
            "outline_level": 0
        },
        "TITLE_L1": {
            "font_family": "黑体",
            "font_size_pt": 16,
            "alignment": "LEFT",
            "first_line_indent_chars": 2,
            "outline_level": 1
        },
        # 章节标题（第X章）：黑体22pt居中无缩进
        "CHAPTER": {
            "font_family": "黑体",
            "font_size_pt": 22,
            "alignment": "CENTER",
            "first_line_indent_chars": 0,
            "outline_level": 1
        },
        "TITLE_L2": {
            "font_family": "楷体_GB2312",
            "font_size_pt": 16,
            "alignment": "LEFT",
            "first_line_indent_chars": 2,
            "outline_level": 2
        },
        "TITLE_L3": {
            "font_family": "楷体_GB2312",
            "font_size_pt": 16,
            "alignment": "LEFT",
            "first_line_indent_chars": 2,
            "outline_level": 3
        },
        "SALUTATION": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "LEFT",
            "first_line_indent_chars": 0  # 称谓行无缩进
        },
        "TEXT_BODY": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "JUSTIFY",
            "first_line_indent_chars": 2,  # 首行缩进两字
            "line_spacing_pt": 28,
            "keep_with_next": True
        },
        "CONCLUSION": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "CENTER",
            "space_before_pt": 8
        },
        # 落款分两级：署名 + 成文日期
        "SIGNATURE_NAME": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "RIGHT",
            "right_indent_chars": 2  # 右空两字
        },
        "SIGNATURE_DATE": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "RIGHT",
            "right_indent_chars": 4  # 成文日期严格右空四字
        },
        # 文号（合政办〔2017〕1号）：居中、仿宋、无缩进
        "DOC_NUMBER": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "CENTER",
            "first_line_indent_chars": 0
        },
        "LIST_ITEM": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "JUSTIFY",
            "line_spacing_pt": 28,
            "keep_with_next": True
        },
        "UNKNOWN": {
            "font_family": "仿宋_GB2312",
            "font_size_pt": 16,
            "alignment": "LEFT",
            "first_line_indent_chars": 2  # 兜底也首行缩进两字
        }
    }
    
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
            self.config = self.DEFAULT_CONFIG.copy()
            logger.info("使用 GB/T 9704-2012 默认配置")
        
        # GB/T 9704-2012 页面边距
        self.page_margin = PageMargin.from_cm(
            top_cm=3.7,
            bottom_cm=3.5,
            left_cm=2.8,
            right_cm=2.6
        )
        
        # 验证配置
        self._validate_config()
    
    def _load_from_yaml(self, yaml_path: str) -> Dict:
        """从 YAML 文件加载配置"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data.get('dfgp', data)
    
    def _validate_config(self) -> None:
        """验证配置完整性"""
        required_labels = ['MAIN_TITLE', 'TITLE_L1', 'TITLE_L2', 'TEXT_BODY', 'SIGNATURE_NAME', 'SIGNATURE_DATE', 'DOC_NUMBER']
        for label in required_labels:
            if label not in self.config:
                logger.warning(f"缺少标签 {label}，将使用默认配置")
                self.config[label] = self.DEFAULT_CONFIG.get(label, {})
        
        # 验证字符缩进字段一致性
        for label, params in self.config.items():
            if 'first_line_indent_chars' in params and 'first_line_indent_twips' in params:
                logger.warning(f"标签 '{label}' 同时定义了字符和Twips缩进，可能存在冲突")
        
        # 验证必需字段
        for label, params in self.config.items():
            if 'font_family' not in params:
                logger.error(f"标签 '{label}' 缺少必需字段 font_family")
            if 'font_size_pt' not in params and 'font_size_twips' not in params:
                logger.error(f"标签 '{label}' 缺少字体大小字段 (font_size_pt 或 font_size_twips)")
    
    def get_style_params(self, label: str) -> StyleParams:
        """
        获取标签对应的样式参数（已转换为 Twips）
        
        Args:
            label: 语义标签 (MAIN_TITLE, TEXT_BODY 等)
            
        Returns:
            StyleParams: 包含 Twips 值的样式参数
        """
        # 兜底逻辑
        base = self.config.get(label, self.config.get('UNKNOWN', self.DEFAULT_CONFIG['UNKNOWN']))
        
        # 记录未找到的标签
        if label not in self.config:
            logger.warning(f"标签 '{label}' 未在配置中找到，使用 UNKNOWN 兜底")
        
        # 基础值
        font_family = base.get('font_family', '仿宋_GB2312')
        font_size_pt = base.get('font_size_pt', 16)
        font_size_twips = self._pt_to_twips(font_size_pt)
        alignment = base.get('alignment', 'LEFT')
        
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
            font_size_twips=font_size_twips,
            alignment=alignment,
            first_line_indent_twips=first_line_indent_twips,
            right_indent_twips=right_indent_twips,
            line_spacing_twips=line_spacing_twips,
            space_before_twips=space_before_twips,
            space_after_twips=space_after_twips,
            keep_with_next=base.get('keep_with_next', False),
            page_break_before=base.get('page_break_before', False),
            outline_level=base.get('outline_level')
        )
    
    def calculate_right_indent(self, chars: int, font_size_pt: float) -> int:
        """
        动态计算右侧缩进（"右空X字"）
        
        这是对外暴露的计算能力，使得 DFGP 配置可以保持声明式（chars），
        而计算结果由管理器在运行时动态生成。
        
        计算公式: Twips = 字符数 × 字号(pt) × 20
        
        Args:
            chars: 字符数（如 2 表示"右空两字"）
            font_size_pt: 当前字号（磅值）
            
        Returns:
            int: Twips 值
            
        Example:
            calculate_right_indent(chars=4, font_size_pt=22)  # 主标题22pt右空4字
            # 返回: 4 × 22 × 20 = 1760 Twips
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
        - GB/T 标准：每字约等于当前字号
        - 2字符缩进 = 2 × 16pt × 20 = 640 Twips
        
        Args:
            chars: 字符数（可以是小数）
            font_size_pt: 字号（磅值）
            
        Returns:
            Twips 值
        """
        # 防止负数输入
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