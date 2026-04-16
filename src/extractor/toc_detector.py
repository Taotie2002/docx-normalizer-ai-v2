"""
TocDetector - 目录检测器
Phase 2 扩展模块

功能：
1. 检测文档是否包含目录
2. 记录目录的起始/结束位置
3. 为后续目录生成提供元数据
"""

import re
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = __import__('logging').getLogger(__name__)


@dataclass
class TocInfo:
    """目录元数据"""
    has_toc: bool = False          # 是否包含目录
    start_idx: int = -1            # 目录起始段落索引
    end_idx: int = -1              # 目录结束段落索引
    title_page_count: int = 0      # 主送机关前首页数量
    
    def to_dict(self):
        return {
            'has_toc': self.has_toc,
            'start_idx': self.start_idx,
            'end_idx': self.end_idx,
            'title_page_count': self.title_page_count
        }


class TocDetector:
    """
    目录检测器
    
    检测逻辑：
    1. "目录"单独成行
    2. 通常在主副标题之后、一级标题之前
    3. 单独成页
    """
    
    # 目录标题正则
    RE_TOC_TITLE = re.compile(r'^[\s\u3000]*目[\s\u3000]*录[\s\u3000]*$', re.IGNORECASE)
    
    # 一级标题特征
    RE_HEADING_L1 = re.compile(r'^(第[一二三四五六七八九十]+章|一[、．.．])')
    
    # 目录结束标记（常见表达）
    RE_TOC_END = re.compile(r'^[\s\u3000]*第[一二三四五六七八九十]+章')
    
    def detect(self, blocks: List) -> TocInfo:
        """
        检测文档中的目录
        
        Args:
            blocks: DocumentIRBlock 列表
            
        Returns:
            TocInfo: 目录元数据
        """
        toc_info = TocInfo()
        
        if not blocks:
            return toc_info
        
        # 查找"目录"标题
        toc_title_idx = -1
        for i, block in enumerate(blocks):
            text = block.text.strip()
            if self.RE_TOC_TITLE.match(text):
                toc_title_idx = i
                logger.info(f"[TocDetector] 发现目录标题 at idx={i}: {text}")
                break
        
        if toc_title_idx == -1:
            logger.info("[TocDetector] 未发现目录")
            return toc_info
        
        toc_info.has_toc = True
        toc_info.start_idx = toc_title_idx
        
        # 查找目录结束位置
        # 策略：从"目录"之后向前查找第一个一级标题或超过5个段落
        end_idx = self._find_toc_end(blocks, toc_title_idx)
        toc_info.end_idx = end_idx
        
        # 估算首页数量（目录前的段落数）
        toc_info.title_page_count = toc_title_idx
        
        logger.info(f"[TocDetector] 目录范围: idx {toc_info.start_idx} - {toc_info.end_idx}")
        
        return toc_info
    
    def _find_toc_end(self, blocks: List, start_idx: int) -> int:
        """
        查找目录结束位置
        
        策略：
        1. 从start_idx之后查找第一个"第X章"或"一、"格式（一级标题）
        2. 如果找不到，使用固定阈值（最多20个段落）
        """
        max_toc_paragraphs = 20  # 目录最多20段
        
        for i in range(start_idx + 1, min(start_idx + max_toc_paragraphs, len(blocks))):
            text = blocks[i].text.strip()
            
            # 遇到一级标题，认为目录结束
            if self.RE_TOC_END.match(text):
                logger.info(f"[TocDetector] 目录结束于 idx={i}: {text[:30]}")
                return i - 1  # 结束于一级标题之前
            
            # 检查是否是主送机关（可能插在目录和正文之间）
            if self._is_main_body_start(text):
                logger.info(f"[TocDetector] 目录结束于 idx={i} (主送机关): {text[:30]}")
                return i - 1
        
        # 默认：目录最多20段
        default_end = min(start_idx + max_toc_paragraphs, len(blocks) - 1)
        logger.info(f"[TocDetector] 目录使用默认结束 idx={default_end}")
        return default_end
    
    def _is_main_body_start(self, text: str) -> bool:
        """
        判断是否正文开始（主送机关行）
        """
        if not text:
            return False
        
        # 主送机关行特征：以冒号结尾，含政府/局等关键词
        if text.endswith('：'):
            keywords = ['政府', '办公室', '委员会', '厅', '局', '部', '处', '公司', '医院', '学校']
            return any(kw in text for kw in keywords)
        
        return False
    
    def extract_toc_blocks(self, blocks: List) -> List:
        """
        提取目录段落（用于后续参考）
        """
        toc_info = self.detect(blocks)
        
        if not toc_info.has_toc:
            return []
        
        return blocks[toc_info.start_idx:toc_info.end_idx + 1]
    
    def get_non_toc_blocks(self, blocks: List) -> List:
        """
        获取不含目录的文档块
        """
        toc_info = self.detect(blocks)
        
        if not toc_info.has_toc:
            return blocks
        
        # 返回目录之前的部分 + 目录之后的部分
        before_toc = blocks[:toc_info.start_idx]
        after_toc = blocks[toc_info.end_idx + 1:]
        
        return before_toc + after_toc
