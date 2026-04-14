"""Phase 1 单元测试：DocxExtractor"""
import sys
sys.path.insert(0, '.')

from src.extractor.ooxml_parser import DocxExtractor, extract_file
from src.core.ir_block import BlockLabel

def test_basic_extraction():
    """测试基础提取功能"""
    # 使用之前灌注过的公文
    extractor = DocxExtractor('/tmp/output_normalized_v2.docx')
    blocks = extractor.extract_to_ir()
    
    print(f"提取了 {len(blocks)} 个段落")
    
    # 验证 V-03
    for i, block in enumerate(blocks[:5]):
        print(f"[{i}] idx={block.source_para_idx} | {block.text[:25]}... | label={block.label}")
    
    assert len(blocks) > 0, "应提取到段落"
    assert all(b.source_para_idx >= 0 for b in blocks), "source_para_idx 必须非负"
    print("✅ 基础提取测试通过")

if __name__ == "__main__":
    test_basic_extraction()
