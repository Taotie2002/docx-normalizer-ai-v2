"""
SemanticCompiler - 语义重构编译器
SRS-2026-002 V11.2 | Phase 2

核心职责：
1. 根据 DocumentIRBlock 的 label，通过 DFGP 获取格式参数
2. 使用 lxml 穿透修改底层 w:pPr 节点（禁止仅依赖 python-docx 高级 API）
3. 向 w:ind 注入缩进、向 w:jc 注入对齐、向 w:rFonts 注入中文字体
4. 保持 V-03 零丢失验证

关键实现：
- _set_paragraph_xml(): 底层 XML 注入
- _set_font_xml(): 中文字体注入
- _compute_right_indent(): "右空X字"动态计算
"""

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import List, Optional
import logging

from src.core.ir_block import DocumentIRBlock
from src.core.dfgp_manager import DFGPManager, StyleParams
from src.core.exceptions import CompilationError
from src.extractor.toc_detector import TocInfo
from src.compiler.toc_generator import TocGenerator

logger = logging.getLogger(__name__)


class SemanticCompiler:
    """
    语义重构编译器
    
    使用 lxml 穿透修改底层 OOXML 节点，实现精确的格式控制。
    """
    
    def __init__(self, dfgp_manager: Optional[DFGPManager] = None):
        """
        初始化语义编译器
        
        Args:
            dfgp_manager: 可选 DFGP 管理器，默认使用 GB/T 9704 标准
        """
        self.doc = Document()
        self.dfgp = dfgp_manager or DFGPManager()
        
        # 设置默认页面边距（GB/T 9704）
        self._set_page_margins()
        
        logger.info("[SemanticCompiler] 初始化完成")
    
    def _set_page_margins(self) -> None:
        """设置页面边距（GB/T 9704-2012）"""
        section = self.doc.sections[0]._sectPr
        margin = self.dfgp.page_margin
        
        pgMar = OxmlElement('w:pgMar')
        pgMar.set(qn('w:top'), str(margin.top_twips))
        pgMar.set(qn('w:bottom'), str(margin.bottom_twips))
        pgMar.set(qn('w:left'), str(margin.left_twips))
        pgMar.set(qn('w:right'), str(margin.right_twips))
        pgMar.set(qn('w:header'), str(int(0.7 * 567)))  # 7mm
        pgMar.set(qn('w:footer'), str(int(0.7 * 567)))
        pgMar.set(qn('w:gutter'), '0')
        
        section.append(pgMar)
        logger.debug("[SemanticCompiler] 页面边距已设置")
    
    def build_from_ir(
        self, 
        ir_blocks: List[DocumentIRBlock], 
        output_path: str,
        toc_info: TocInfo = None
    ) -> None:
        """
        主循环：将 IR Block 序列重构为物理文档
        
        Args:
            ir_blocks: IR Block 序列
            output_path: 输出文件路径
            toc_info: 目录元数据（如有）
            
        Raises:
            CompilationError: 重构失败
        """
        if not ir_blocks:
            raise CompilationError("IR Block 序列为空")
        
        logger.info(f"[SemanticCompiler] 开始重构，共 {len(ir_blocks)} 个 Block")
        
        try:
            # 查找目录插入位置（如果有目录的话）
            toc_insert_idx = -1
            if toc_info and toc_info.has_toc:
                # 在主送机关行之后插入目录
                for i, block in enumerate(ir_blocks):
                    if block.label == 'SALUTATION':
                        toc_insert_idx = i + 1
                        break
            
            for i, block in enumerate(ir_blocks):
                self._process_block(block)
                
                # 在指定位置插入目录
                if i == toc_insert_idx and toc_info and toc_info.has_toc:
                    self._insert_toc(toc_info)
            
            self.doc.save(output_path)
            logger.info(f"[SemanticCompiler] 重构完成: {output_path}")
            
        except Exception as e:
            raise CompilationError(f"重构失败: {e}") from e
    
    def _insert_toc(self, toc_info: TocInfo) -> None:
        """
        插入目录（带分节符）
        
        Args:
            toc_info: 目录元数据
        """
        toc_gen = TocGenerator()
        toc_gen.insert_toc(self.doc, toc_info, insert_idx=0)
        logger.info("[SemanticCompiler] 目录已插入")
    
    def _process_block(self, block: DocumentIRBlock) -> None:
        """
        处理单个 IR Block
        
        步骤：
        1. 获取该标签的格式参数
        2. 创建段落并写入纯文本（去除前导空格）
        3. 注入字体、缩进、对齐等 XML 属性
        
        Args:
            block: IR Block
        """
        if not block.text:
            return
        
        # 去除前导空格（中文全角空格和ASCII空格）
        text = block.text.lstrip('\u3000 ')
        if not text:
            return
        
        # Step 1: 获取格式参数
        params = self.dfgp.get_style_params(block.label)
        
        # Step 2: 创建段落（不使用 add_heading，保持绝对控制）
        paragraph = self.doc.add_paragraph()
        run = paragraph.add_run(text)
        
        # Step 3: 设置中文字体（必须同时设置 w:rFonts/w:eastAsia）
        self._set_font_xml(run, params)
        
        # Step 4: 注入段落属性（缩进、对齐、行距等）
        self._set_paragraph_xml(paragraph, params)
    
    def _set_font_xml(self, run, params: StyleParams) -> None:
        """
        设置中文字体
        
        必须同时设置：
        - run.font.name（西文字体）
        - w:rFonts/w:eastAsia（中文字体）
        
        Args:
            run: python-docx Run 对象
            params: 样式参数
        """
        font_family = params.font_family
        
        # 方案1：直接修改 XML（更可靠）
        rPr = run._element.find(qn('w:rPr'))
        if rPr is None:
            rPr = OxmlElement('w:rPr')
            run._element.insert(0, rPr)
        
        # 查找或创建 rFonts
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = OxmlElement('w:rFonts')
            rPr.insert(0, rFonts)
        
        # 设置中文字体
        rFonts.set(qn('w:eastAsia'), font_family)
        
        # 规则4：字母和数字使用Times New Roman
        rFonts.set(qn('w:ascii'), 'Times New Roman')
        rFonts.set(qn('w:hAnsi'), 'Times New Roman')
        rFonts.set(qn('w:hint'), 'eastAsia')  # 提示引擎优先使用东亚字体
        
        # 设置字号 (w:sz 使用半磅单位，1pt=2半磅)
        sz = rPr.find(qn('w:sz'))
        if sz is None:
            sz = OxmlElement('w:sz')
            rPr.append(sz)
        sz.set(qn('w:val'), str(int(params.font_size_pt * 2)))
        
        # 设置 szCs（复杂文种字号）
        szCs = rPr.find(qn('w:szCs'))
        if szCs is None:
            szCs = OxmlElement('w:szCs')
            rPr.append(szCs)
        szCs.set(qn('w:val'), str(int(params.font_size_pt * 2)))
    
    def _set_paragraph_xml(self, paragraph, params: StyleParams) -> None:
        """
        核心：向段落节点注入底层 XML 属性
        
        必须注入的节点：
        - <w:ind>: 缩进（首行缩进、右缩进）
        - <w:jc>: 对齐方式
        - <w:spacing>: 行间距
        
        Args:
            paragraph: python-docx Paragraph 对象
            params: 样式参数
        """
        pPr = paragraph._p.find(qn('w:pPr'))
        if pPr is None:
            pPr = OxmlElement('w:pPr')
            paragraph._p.insert(0, pPr)
        
        # 1. 注入缩进节点 <w:ind>
        self._inject_indent(pPr, params)
        
        # 2. 注入对齐节点 <w:jc>
        self._inject_alignment(pPr, params)
        
        # 3. 注入行距节点 <w:spacing>
        self._inject_spacing(pPr, params)
        
        # 4. 注入分页控制
        self._inject_pagination(pPr, params)
    
    def _inject_indent(self, pPr, params: StyleParams) -> None:
        """
        注入 <w:ind> 节点
        
        支持：
        - w:firstLine: 首行缩进（Twips）
        - w:right: 右侧缩进（Twips），用于"右空X字"
        
        "右空X字" 计算逻辑：
        - 右侧缩进 Twips = X字符 × 字号(pt) × 20
        - 例如：落款右空2字 = 2 × 16pt × 20 = 640 Twips
        
        Args:
            pPr: <w:pPr> 节点
            params: 样式参数
        """
        # 检查是否已有 ind 节点
        existing_ind = pPr.find(qn('w:ind'))
        if existing_ind is not None:
            pPr.remove(existing_ind)
        
        # 判断是否需要缩进
        needs_indent = (
            params.first_line_indent_twips is not None
            or params.right_indent_twips is not None
        )
        
        if not needs_indent:
            return
        
        ind = OxmlElement('w:ind')
        
        # 首行缩进
        if params.first_line_indent_twips is not None:
            ind.set(qn('w:firstLine'), str(params.first_line_indent_twips))
        
        # 右侧缩进（"右空X字"）
        if params.right_indent_twips is not None:
            ind.set(qn('w:right'), str(params.right_indent_twips))
        
        pPr.append(ind)
        logger.debug(
            f"[XML] 缩进: firstLine={params.first_line_indent_twips}, "
            f"right={params.right_indent_twips}"
        )
    
    def _inject_alignment(self, pPr, params: StyleParams) -> None:
        """
        注入 <w:jc> 节点
        
        对齐方式映射：
        - LEFT → left
        - CENTER → center
        - RIGHT → right
        - JUSTIFY → both（两端对齐）
        
        Args:
            pPr: <w:pPr> 节点
            params: 样式参数
        """
        if not params.alignment:
            return
        
        # 检查是否已有 jc 节点
        existing_jc = pPr.find(qn('w:jc'))
        if existing_jc is not None:
            pPr.remove(existing_jc)
        
        # 对齐方式映射
        alignment_map = {
            'LEFT': 'left',
            'CENTER': 'center',
            'RIGHT': 'right',
            'JUSTIFY': 'both'  # 两端对齐
        }
        
        jc_val = alignment_map.get(params.alignment.upper())
        if not jc_val:
            return
        
        jc = OxmlElement('w:jc')
        jc.set(qn('w:val'), jc_val)
        pPr.append(jc)
        logger.debug(f"[XML] 对齐: {jc_val}")
    
    def _inject_spacing(self, pPr, params: StyleParams) -> None:
        """
        注入 <w:spacing> 节点
        
        设置固定行距（GB/T 9704 要求固定值28pt）
        
        Args:
            pPr: <w:pPr> 节点
            params: 样式参数
        """
        if params.line_spacing_twips is None:
            return
        
        # 检查是否已有 spacing 节点
        existing_spacing = pPr.find(qn('w:spacing'))
        if existing_spacing is not None:
            pPr.remove(existing_spacing)
        
        spacing = OxmlElement('w:spacing')
        spacing.set(qn('w:line'), str(params.line_spacing_twips))
        spacing.set(qn('w:lineRule'), 'exact')  # 固定值
        spacing.set(qn('w:before'), str(params.space_before_twips))
        spacing.set(qn('w:after'), str(params.space_after_twips))
        
        pPr.append(spacing)
        logger.debug(f"[XML] 行距: {params.line_spacing_twips} (fixed)")
    
    def _inject_pagination(self, pPr, params: StyleParams) -> None:
        """
        注入分页控制节点
        
        - <w:keepNext>: 与下段同页
        - <w:pageBreakBefore>: 段前分页
        
        Args:
            pPr: <w:pPr> 节点
            params: 样式参数
        """
        if params.keep_with_next:
            keepNext = OxmlElement('w:keepNext')
            pPr.append(keepNext)
        
        if params.page_break_before:
            pageBreak = OxmlElement('w:pageBreakBefore')
            pPr.append(pageBreak)
        
        # 大纲级别（用于导航窗格）
        if params.outline_level is not None:
            # 检查是否已有 outlineLvl
            existing_outline = pPr.find(qn('w:outlineLvl'))
            if existing_outline is not None:
                pPr.remove(existing_outline)
            
            outlineLvl = OxmlElement('w:outlineLvl')
            outlineLvl.set(qn('w:val'), str(params.outline_level))
            pPr.append(outlineLvl)


# === 便捷函数 ===

def compile_with_format(
    ir_blocks: List[DocumentIRBlock],
    output_path: str,
    dfgp_manager: Optional[DFGPManager] = None
) -> None:
    """
    一行代码：将 IR Block 序列编译为带格式的文档
    
    Args:
        ir_blocks: IR Block 序列
        output_path: 输出文件路径
        dfgp_manager: 可选 DFGP 管理器
    """
    compiler = SemanticCompiler(dfgp_manager)
    compiler.build_from_ir(ir_blocks, output_path)
