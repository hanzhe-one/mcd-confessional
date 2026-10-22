"""控制台输出兜底：让终端不会因为字符集而中断。

Windows 默认 stdout 编码是 GBK（cp936）。庭审文本里出现 ✓、− 这类字符时，
print 会直接抛 UnicodeEncodeError，整场庭审在中途退出——数据全对，进程却没了。

这里把不可编码的字符降级成替换符：能输出优先于字符完整。
"""

from __future__ import annotations

import sys


def harden_stdout() -> None:
    """把 stdout / stderr 的错误策略改成 replace（幂等）。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # 被替换成非 TextIOWrapper 的流
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):  # pragma: no cover - 流已关闭或重定向异常
            pass
