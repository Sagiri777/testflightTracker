import logging
import sys

class ColorFormatter(logging.Formatter):
    GREY = '\033[90m'
    GREEN = '\033[92m'
    RESET = '\033[0m'

    def format(self, record):
        # 保留对 extra 字段 group/url/result 的支持以兼容现有代码
        msg = record.getMessage()
        group = getattr(record, "group", "")
        url = getattr(record, "url", "")
        result = getattr(record, "result", msg)

        # 使用 logger 名称作为服务名前缀（record.name）
        name = getattr(record, "name", "")
        name_prefix = f"[{name}] " if name else ""

        if isinstance(result, str) and "full" in result.lower():
            color = self.GREY
        else:
            color = self.GREEN

        group_fmt = f"{color}{group}{self.RESET}" if group else ""
        url_fmt = f"{color}{url}{self.RESET}" if url else ""
        result_fmt = f"{color}{result}{self.RESET}" if result else msg

        # 如果没有 group/url/result，则回退到默认消息，但仍保留服务名前缀
        if group_fmt or url_fmt or result_fmt:
            return f"{name_prefix}{group_fmt} - {url_fmt}: {result_fmt}"
        return f"{name_prefix}{msg}"

class FlushStreamHandler(logging.StreamHandler):
    """
    StreamHandler that ensures the stream is flushed after each emit.
    This helps when stdout is buffered or when immediate output is required.
    我们直接手动写入并 flush，避免依赖父类实现在不同环境有差异导致未及时 flush 的情况。
    """
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream if hasattr(self, "stream") and self.stream is not None else sys.stdout
            stream.write(msg + self.terminator)
            try:
                stream.flush()
            except Exception:
                pass
        except Exception:
            # 如遇到任何错误，回退到基类实现以确保不抛异常影响程序
            try:
                super().emit(record)
                try:
                    self.flush()
                except Exception:
                    pass
            except Exception:
                # 最后兜底，静默忽略
                pass

# 预定义服务名，方便统一管理和文档说明
WAIT_SERVICE = "wait_service"
REQUEST_SERVICE = "request_service"
NOTIFY_SERVICE = "notify_service"
DEFAULT_SERVICE = "testflight"

# 内部单例：保存用于共享 handler/配置的 base logger（以 DEFAULT_SERVICE 命名）
_logger_singleton = None

def configure_logger(level=logging.INFO, use_color=True, name=DEFAULT_SERVICE):
    """
    Configure base logger once. Subsequent calls return the same configured base logger.
    The base logger's handlers 将被共享给其它命名 logger（通过 get_service_logger）。
    同时把相同的 handler 绑定到 logging.root，确保通过 logging.* 发出的日志也走相同流。
    """
    global _logger_singleton
    if _logger_singleton is not None:
        return _logger_singleton

    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = FlushStreamHandler(stream=sys.stdout)
    if use_color:
        handler.setFormatter(ColorFormatter())
    else:
        # 在非彩色模式下也包含服务名和级别
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))

    # 为 base logger 使用 handler
    logger.handlers = [handler]
    logger.propagate = False

    # 还将同一个 handler 绑定到 root logger，确保遗留的 logging.* 输出也使用相同的流与 flush 行为
    try:
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(level)
    except Exception:
        # 若无法修改 root logger，不影响主流程
        pass

    _logger_singleton = logger
    return logger

def get_logger(name=None):
    """
    Return configured logger. If not configured yet, will configure with defaults.
    If name provided, returns logger with that name but shares handlers and level from base logger.
    Use get_service_logger for clarity when dealing with service-specific loggers.
    """
    global _logger_singleton
    if _logger_singleton is None:
        _logger_singleton = configure_logger()
    if name:
        lg = logging.getLogger(name)
        lg.setLevel(_logger_singleton.level)
        # 共享 handlers 引用（保证 handler 为单一、已 flush 的输出）
        lg.handlers = _logger_singleton.handlers
        lg.propagate = False
        return lg
    return _logger_singleton

def get_service_logger(service_name, level=None, use_color=None):
    """
    Convenience function to get a logger for a specific service.
    - service_name: e.g., WAIT_SERVICE or REQUEST_SERVICE or any custom name.
    - level/use_color: optional overrides when base logger not configured yet.
    返回的 logger 拥有独立的 name，但共享同一组 handlers，方便区分来源且输出一致。
    """
    global _logger_singleton
    if _logger_singleton is None:
        # allow overriding base level/color on first config
        _logger_singleton = configure_logger(
            level=(logging.INFO if level is None else level),
            use_color=(True if use_color is None else use_color),
            name=DEFAULT_SERVICE
        )
    return get_logger(service_name)

