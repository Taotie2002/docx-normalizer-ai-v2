"""
docx-normalizer-ai-v2 主入口
SRS-2026-002 V11.2

Phase 1: Docx → IR → Docx (零丢失)
Phase 2: + 分类 → DFGP 格式灌注
"""

import sys
import os
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.extractor.ooxml_parser import DocxExtractor
from src.classifier.base_classifier import RuleSpatialClassifier
from src.compiler.xml_injector import SemanticCompiler
from src.auditor.validator import V03Validator
from src.core.exceptions import ExtractionError, CompilationError


def run_pipeline(input_file: str, output_file: str, validate: bool = True) -> bool:
    """
    Phase 1 + Phase 2 完整流水线
    
    流程: Docx → Extract → Classify → Build(DFGP) → [V-03 Validate]
    
    Args:
        input_file: 输入 .docx 文件
        output_file: 输出 .docx 文件
        validate: 是否执行 V-03 验证
        
    Returns:
        bool: 是否成功
    """
    print("=" * 60)
    print("=== docx-normalizer-ai-v2 ===")
    print(f"输入: {input_file}")
    print(f"输出: {output_file}")
    print("=" * 60)
    
    try:
        # ============ Phase 1: 提取 ============
        print("\n[Step 1] 提取 IR Block...")
        extractor = DocxExtractor(input_file)
        raw_blocks = extractor.extract_to_ir()
        print(f"  ✅ 提取完成: {len(raw_blocks)} 个段落")
        
        # ============ Phase 2: 分类 ============
        print("\n[Step 2] 分类（Rule + Spatial）...")
        classifier = RuleSpatialClassifier()
        classified_blocks = classifier.process(raw_blocks)
        
        # 统计分类结果
        labels = {}
        for b in classified_blocks:
            labels[b.label] = labels.get(b.label, 0) + 1
        print(f"  ✅ 分类完成:")
        for label, count in sorted(labels.items()):
            print(f"      {label}: {count}")
        
        # ============ Phase 2: 格式灌注 ============
        print("\n[Step 3] 格式灌注（DFGP + lxml）...")
        compiler = SemanticCompiler()
        compiler.build_from_ir(classified_blocks, output_file)
        print(f"  ✅ 灌注完成: {output_file}")
        
        # ============ Phase 1: V-03 验证 ============
        if validate:
            print("\n[Step 4] V-03 零丢失验证...")
            validator = DocxExtractor(output_file)
            rebuilt_blocks = validator.extract_to_ir()
            
            v03 = V03Validator()
            result = v03.validate(raw_blocks, rebuilt_blocks)
            
            if result.is_pass:
                print(f"  ✅ V-03 验证通过")
                print(f"      Hash: {result.raw_text_hash[:16]}...")
                print(f"      Token Diff: {result.token_diff_count}")
            else:
                print(f"  ❌ V-03 验证失败: {result.failure_mode}")
                if result.token_diffs:
                    print(f"      Token Diffs: {len(result.token_diffs)}")
                return False
        
        print("\n" + "=" * 60)
        print("=== 完成 ===")
        print("=" * 60)
        return True
        
    except ExtractionError as e:
        print(f"\n❌ 提取失败: {e}")
        return False
    except CompilationError as e:
        print(f"\n❌ 编译失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        return False


def main():
    """命令行入口"""
    if len(sys.argv) < 3:
        print("用法: python main.py <输入文件> <输出文件>")
        print("示例: python main.py input.docx output.docx")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"❌ 输入文件不存在: {input_file}")
        sys.exit(1)
    
    success = run_pipeline(input_file, output_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
