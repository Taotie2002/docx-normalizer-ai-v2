"""
自定义异常树
SRS-2026-002 V11.2
"""

class DocCompilerError(Exception):
    """文档编译器基础异常"""
    pass


class ExtractionError(DocCompilerError):
    """提取阶段异常"""
    pass


class ClassificationError(DocCompilerError):
    """分类阶段异常"""
    pass


class CompilationError(DocCompilerError):
    """编译阶段异常"""
    pass


class ValidationError(DocCompilerError):
    """验证阶段异常"""
    pass


class RIDCollisionError(CompilationError):
    """rId 冲突异常"""
    pass


class UnsupportedObjectError(CompilationError):
    """不支持的对象类型异常"""
    pass


class GoldenSetError(DocCompilerError):
    """Golden Set 相关异常"""
    pass


class AgentHubError(DocCompilerError):
    """Agent 协作中枢异常"""
    pass


class CircuitBreakerError(AgentHubError):
    """熔断机制触发异常"""
    pass
