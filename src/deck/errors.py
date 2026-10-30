"""统一错误类型：所有对外失败都必须带 code / message / hint。"""

from __future__ import annotations


class AgentError(RuntimeError):
    """可预期的业务失败，由 CLI 转成 JSON 输出并返回非零退出码。"""

    def __init__(self, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint

    def as_dict(self) -> dict:
        error = {"code": self.code, "message": self.message}
        if self.hint:
            error["hint"] = self.hint
        return error


class StageError(AgentError):
    """流水线阶段错误。"""


class ProviderError(AgentError):
    """模型提供方错误。"""
