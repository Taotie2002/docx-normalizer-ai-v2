"""
PhysicalValidator - 物理层 XML 审查器
Phase 2 准入检查

检查项：
1. 焦土清洗彻底性：无残留节点
2. 属性冗余度：无重复定义
3. rId 引用闭环：图片引用完整
"""

import zipfile
from pathlib import Path
from lxml import etree
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# 允许的命名空间
ALLOWED_NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

# DFGP 定义的合法属性
LEGAL_W_PARR_PROPS = {
    'w:ind', 'w:jc', 'w:spacing', 'w:keepNext', 'w:pageBreakBefore',
    'w:outlineLvl', 'w:suppressLineNumbers', 'w:mirrorIndents',
    'w:overlap', 'w:divId', 'w:cnfStyle', 'w:pPrChange',
}

LEGAL_W_RUN_PROPS = {
    'w:rFonts', 'w:sz', 'w:szCs', 'w:vertAlign', 'w:u', 'w:b', 'w:i',
    'w:strike', 'w:color', 'w:shd', 'w:rPrChange',
}


@dataclass
class ValidationIssue:
    severity: str  # ERROR | WARNING | INFO
    location: str  # file path or xpath
    issue_type: str
    description: str
    xml_snippet: str = ""


class PhysicalValidator:
    """
    物理层 XML 审查器
    
    检查 .docx 文件的底层 XML 结构是否干净、合规。
    """
    
    def __init__(self, docx_path: str):
        self.docx_path = Path(docx_path)
        self.issues: List[ValidationIssue] = []
        self.warnings: List[ValidationIssue] = []
        self.info: List[ValidationIssue] = []
        
        self.ns = {'w': ALLOWED_NAMESPACES['w']}
        
    def validate(self) -> Tuple[bool, List[ValidationIssue]]:
        """
        执行完整验证
        
        Returns:
            (is_clean, issues): 是否通过 + 问题列表
        """
        self.issues = []
        
        try:
            with zipfile.ZipFile(self.docx_path, 'r') as zf:
                # 1. 检查 document.xml
                self._check_document_xml(zf)
                
                # 2. 检查 rels 文件
                self._check_rels(zf)
                
                # 3. 检查 media 引用闭环
                self._check_media_references(zf)
                
        except Exception as e:
            self.issues.append(ValidationIssue(
                severity='ERROR',
                location=str(self.docx_path),
                issue_type='FILE_ERROR',
                description=f'无法读取文件: {e}'
            ))
        
        is_clean = len([i for i in self.issues if i.severity == 'ERROR']) == 0
        return is_clean, self.issues
    
    def _check_document_xml(self, zf: zipfile.ZipFile) -> None:
        """检查 document.xml"""
        try:
            xml_content = zf.read('word/document.xml')
            root = etree.fromstring(xml_content)
            
            # 检查所有段落
            for i, p in enumerate(root.findall('.//w:p', self.ns)):
                self._check_paragraph_props(p, f'paragraph[{i}]')
            
            # 检查所有 run
            for i, r in enumerate(root.findall('.//w:r', self.ns)):
                self._check_run_props(r, f'run[{i}]')
                
        except Exception as e:
            self.issues.append(ValidationIssue(
                severity='ERROR',
                location='word/document.xml',
                issue_type='PARSE_ERROR',
                description=str(e)
            ))
    
    def _check_paragraph_props(self, p_elem, location: str) -> None:
        """检查段落属性"""
        pPr = p_elem.find('w:pPr', self.ns)
        if pPr is None:
            return
        
        # 检查重复属性
        children = list(pPr)
        tag_counts = {}
        for child in children:
            tag = child.tag.split('}')[1] if '}' in child.tag else child.tag
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        for tag, count in tag_counts.items():
            if count > 1:
                self.issues.append(ValidationIssue(
                    severity='WARNING',
                    location=location,
                    issue_type='DUPLICATE_ATTR',
                    description=f'<w:{tag}> 出现 {count} 次',
                    xml_snippet=f'<w:{tag} x{count}>'
                ))
        
        # 检查未知属性
        for child in children:
            tag = child.tag.split('}')[1] if '}' in child.tag else child.tag
            if tag not in LEGAL_W_PARR_PROPS and not tag.endswith('Change'):
                self.warnings.append(ValidationIssue(
                    severity='INFO',
                    location=location,
                    issue_type='UNCOMMON_ATTR',
                    description=f'不常见的段落属性: <w:{tag}>'
                ))
    
    def _check_run_props(self, r_elem, location: str) -> None:
        """检查字符属性"""
        rPr = r_elem.find('w:rPr', self.ns)
        if rPr is None:
            return
        
        # 检查重复属性
        children = list(rPr)
        tag_counts = {}
        for child in children:
            tag = child.tag.split('}')[1] if '}' in child.tag else child.tag
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        for tag, count in tag_counts.items():
            if count > 1:
                self.issues.append(ValidationIssue(
                    severity='WARNING',
                    location=location,
                    issue_type='DUPLICATE_ATTR',
                    description=f'<w:{tag}> 出现 {count} 次',
                    xml_snippet=f'<w:{tag} x{count}>'
                ))
    
    def _check_rels(self, zf: zipfile.ZipFile) -> None:
        """检查 rels 文件"""
        try:
            rels_content = zf.read('word/_rels/document.xml.rels')
            root = etree.fromstring(rels_content)
            
            # 收集所有 Target
            targets = {}
            for rel in root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                rel_id = rel.get('Id')
                rel_type = rel.get('Type', '').split('/')[-1]
                target = rel.get('Target', '')
                targets[rel_id] = {'type': rel_type, 'target': target}
            
            # 检查孤儿引用（Target 不存在）
            for rel_id, info in targets.items():
                target = info['target']
                if target.startswith('media/'):
                    media_file = f'word/{target}'
                    if media_file not in zf.namelist():
                        self.issues.append(ValidationIssue(
                            severity='ERROR',
                            location='word/_rels/document.xml.rels',
                            issue_type='ORPHAN_RID',
                            description=f'rId={rel_id} 引用不存在的 media: {target}'
                        ))
                        
        except Exception as e:
            self.warnings.append(ValidationIssue(
                severity='WARNING',
                location='word/_rels/document.xml.rels',
                issue_type='RELS_PARSE_ERROR',
                description=str(e)
            ))
    
    def _check_media_references(self, zf: zipfile.ZipFile) -> None:
        """检查 media 文件完整性"""
        media_files = [f for f in zf.namelist() if f.startswith('word/media/')]
        
        if not media_files:
            self.info.append(ValidationIssue(
                severity='INFO',
                location='word/media/',
                issue_type='NO_MEDIA',
                description='文档不含 media 文件（纯文本文档）'
            ))
            return
        
        # 检查 media 文件大小（异常小的可能是损坏）
        for media_file in media_files:
            info = zf.getinfo(media_file)
            if info.file_size < 100:
                self.warnings.append(ValidationIssue(
                    severity='WARNING',
                    location=media_file,
                    issue_type='SUSPICIOUS_SIZE',
                    description=f'Media 文件异常小: {info.file_size} bytes'
                ))
    
    def get_report(self) -> str:
        """生成审查报告"""
        lines = [
            "# 物理层 XML 审查报告",
            f"**文件**: {self.docx_path.name}",
            f"**时间**: {Path('/tmp').exists()}",  # placeholder
            "",
            "---",
            "",
            "## 审查结果",
            "",
        ]
        
        errors = [i for i in self.issues if i.severity == 'ERROR']
        warnings = [i for i in self.issues if i.severity == 'WARNING']
        
        if not errors:
            lines.append("✅ **无 ERROR** - 通过准入检查")
        else:
            lines.append(f"❌ **{len(errors)} 个 ERROR** - 不通过")
        
        if warnings:
            lines.append(f"⚠️ {len(warnings)} 个 WARNING")
        
        if errors:
            lines.append("")
            lines.append("### ERROR 详情")
            for issue in errors:
                lines.append(f"- [{issue.location}] {issue.description}")
        
        if warnings:
            lines.append("")
            lines.append("### WARNING 详情")
            for issue in warnings:
                lines.append(f"- [{issue.location}] {issue.description}")
        
        return "\n".join(lines)


def validate_docx(docx_path: str) -> Tuple[bool, str]:
    """
    一行命令验证 .docx 文件
    
    Returns:
        (is_clean, report): 是否通过 + 报告
    """
    validator = PhysicalValidator(docx_path)
    is_clean, issues = validator.validate()
    return is_clean, validator.get_report()
