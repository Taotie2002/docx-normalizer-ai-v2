"""
V-03 零丢失验证器
SRS-2026-002 V11.2

实现三重验证机制：
1. 完整字符串 Hash 比对
2. Token 级 Diff 扫描
3. 结构顺序比对 (source_para_idx)
"""

import hashlib
import difflib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

from src.core.ir_block import DocumentIRBlock
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class V03ValidationResult:
    """V-03 验证结果"""
    # 三重验证结果
    hash_match: bool
    token_diff_count: int
    sequence_valid: bool
    
    # 详细信息
    raw_text_hash: str
    rebuilt_text_hash: str
    raw_total_chars: int
    rebuilt_total_chars: int
    
    # Diff 详情
    token_diffs: List[Dict]  # [{idx, raw, rebuilt, diff_type}]
    
    # 序列详情
    sequence_errors: List[str]
    
    # 最终判定
    is_pass: bool
    failure_mode: str  # ALL_PASS | PARTIAL_FAIL | ALL_FAIL
    
    def summary(self) -> str:
        return (
            f"V-03 Validation: {self.failure_mode}\n"
            f"  Hash: {'✅' if self.hash_match else '❌'} "
            f"(raw={self.raw_text_hash[:8]}, rebuilt={self.rebuilt_text_hash[:8]})\n"
            f"  Token Diff: {'✅' if self.token_diff_count == 0 else '⚠️'} "
            f"({self.token_diff_count} 处差异)\n"
            f"  Sequence: {'✅' if self.sequence_valid else '❌'}\n"
            f"  Final: {'PASS' if self.is_pass else 'FAIL'}"
        )


