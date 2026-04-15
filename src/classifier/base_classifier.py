"""
Base Classifier - 基础分类器
SRS-2026-002 V11.2 | Phase 2

混合分类策略：
- L1 Rule: 正则匹配（标题、日期等）
- L3 Spatial: 位置推断（前10%标题区，后15%落款区）
- Fallback: 兜底为正文
"""

import re
from typing import List, Optional
from dataclasses import dataclass
import logging

from src.core.ir_block import DocumentIRBlock, BlockLabel
from src.core.exceptions import ClassificationError

logger = logging.getLogger(__name__)


@dataclass
class ClassifierConfig:
    """分类器配置"""
    # 空间位置阈值
    title_zone_ratio: float = 0.10   # 前10%为标题区
    signature_zone_ratio: float = 0.85  # 后15%为落款区
    
    # 文本长度阈值
    short_text_threshold: int = 30    # 短文本阈值
    very_short_threshold: int = 25    # 极短文本阈值
    
    # 置信度
    rule_confidence: float = 1.0
    spatial_confidence: float = 0.8
    fallback_confidence: float = 0.6


class RuleSpatialClassifier:
    """
    L1(Rule) + L3(Spatial) 混合分类器
    
    特点：
    - 无需 LLM，纯规则判断
    - 优先级：Rule > Spatial > Fallback
    - 输出：原地更新 DocumentIRBlock 的 label 字段
    """
    
    def __init__(self, config: Optional[ClassifierConfig] = None):
        """
        初始化分类器
        
        Args:
            config: 可选配置，默认使用 GB/T 9704 标准
        """
        self.config = config or ClassifierConfig()
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """编译常用正则表达式"""
        # 一级标题：一、二、三、...
        self.re_heading_1 = re.compile(
            r'^[一二三四五六七八九十]+、'
        )
        
        # 二级标题：（一）、（二）、...
        self.re_heading_2 = re.compile(
            r'^（[一二三四五六七八九十]+）'
        )
        
        # 三级标题：1.1、1.1.1（纯数字点号）
        self.re_heading_3 = re.compile(r'^\d+\.\d+(?:\.\d+)?$')

        # 签发人：签发人：xxx
        self.re_issuer = re.compile(r'^签发人：.+')

        # 发文号：xxx〔2024〕xxx号
        self.re_document_number = re.compile(r'^.*〔\d{4}〕.*号$')

        # 附件说明：附件：或附件1：
        self.re_attachment = re.compile(r'^附件[：:\s]')

        # 抄送单位：抄送：xxx
        self.re_cc_unit = re.compile(r'^抄送：.+')

        # 印发机关和日期：xxx 2024年1月1日印发
        self.re_publisher = re.compile(r'^\S+\s+\d{4}年\d{1,2}月\d{1,3}日印发$')

        # 主题词：主题词：xxx
        self.re_theme_keyword = re.compile(r'^主题词：.+')
        
        # 日期行：XXXX年XX月XX日
        self.re_date_line = re.compile(
            r'^[*\u4e00-\u9fa5]{2,4}年[\u4e00-\u9fa5]{1,2}月[\u4e00-\u9fa5]{1,3}日$'
        )
        
        # 结语关键词
        self.re_conclusion = re.compile(
            r'^(妥否|请批示|请审阅|请审核|以上如无不妥)'
        )
        
        # 主标题特征：前两段、简短、含"关于"
        self.re_main_title = re.compile(
            r'^关于'
        )
        
        logger.debug("[Classifier] 正则表达式已编译")
    
    def process(self, blocks: List[DocumentIRBlock]) -> List[DocumentIRBlock]:
        """
        处理 IR Block 序列，原地更新 label 字段
        
        Args:
            blocks: IR Block 序列
            
        Returns:
            更新后的 IR Block 序列
        """
        if not blocks:
            return blocks
        
        total_blocks = len(blocks)
        
        logger.info(f"[Classifier] 开始分类，共 {total_blocks} 个 Block")
        
        try:
            for block in blocks:
                self._classify_block(block, total_blocks)
            
            # 统计结果
            stats = self._count_labels(blocks)
            logger.info(f"[Classifier] 分类完成: {stats}")
            
        except Exception as e:
            raise ClassificationError(f"分类失败: {e}") from e
        
        return blocks
    
    def _classify_block(self, block: DocumentIRBlock, total_blocks: int) -> None:
        """
        分类单个 Block
        
        Args:
            block: IR Block
            total_blocks: 总段落数（用于计算位置）
        """
        text = block.text.strip()
        
        if not text:
            block.label = BlockLabel.UNKNOWN
            block.classifier_source = "FALLBACK"
            block.confidence = 0.0
            return
        
        position_ratio = block.source_para_idx / max(total_blocks - 1, 1)
        
        # ========== L1: 规则判断（最高优先级）==========
        
        # 一级标题：一、二、三、...
        if self._is_heading_1(text):
            block.label = BlockLabel.TITLE_L1
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 一级标题: {text[:20]}")
            return
        
        # 二级标题：（一）、（二）、...
        if self._is_heading_2(text):
            block.label = BlockLabel.TITLE_L2
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 二级标题: {text[:20]}")
            return
        
        # 签发人
        if self._is_issuer(text):
            block.label = BlockLabel.SIGNATURE
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 签发人: {text}")
            return

        # 发文号
        if self._is_document_number(text):
            block.label = BlockLabel.TEXT_BODY
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 发文号: {text}")
            return

        # 附件说明
        if self._is_attachment(text):
            block.label = BlockLabel.ATTACHMENT
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 附件说明: {text}")
            return

        # 抄送单位
        if self._is_cc_unit(text):
            block.label = BlockLabel.CC_UNIT
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 抄送单位: {text}")
            return

        # 印发机关和日期
        if self._is_publisher(text):
            block.label = BlockLabel.PUBLISHER_INFO
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 印发机关和日期: {text}")
            return

        # 主题词
        if self._is_theme_keyword(text):
            block.label = BlockLabel.THEME_KEYWORD
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 主题词: {text}")
            return

        # 日期行
        if self._is_date_line(text):
            block.label = BlockLabel.SIGNATURE  # 日期行归属落款
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 日期行: {text}")
            return
        
        # 结语
        if self._is_conclusion(text):
            block.label = BlockLabel.CONCLUSION
            block.classifier_source = "RULE"
            block.confidence = self.config.rule_confidence
            logger.debug(f"[L1] 结语: {text[:20]}")
            return
        
        # ========== L3: 空间位置辅助 ==========
        
        # 标题区（前10%）
        if position_ratio <= self.config.title_zone_ratio:
            if self._is_salutation(text):
                block.label = BlockLabel.SALUTATION
                block.classifier_source = "SPATIAL"
                block.confidence = self.config.spatial_confidence
            elif len(text) < self.config.very_short_threshold:
                block.label = BlockLabel.MAIN_TITLE
                block.classifier_source = "SPATIAL"
                block.confidence = self.config.spatial_confidence
                logger.debug(f"[L3] 主标题(位置): {text[:20]}")
            else:
                # 短文本但不在标题区，可能是正文标题
                block.label = BlockLabel.TEXT_BODY
                block.classifier_source = "SPATIAL"
                block.confidence = self.config.spatial_confidence
            return
        
        # 落款区（后15%）
        if position_ratio >= self.config.signature_zone_ratio:
            if self._is_signature(text):
                block.label = BlockLabel.SIGNATURE
                block.classifier_source = "SPATIAL"
                block.confidence = self.config.spatial_confidence
                logger.debug(f"[L3] 落款(位置): {text[:20]}")
                return
        
        # ========== Fallback: 正文 ==========
        
        block.label = BlockLabel.TEXT_BODY
        block.classifier_source = "FALLBACK"
        block.confidence = self.config.fallback_confidence
    
    def _is_heading_1(self, text: str) -> bool:
        """判断是否一级标题：一、二、三、..."""
        return (
            self.re_heading_1.match(text) is not None
            and len(text) < self.config.short_text_threshold
        )
    
    def _is_heading_2(self, text: str) -> bool:
        """判断是否二级标题：（一）、（二）..."""
        return (
            self.re_heading_2.match(text) is not None
            and len(text) < self.config.short_text_threshold + 10
        )
    
    def _is_date_line(self, text: str) -> bool:
        """判断是否日期行"""
        return self.re_date_line.match(text) is not None
    
    def _is_conclusion(self, text: str) -> bool:
        """判断是否结语"""
        return self.re_conclusion.search(text) is not None

    def _is_issuer(self, text: str) -> bool:
        """判断是否签发人"""
        return self.re_issuer.match(text) is not None

    def _is_document_number(self, text: str) -> bool:
        """判断是否发文号"""
        return self.re_document_number.match(text) is not None

    def _is_attachment(self, text: str) -> bool:
        """判断是否附件说明"""
        return self.re_attachment.match(text) is not None

    def _is_cc_unit(self, text: str) -> bool:
        """判断是否抄送单位"""
        return self.re_cc_unit.match(text) is not None

    def _is_publisher(self, text: str) -> bool:
        """判断是否印发机关和日期"""
        return self.re_publisher.match(text) is not None

    def _is_theme_keyword(self, text: str) -> bool:
        """判断是否主题词"""
        return self.re_theme_keyword.match(text) is not None
    
    def _is_salutation(self, text: str) -> bool:
        """判断是否称谓行"""
        return (
            text.startswith('尊敬的') 
            or ('：' in text and len(text) < 30)
            or text.endswith('：')
        )
    
    def _is_signature(self, text: str) -> bool:
        """判断是否落款"""
        # 包含机构名称关键词或日期
        signature_keywords = ['局', '办公室', '委员会', '中心', '厅', '部', '办公室']
        return (
            any(kw in text for kw in signature_keywords)
            or self.re_date_line.search(text) is not None
        )
    
    def _count_labels(self, blocks: List[DocumentIRBlock]) -> dict:
        """统计各标签数量"""
        counts = {}
        for b in blocks:
            counts[b.label] = counts.get(b.label, 0) + 1
        return counts


# === 便捷函数 ===

def classify_blocks(blocks: List[DocumentIRBlock]) -> List[DocumentIRBlock]:
    """
    一行代码分类 IR Block 序列
    
    Args:
        blocks: IR Block 序列
        
    Returns:
        分类后的序列
    """
    classifier = RuleSpatialClassifier()
    return classifier.process(blocks)
