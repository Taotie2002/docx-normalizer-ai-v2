"""
Golden Set 批处理回归测试
Phase 4 验收基础设施

执行流程：
1. 扫描 tests/golden_set/*.docx
2. 对每个文件执行: Extract → IR → Build → V-03 Validate
3. 生成 Phase1_Final_Report.md
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extractor.ooxml_parser import DocxExtractor
from src.compiler.builder import DocxCompiler
from src.auditor.validator import V03Validator, V03ValidationResult
from src.core.exceptions import ExtractionError, CompilationError


class GoldenSetRunner:
    """Golden Set 批处理运行器"""
    
    def __init__(self, golden_set_dir: str, output_dir: str):
        self.golden_set_dir = Path(golden_set_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results: List[Dict] = []
        self.summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "by_type": {
                "A": {"total": 0, "passed": 0, "failed": 0},
                "B": {"total": 0, "passed": 0, "failed": 0},
                "C": {"total": 0, "passed": 0, "failed": 0},
                "D": {"total": 0, "passed": 0, "failed": 0},
            }
        }
    
    def scan_samples(self) -> List[Path]:
        """扫描所有测试样本"""
        samples = []
        for subdir in self.golden_set_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith("type_"):
                for f in subdir.glob("*.docx"):
                    samples.append(f)
        return sorted(samples)
    
    def get_sample_type(self, path: Path) -> str:
        """从路径推断样本类型"""
        if "type_a" in path.parts:
            return "A"
        elif "type_b" in path.parts:
            return "B"
        elif "type_c" in path.parts:
            return "C"
        elif "type_d" in path.parts:
            return "D"
        return "Unknown"
    
    def run_single(self, sample_path: Path) -> Dict:
        """运行单个样本测试"""
        result = {
            "file": sample_path.name,
            "type": self.get_sample_type(sample_path),
            "status": "PENDING",
            "error": None,
            "v03_result": None,
            "blocks_count": 0,
            "rebuilt_path": None
        }
        
        temp_rebuilt = self.output_dir / f"rebuilt_{sample_path.stem}.docx"
        result["rebuilt_path"] = str(temp_rebuilt)
        
        try:
            # Step 1: Extract
            extractor = DocxExtractor(str(sample_path))
            raw_blocks = extractor.extract_to_ir()
            result["blocks_count"] = len(raw_blocks)
            
            # Step 2: Build
            compiler = DocxCompiler()
            compiler.build_from_ir(raw_blocks, str(temp_rebuilt))
            
            # Step 3: Extract rebuilt for validation
            validator_extractor = DocxExtractor(str(temp_rebuilt))
            rebuilt_blocks = validator_extractor.extract_to_ir()
            
            # Step 4: V-03 Validate
            v03 = V03Validator()
            v03_result = v03.validate(raw_blocks, rebuilt_blocks)
            result["v03_result"] = v03_result
            
            if v03_result.is_pass:
                result["status"] = "PASS"
            else:
                result["status"] = f"FAIL_{v03_result.failure_mode}"
                
        except ExtractionError as e:
            result["status"] = "ERROR_EXTRACT"
            result["error"] = str(e)
        except CompilationError as e:
            result["status"] = "ERROR_COMPILE"
            result["error"] = str(e)
        except Exception as e:
            result["status"] = "ERROR_UNKNOWN"
            result["error"] = str(e)
        
        return result
    
    def run_all(self) -> None:
        """运行所有测试"""
        samples = self.scan_samples()
        
        print("=" * 60)
        print("=== Golden Set 批处理开始 ===")
        print(f"发现 {len(samples)} 个测试样本")
        print("=" * 60)
        
        self.summary["total"] = len(samples)
        
        for i, sample in enumerate(samples, 1):
            print(f"\n[{i}/{len(samples)}] 测试: {sample.name}")
            
            result = self.run_single(sample)
            self.results.append(result)
            
            # 更新统计
            sample_type = result["type"]
            self.summary["by_type"][sample_type]["total"] += 1
            
            if result["status"] == "PASS":
                self.summary["passed"] += 1
                self.summary["by_type"][sample_type]["passed"] += 1
                print(f"  ✅ PASS ({result['blocks_count']} blocks)")
            else:
                self.summary["failed"] += 1
                self.summary["by_type"][sample_type]["failed"] += 1
                print(f"  ❌ {result['status']}: {result.get('error', '')}")
        
        self.generate_report()
    
    def generate_report(self) -> None:
        """生成测试报告"""
        report_path = self.output_dir / "Phase1_Final_Report.md"
        
        # 计算通过率
        pass_rate = (
            self.summary["passed"] / self.summary["total"] * 100
            if self.summary["total"] > 0 else 0
        )
        
        lines = [
            "# Phase 1 批处理测试报告",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**测试框架**: docx-normalizer-ai-v2",
            f"**测试类型**: V-03 零丢失验证",
            "",
            "---",
            "",
            "## 总体结果",
            "",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 总样本数 | {self.summary['total']} |",
            f"| 通过数 | {self.summary['passed']} |",
            f"| 失败数 | {self.summary['failed']} |",
            f"| 通过率 | {pass_rate:.1f}% |",
            "",
            "## 分类型统计",
            "",
            f"| 类型 | 总数 | 通过 | 失败 | 通过率 |",
            f"|------|------|------|------|--------|",
        ]
        
        for t in ["A", "B", "C", "D"]:
            stats = self.summary["by_type"][t]
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            lines.append(f"| Type {t} | {stats['total']} | {stats['passed']} | {stats['failed']} | {rate:.1f}% |")
        
        lines.extend([
            "",
            "## 详细结果",
            "",
            "| 文件名 | 类型 | 状态 | 段落数 | Hash | Token Diff |",
            "|------|------|------|--------|------|------------|",
        ])
        
        for r in self.results:
            v03 = r.get("v03_result")
            hash_ok = "✅" if (v03 and v03.hash_match) else "❌"
            diff_count = v03.token_diff_count if v03 else "-"
            lines.append(
                f"| {r['file']} | {r['type']} | {r['status']} | "
                f"{r['blocks_count']} | {hash_ok} | {diff_count} |"
            )
        
        # 失败样本详情
        failed_results = [r for r in self.results if r["status"] != "PASS"]
        if failed_results:
            lines.extend([
                "",
                "## 失败样本分析",
                "",
            ])
            for r in failed_results:
                lines.append(f"### {r['file']}")
                lines.append(f"- 类型: {r['type']}")
                lines.append(f"- 状态: {r['status']}")
                if r.get("error"):
                    lines.append(f"- 错误: {r['error']}")
                
                v03 = r.get("v03_result")
                if v03 and v03.token_diffs:
                    lines.append("- Token Diffs:")
                    for d in v03.token_diffs[:5]:
                        lines.append(
                            f"  - [{d['idx']}] {d['diff_type']}: "
                            f"\"{d['raw_text']}\" → \"{d['rebuilt_text']}\""
                        )
                lines.append("")
        
        report_content = "\n".join(lines)
        report_path.write_text(report_content, encoding="utf-8")
        
        print("\n" + "=" * 60)
        print(f"=== 报告已生成: {report_path} ===")
        print(f"总体通过率: {pass_rate:.1f}%")
        print("=" * 60)


def main():
    # 默认路径
    project_root = Path(__file__).parent.parent.parent
    golden_set_dir = project_root / "tests" / "golden_set"
    output_dir = project_root / "tests" / "reports"
    
    runner = GoldenSetRunner(str(golden_set_dir), str(output_dir))
    runner.run_all()


if __name__ == "__main__":
    main()