class V03Validator:
    """
    V-03 零丢失验证器
    
    三重验证机制：
    1. Hash 比对：完整字符串的 SHA-256 Hash
    2. Token Diff：字形级差异扫描
    3. Sequence：source_para_idx 严格递增
    """
    
    # 允许的差异类型（不计入失败）
    ALLOWED_DIFF_TYPES = frozenset({
        'whitespace_normalization',  # 空白符规范化（如多个空格合并）
        'lineEnding_normalization',  # 换行符规范化（CRLF → LF）
    })
    
    # 致命差异类型（计入 ALL_FAIL）
    FATAL_DIFF_TYPES = frozenset({
        'char_missing',      # 字符丢失
        'char_added',       # 字符增加（非原文内容）
        'char_substituted', # 字符替换（非空白差异）
    })
    
    def __init__(self, tolerance: int = 0):
        """
        初始化验证器
        
        Args:
            tolerance: Token Diff 容差（默认 0，不允许差异）
        """
        self.tolerance = tolerance
    
    def validate(
        self,
        raw_blocks: List[DocumentIRBlock],
        rebuilt_blocks: List[DocumentIRBlock]
    ) -> V03ValidationResult:
        """
        执行 V-03 三重验证
        
        Args:
            raw_blocks: 原始 IR Block 序列
            rebuilt_blocks: 重构后 IR Block 序列
            
        Returns:
            V03ValidationResult: 验证结果
        """
        # ============ Step 1: Hash 比对 ============
        raw_text = self._join_text(raw_blocks)
        rebuilt_text = self._join_text(rebuilt_blocks)
        
        raw_hash = self._compute_hash(raw_text)
        rebuilt_hash = self._compute_hash(rebuilt_text)
        hash_match = (raw_hash == rebuilt_hash)
        
        # ============ Step 2: Token 级 Diff ============
        token_diffs = self._scan_token_diff(raw_blocks, rebuilt_blocks)
        has_fatal_diff = any(
            d['diff_type'] in self.FATAL_DIFF_TYPES 
            for d in token_diffs
        )
        
        # ============ Step 3: 序列验证 ============
        sequence_errors = self._validate_sequence(raw_blocks)
        sequence_valid = len(sequence_errors) == 0
        
        # ============ 判定失败模式 ============
        if hash_match and not token_diffs and sequence_valid:
            failure_mode = "ALL_PASS"
            is_pass = True
        elif has_fatal_diff:
            failure_mode = "ALL_FAIL"
            is_pass = False
        else:
            failure_mode = "PARTIAL_FAIL"
            is_pass = (len(token_diffs) <= self.tolerance)
        
        result = V03ValidationResult(
            hash_match=hash_match,
            token_diff_count=len(token_diffs),
            sequence_valid=sequence_valid,
            raw_text_hash=raw_hash,
            rebuilt_text_hash=rebuilt_hash,
            raw_total_chars=len(raw_text),
            rebuilt_total_chars=len(rebuilt_text),
            token_diffs=token_diffs,
            sequence_errors=sequence_errors,
            is_pass=is_pass,
            failure_mode=failure_mode
        )
        
        logger.info(f"[V03] {result.summary()}")
        return result
    
    def _join_text(self, blocks: List[DocumentIRBlock]) -> str:
        """
        将 IR Block 序列合并为单一文本
        
        使用 U+0001 作为段分隔符，永远不会出现在正文中
        
        Args:
            blocks: IR Block 序列
            
        Returns:
            合并后的文本
        """
        SEP = "\u0001"  # ASCII SOH，从不用作正常文本
        return SEP.join(block.text for block in blocks)
    
    def _compute_hash(self, text: str) -> str:
        """
        计算文本的 SHA-256 Hash
        
        Args:
            text: 文本
            
        Returns:
            64位十六进制 Hash
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _scan_token_diff(
        self,
        raw_blocks: List[DocumentIRBlock],
        rebuilt_blocks: List[DocumentIRBlock]
    ) -> List[Dict]:
        """
        Token 级 Diff 扫描
        
        使用 difflib 进行字形级比对，识别：
        - 字符丢失/增加
        - 字符替换
        - 空白规范化
        
        Args:
            raw_blocks: 原始块
            rebuilt_blocks: 重构后块
            
        Returns:
            差异列表
        """
        diffs = []
        
        for idx, (raw, rebuilt) in enumerate(zip(raw_blocks, rebuilt_blocks)):
            raw_text = raw.text
            rebuilt_text = rebuilt.text
            
            if raw_text == rebuilt_text:
                continue
            
            # 使用 SequenceMatcher 进行字形级比对
            matcher = difflib.SequenceMatcher(None, raw_text, rebuilt_text)
            
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'equal':
                    continue
                
                if tag == 'replace':
                    # 字符替换
                    diffs.append({
                        'idx': idx,
                        'block_id': raw.block_id,
                        'raw_text': raw_text[max(0, i1-5):i2+5],
                        'rebuilt_text': rebuilt_text[max(0, j1-5):j2+5],
                        'diff_type': 'char_substituted'
                    })
                elif tag == 'delete':
                    # 字符丢失
                    diffs.append({
                        'idx': idx,
                        'block_id': raw.block_id,
                        'raw_text': raw_text[max(0, i1-5):i2+5],
                        'rebuilt_text': '',
                        'diff_type': 'char_missing'
                    })
                elif tag == 'insert':
                    # 字符增加
                    diffs.append({
                        'idx': idx,
                        'block_id': raw.block_id,
                        'raw_text': '',
                        'rebuilt_text': rebuilt_text[max(0, j1-5):j2+5],
                        'diff_type': 'char_added'
                    })
        
        return diffs
    
    def _validate_sequence(
        self, 
        blocks: List[DocumentIRBlock]
    ) -> List[str]:
        """
        验证 source_para_idx 序列是否严格递增
        
        Args:
            blocks: IR Block 序列
            
        Returns:
            错误列表
        """
        errors = []
        
        if not blocks:
            return errors
        
        # 检查连续性
        for i in range(1, len(blocks)):
            if blocks[i].source_para_idx <= blocks[i-1].source_para_idx:
                errors.append(
                    f"序列中断: block[{i}] source_para_idx="
                    f"{blocks[i].source_para_idx} <= "
                    f"block[{i-1}]={blocks[i-1].source_para_idx}"
                )
        
        return errors


# === 便捷函数 ===

def validate_zero_loss(
    raw_blocks: List[DocumentIRBlock],
    rebuilt_blocks: List[DocumentIRBlock]
) -> V03ValidationResult:
    """
    一行代码验证零丢失
    
    Args:
        raw_blocks: 原始块
        rebuilt_blocks: 重构后块
        
    Returns:
        V03ValidationResult
    """
    validator = V03Validator()
    return validator.validate(raw_blocks, rebuilt_blocks)
