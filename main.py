"""
Phase 1 主入口：Docx -> IR -> Docx 闭环测试
SRS-2026-002 V11.2

执行完整流程：
1. DocxExtractor: 脱骨提取 → IR Block 序列
2. DocxCompiler: 空白重构 → 新 Docx
3. 验证: 重构后文档内容与原文档 100% 一致
"""

import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.extractor.ooxml_parser import DocxExtractor
from src.compiler.builder import DocxCompiler
from src.core.exceptions import ExtractionError, CompilationError


def run_phase_1_pipeline(input_file: str, output_file: str) -> bool:
    """
    Phase 1 完整流水线测试
    
    Args:
        input_file: 输入 .docx 文件路径
        output_file: 输出 .docx 文件路径
        
    Returns:
        bool: 是否成功
    """
    print("=" * 60)
    print("=== 启动 Phase 1: Docx -> IR -> Docx 测试 ===")
    print("=" * 60)
    
    try:
        # ============ Step 1: 解析与脱骨 ============
        print(f"\n[Step 1] 加载文档: {input_file}")
        extractor = DocxExtractor(input_file)
        
        print("[Step 1] 执行脱骨提取...")
        ir_sequence = extractor.extract_to_ir()
        print(f"[Step 1] ✅ 脱骨完成: {len(ir_sequence)} 个 IR Blocks")
        
        # 打印前 5 个 Block 摘要
        print("\n--- IR 序列预览 (前5个) ---")
        for i, block in enumerate(ir_sequence[:5]):
            text_preview = block.text[:30].replace('\n', ' ')
            print(f"  [{i}] idx={block.source_para_idx} | level={block.heading_level} | {text_preview}...")
        
        # ============ Step 2: 空白重构 ============
        print(f"\n[Step 2] 创建空白编译器...")
        compiler = DocxCompiler()
        
        print("[Step 2] 执行空白重构...")
        compiler.build_from_ir(ir_sequence, output_file)
        print(f"[Step 2] ✅ 重构完成: {output_file}")
        
        # ============ Step 3: 验证 V-03 零丢失 ============
        print("\n[Step 3] V-03 零丢失验证...")
        
        # 提取输出文档的文本
        validator = DocxExtractor(output_file)
        output_blocks = validator.extract_to_ir()
        
        # 比较段落数量
        if len(ir_sequence) != len(output_blocks):
            print(f"❌ 段落数量不匹配: 输入={len(ir_sequence)}, 输出={len(output_blocks)}")
            return False
        
        # 比较每个段落的文本
        mismatches = []
        for i, (orig, rebuilt) in enumerate(zip(ir_sequence, output_blocks)):
            if orig.text != rebuilt.text:
                mismatches.append({
                    "idx": i,
                    "original": orig.text[:50],
                    "rebuilt": rebuilt.text[:50]
                })
        
        if mismatches:
            print(f"❌ 发现 {len(mismatches)} 处文本不一致:")
            for m in mismatches[:3]:
                print(f"  [{m['idx']}] 原文: {m['original']}")
                print(f"       重构: {m['rebuilt']}")
            return False
        
        print("✅ V-03 零丢失验证通过: 文本内容 100% 一致")
        print("\n" + "=" * 60)
        print("=== Phase 1 测试成功结束 ===")
        print("=" * 60)
        return True
        
    except ExtractionError as e:
        print(f"❌ 提取失败: {e}")
        return False
    except CompilationError as e:
        print(f"❌ 编译失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False


if __name__ == "__main__":
    # Phase 1 测试：使用之前灌注过的公文
    input_file = "/tmp/output_normalized_v2.docx"
    output_file = "/tmp/phase1_rebuilt.docx"
    
    # 如果命令行提供了文件路径，使用命令行参数
    if len(sys.argv) > 2:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    
    success = run_phase_1_pipeline(input_file, output_file)
    sys.exit(0 if success else 1)
