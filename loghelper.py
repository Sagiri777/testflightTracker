import os
import logging
import re
from typing import Dict, Optional, Tuple, Any, Union

# 添加colorama支持，用于跨平台颜色输出
try:
    from colorama import init, Fore, Style, Back
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

# 添加webcolors支持，用于hex颜色转换
try:
    import webcolors
    HAS_WEBCOLORS = True
except ImportError:
    HAS_WEBCOLORS = False

class ColorConverter:
    """颜色转换器，支持hex颜色编码到ANSI颜色"""
    
    # 预定义颜色映射
    BASIC_COLORS = {
        'black': Fore.BLACK,
        'red': Fore.RED,
        'green': Fore.GREEN,
        'yellow': Fore.YELLOW,
        'blue': Fore.BLUE,
        'magenta': Fore.MAGENTA,
        'cyan': Fore.CYAN,
        'white': Fore.WHITE,
        'bright_black': Fore.LIGHTBLACK_EX,
        'bright_red': Fore.LIGHTRED_EX,
        'bright_green': Fore.LIGHTGREEN_EX,
        'bright_yellow': Fore.LIGHTYELLOW_EX,
        'bright_blue': Fore.LIGHTBLUE_EX,
        'bright_magenta': Fore.LIGHTMAGENTA_EX,
        'bright_cyan': Fore.LIGHTCYAN_EX,
        'bright_white': Fore.LIGHTWHITE_EX,
    }
    
    # 常见hex颜色到基本颜色的映射（用于降级）
    HEX_TO_BASIC = {
        '#ff0000': 'red', '#00ff00': 'green', '#0000ff': 'blue',
        '#ffff00': 'yellow', '#ff00ff': 'magenta', '#00ffff': 'cyan',
        '#000000': 'black', '#ffffff': 'white',
        '#808080': 'bright_black', '#c0c0c0': 'bright_white',
        '#800000': 'red', '#008000': 'green', '#000080': 'blue',
        '#808000': 'yellow', '#800080': 'magenta', '#008080': 'cyan',
    }
    
    @classmethod
    def hex_to_ansi(cls, hex_color: str, is_background: bool = False) -> str:
        """
        将hex颜色转换为ANSI转义序列
        
        Args:
            hex_color: hex颜色字符串，如 '#FF0000' 或 'FF0000'
            is_background: 是否为背景色
        
        Returns:
            ANSI转义序列字符串
        """
        if not hex_color.startswith('#'):
            hex_color = '#' + hex_color
        
        # 如果是基本颜色映射，直接使用
        if hex_color.lower() in cls.HEX_TO_BASIC and HAS_COLORAMA:
            basic_color = cls.HEX_TO_BASIC[hex_color.lower()]
            color_code = cls.BASIC_COLORS[basic_color]
            return color_code.replace(Fore.RESET, Back.RESET) if is_background else color_code
        
        # 如果有webcolors支持，尝试转换为RGB
        if HAS_WEBCOLORS:
            try:
                rgb = webcolors.hex_to_rgb(hex_color)
                if is_background:
                    return f'\033[48;2;{rgb.red};{rgb.green};{rgb.blue}m'
                else:
                    return f'\033[38;2;{rgb.red};{rgb.green};{rgb.blue}m'
            except (ValueError, AttributeError):
                pass
        
        # 降级处理：将hex转换为最接近的基本颜色
        if HAS_COLORAMA:
            return cls._find_closest_basic_color(hex_color, is_background)
        
        return ''
    
    @classmethod
    def _find_closest_basic_color(cls, hex_color: str, is_background: bool = False) -> str:
        """找到最接近的基本颜色（简单的RGB距离计算）"""
        try:
            # 简单的hex转RGB
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # 计算与每个基本颜色的距离
            min_distance = float('inf')
            closest_color = 'white'
            
            for color_name, color_code in cls.BASIC_COLORS.items():
                # 获取基本颜色的RGB值（近似）
                base_rgb = cls._get_basic_color_rgb(color_name)
                distance = ((r - base_rgb[0]) ** 2 + 
                           (g - base_rgb[1]) ** 2 + 
                           (b - base_rgb[2]) ** 2)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_color = color_name
            
            color_code = cls.BASIC_COLORS[closest_color]
            return color_code.replace(Fore.RESET, Back.RESET) if is_background else color_code
        except (ValueError, IndexError):
            return Fore.RESET
    
    @classmethod
    def _get_basic_color_rgb(cls, color_name: str) -> Tuple[int, int, int]:
        """获取基本颜色的近似RGB值"""
        color_map = {
            'black': (0, 0, 0),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'yellow': (255, 255, 0),
            'blue': (0, 0, 255),
            'magenta': (255, 0, 255),
            'cyan': (0, 255, 255),
            'white': (255, 255, 255),
            'bright_black': (128, 128, 128),
            'bright_red': (255, 128, 128),
            'bright_green': (128, 255, 128),
            'bright_yellow': (255, 255, 128),
            'bright_blue': (128, 128, 255),
            'bright_magenta': (255, 128, 255),
            'bright_cyan': (128, 255, 255),
            'bright_white': (255, 255, 255),
        }
        return color_map.get(color_name, (255, 255, 255))

class EnhancedColoredFormatter(logging.Formatter):
    """增强的颜色格式化器，支持hex颜色编码"""
    
    # 预编译正则表达式，提高性能
    _STYLE_PATTERN = re.compile(r'\[([^\[\]]+)\]([^\[\]]*?)\[/\]')
    _HEX_COLOR_PATTERN = re.compile(r'^#?[0-9a-fA-F]{6}$')
    
    def __init__(self, fmt=None, datefmt=None, style='%', no_color=False):
        super().__init__(fmt, datefmt, style)
        self.no_color = no_color
        self.color_converter = ColorConverter()
        
        # 预定义颜色映射
        if HAS_COLORAMA and not no_color:
            self.colors = {
                'DEBUG': Fore.CYAN,
                'INFO': Fore.GREEN,
                'WARNING': Fore.YELLOW,
                'ERROR': Fore.RED,
                'CRITICAL': Fore.RED + Style.BRIGHT,
            }
            self.inline_styles = {
                'red': Fore.RED,
                'green': Fore.GREEN,
                'yellow': Fore.YELLOW,
                'blue': Fore.BLUE,
                'magenta': Fore.MAGENTA,
                'cyan': Fore.CYAN,
                'white': Fore.WHITE,
                'black': Fore.BLACK,
                'bright': Style.BRIGHT,
                'dim': Style.DIM,
                'normal': Style.NORMAL,
                'reset': Style.RESET_ALL,
            }
            # 添加亮色变体
            self.inline_styles.update({
                'bright_red': Fore.LIGHTRED_EX,
                'bright_green': Fore.LIGHTGREEN_EX,
                'bright_yellow': Fore.LIGHTYELLOW_EX,
                'bright_blue': Fore.LIGHTBLUE_EX,
                'bright_magenta': Fore.LIGHTMAGENTA_EX,
                'bright_cyan': Fore.LIGHTCYAN_EX,
                'bright_white': Fore.LIGHTWHITE_EX,
                'bright_black': Fore.LIGHTBLACK_EX,
            })
        else:
            self.colors = {}
            self.inline_styles = {}

    def format(self, record):
        # 确保record有program_name属性
        if not hasattr(record, 'program_name'):
            record.program_name = ''
        
        # 处理所有extra字段中的内联样式，但排除program_name
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if (key not in ['args', 'asctime', 'created', 'exc_info', 'exc_text', 
                              'filename', 'funcName', 'levelname', 'levelno', 'lineno', 
                              'module', 'msecs', 'message', 'msg', 'name', 'pathname', 
                              'process', 'processName', 'relativeCreated', 'stack_info', 
                              'thread', 'threadName', 'program_name'] and
                    isinstance(value, str)):
                    setattr(record, key, self._apply_inline_styles(value))
        
        # 获取原始消息
        original_message = super().format(record)
        
        # 处理整个消息中的内联样式
        message_with_inline_styles = self._apply_inline_styles(original_message)
        
        # 应用颜色样式
        if HAS_COLORAMA and not self.no_color:
            if hasattr(record, 'dim') and record.dim:
                return f"{Style.DIM}{message_with_inline_styles}{Style.NORMAL}"
            elif hasattr(record, 'color') and record.color:
                color_code = self._get_color_code(record.color)
                return f"{color_code}{message_with_inline_styles}{Style.RESET_ALL}"
            elif record.levelname in self.colors:
                return f"{self.colors[record.levelname]}{message_with_inline_styles}{Style.RESET_ALL}"
        
        return message_with_inline_styles
    
    def _get_color_code(self, color_spec: str) -> str:
        """根据颜色规格获取颜色代码"""
        if not color_spec:
            return ''
        
        # 检查是否为hex颜色
        if self._HEX_COLOR_PATTERN.match(color_spec):
            return self.color_converter.hex_to_ansi(color_spec)
        
        # 检查是否为预定义颜色
        color_spec_lower = color_spec.lower()
        if color_spec_lower in self.inline_styles:
            return self.inline_styles[color_spec_lower]
        
        # 尝试作为Fore属性
        if HAS_COLORAMA:
            try:
                return getattr(Fore, color_spec.upper(), '')
            except AttributeError:
                pass
        
        return ''
    
    def _apply_inline_styles(self, message):
        """解析并应用内联样式标记，支持hex颜色"""
        if not HAS_COLORAMA or self.no_color:
            # 移除样式标记但保留文本
            return self._STYLE_PATTERN.sub(r'\2', message)
        
        def replace_style(match):
            styles_str, text = match.groups()
            if not styles_str or not text:
                return text or ''
            
            styles = [s.strip().lower() for s in styles_str.split(',')]
            style_codes = []
            
            for style in styles:
                if style in self.inline_styles:
                    style_codes.append(self.inline_styles[style])
                elif self._HEX_COLOR_PATTERN.match(style):
                    # 处理hex颜色
                    style_codes.append(self.color_converter.hex_to_ansi(style))
                elif style.startswith('bg_'):
                    # 处理背景色
                    bg_color = style[3:]  # 移除 'bg_' 前缀
                    if bg_color in self.inline_styles:
                        bg_code = self.inline_styles[bg_color].replace(Fore.RESET, Back.RESET)
                        style_codes.append(bg_code)
                    elif self._HEX_COLOR_PATTERN.match(bg_color):
                        style_codes.append(self.color_converter.hex_to_ansi(bg_color, True))
            
            if style_codes:
                return f"{''.join(style_codes)}{text}{Style.RESET_ALL}"
            return text
        
        # 使用预编译的正则表达式进行替换
        processed_message = message
        previous_message = ""
        
        # 最多处理3次，防止无限循环
        for _ in range(3):
            if processed_message == previous_message:
                break
            previous_message = processed_message
            processed_message = self._STYLE_PATTERN.sub(replace_style, processed_message)
        
        return processed_message

class LoggerConfig:
    """日志配置管理器"""
    
    def __init__(self):
        self.no_color = os.environ.get('NO_COLOR', '').lower() in ('1', 'true', 'yes')
        self.force_color = os.environ.get('FORCE_COLOR', '').lower() in ('1', 'true', 'yes')
        
        # 初始化colorama
        if HAS_COLORAMA:
            if self.force_color:
                init(autoreset=True, strip=False, convert=False)
            else:
                init(autoreset=True, strip=False, convert=None)
    
    @property
    def use_color(self) -> bool:
        """是否使用颜色"""
        return HAS_COLORAMA and not self.no_color

class ProgramLogger:
    """程序名称日志记录器"""
    
    def __init__(self, base_logger, config):
        self.base_logger = base_logger
        self.config = config
        self._program_formatter = None
        self._extra_formatter = None
    
    @property
    def program_formatter(self):
        """程序名称格式化器（单例）"""
        if self._program_formatter is None:
            program_fmt = '[%(program_name)s] %(asctime)s %(levelname)s %(message)s'
            self._program_formatter = EnhancedColoredFormatter(
                fmt=program_fmt,
                datefmt='%Y-%m-%d T%H:%M:%S',
                no_color=self.config.no_color
            )
        return self._program_formatter
    
    @property
    def extra_formatter(self):
        """extra字段格式化器（单例）"""
        if self._extra_formatter is None:
            extra_fmt = '%(asctime)s %(levelname)s %(message)s [%(extra_fields)s]'
            self._extra_formatter = EnhancedColoredFormatter(
                fmt=extra_fmt,
                datefmt='%Y-%m-%d T%H:%M:%S',
                no_color=self.config.no_color
            )
        return self._extra_formatter
    
    def log_with_program(self, program_name: str, message: str, level: str = 'info', **kwargs):
        """使用程序名称记录日志"""
        handler = self.base_logger.handlers[0]
        original_formatter = handler.formatter
        
        handler.setFormatter(self.program_formatter)
        
        try:
            # 预处理程序名称中的内联样式
            styled_program_name = self._preprocess_styles(program_name)
            kwargs.setdefault('extra', {})['program_name'] = styled_program_name
            getattr(self.base_logger, level.lower())(message, **kwargs)
        finally:
            handler.setFormatter(original_formatter)
    
    def log_with_extra_detailed(self, extra_fields: Dict, message: str, level: str = 'info', **kwargs):
        """使用详细extra字段记录日志"""
        handler = self.base_logger.handlers[0]
        original_formatter = handler.formatter
        
        handler.setFormatter(self.extra_formatter)
        
        try:
            # 将extra字段格式化为字符串
            extra_str = " ".join([f"{k}={v}" for k, v in extra_fields.items()])
            
            kwargs.setdefault('extra', {})
            kwargs['extra'].update(extra_fields)
            kwargs['extra']['extra_fields'] = extra_str
            
            getattr(self.base_logger, level.lower())(message, **kwargs)
        finally:
            handler.setFormatter(original_formatter)
    
    def _preprocess_styles(self, text: str) -> str:
        """预处理文本中的样式（用于程序名称等）"""
        if not HAS_COLORAMA or self.config.no_color:
            # 创建一个临时的无颜色格式化器来处理样式标记
            temp_formatter = EnhancedColoredFormatter(no_color=True)
            return temp_formatter._apply_inline_styles(text)
        else:
            temp_formatter = EnhancedColoredFormatter(no_color=False)
            return temp_formatter._apply_inline_styles(text)

# 全局配置
config = LoggerConfig()

# 创建主logger
log = logging.getLogger("testflightTracker")
log.handlers.clear()
log.setLevel(logging.INFO)
log.propagate = False

# 创建handler和formatter
handler = logging.StreamHandler()
base_fmt = '%(asctime)s %(levelname)s %(message)s'

formatter = EnhancedColoredFormatter(
    fmt=base_fmt,
    datefmt='%Y-%m-%d T%H:%M:%S',
    no_color=config.no_color
)
handler.setFormatter(formatter)
log.addHandler(handler)

# 创建程序日志记录器
program_logger = ProgramLogger(log, config)

# ===== 便捷方法 =====

# 淡化效果方法
def debug_dim(message, *args, **kwargs):
    kwargs.setdefault('extra', {})['dim'] = True
    log.debug(message, *args, **kwargs)

def info_dim(message, *args, **kwargs):
    kwargs.setdefault('extra', {})['dim'] = True
    log.info(message, *args, **kwargs)

def warning_dim(message, *args, **kwargs):
    kwargs.setdefault('extra', {})['dim'] = True
    log.warning(message, *args, **kwargs)

def error_dim(message, *args, **kwargs):
    kwargs.setdefault('extra', {})['dim'] = True
    log.error(message, *args, **kwargs)

def critical_dim(message, *args, **kwargs):
    kwargs.setdefault('extra', {})['dim'] = True
    log.critical(message, *args, **kwargs)

# 彩色日志方法
def info_colored(message, color='GREEN', *args, **kwargs):
    kwargs.setdefault('extra', {})['color'] = color
    log.info(message, *args, **kwargs)

def warning_colored(message, color='YELLOW', *args, **kwargs):
    kwargs.setdefault('extra', {})['color'] = color
    log.warning(message, *args, **kwargs)

def error_colored(message, color='RED', *args, **kwargs):
    kwargs.setdefault('extra', {})['color'] = color
    log.error(message, *args, **kwargs)

# 程序名称日志方法
def debug_program(program_name, message, *args, **kwargs):
    program_logger.log_with_program(program_name, message, 'debug', *args, **kwargs)

def info_program(program_name, message, *args, **kwargs):
    program_logger.log_with_program(program_name, message, 'info', *args, **kwargs)

def warning_program(program_name, message, *args, **kwargs):
    program_logger.log_with_program(program_name, message, 'warning', *args, **kwargs)

def error_program(program_name, message, *args, **kwargs):
    program_logger.log_with_program(program_name, message, 'error', *args, **kwargs)

def critical_program(program_name, message, *args, **kwargs):
    program_logger.log_with_program(program_name, message, 'critical', *args, **kwargs)

# Extra字段日志方法
def log_with_extra(extra_fields, message, level='info', **kwargs):
    """使用extra字段记录日志（简化版）"""
    if extra_fields:
        extra_str = " ".join([f"{k}={v}" for k, v in extra_fields.items()])
        full_message = f"{message} [{extra_str}]"
    else:
        full_message = message
    
    kwargs.setdefault('extra', {})
    kwargs['extra'].update(extra_fields)
    getattr(log, level.lower())(full_message, **kwargs)

def log_with_extra_detailed(extra_fields, message, level='info', **kwargs):
    """使用extra字段记录日志（详细版）"""
    program_logger.log_with_extra_detailed(extra_fields, message, level, **kwargs)

# 使用示例和测试
if __name__ == "__main__":
    print("=== 增强版日志系统测试（支持hex颜色编码） ===\n")
    
    # 颜色支持检测
    print("--- 颜色支持检测 ---")
    print(f"colorama库是否可用: {HAS_COLORAMA}")
    print(f"webcolors库是否可用: {HAS_WEBCOLORS}")
    print(f"是否禁用颜色: {config.no_color}")
    print(f"是否强制启用颜色: {config.force_color}")
    
    # 基本日志输出
    print("\n--- 基本日志输出 ---")
    log.debug("这是调试信息")
    log.info("这是普通信息")
    log.warning("这是警告信息")
    log.error("这是错误信息")
    log.critical("这是严重错误信息")
    
    # 使用hex颜色的日志输出
    print("\n--- 使用hex颜色的日志输出 ---")
    log.info("这是[#FF0000]红色文本[/]和[#00FF00]绿色文本[/]")
    log.info("背景色测试：[bg_#0000FF]蓝色背景[/]和[#FFFFFF,bg_#FF0000]红底白字[/]")
    
    # 混合样式测试
    print("\n--- 混合样式测试 ---")
    log.info("混合样式：[#FFA500,bright]亮橙色加粗[/]和[dim,#008000]暗绿色[/]")
    log.info("复杂样式：[bg_#FFFF00,#000000]黄底黑字[/]加[bright_red]亮红色[/]")
    
    # 程序名称使用hex颜色
    print("\n--- 程序名称使用hex颜色 ---")
    info_program("[#FF6B6B]AuthService[/]", "用户认证成功")
    warning_program("[#FFA500]Monitor[/]", "系统负载较高")
    error_program("[#DC143C]Database[/]", "连接超时")
    
    # 使用extra字段和hex颜色
    print("\n--- 使用extra字段和hex颜色 ---")
    log_with_extra_detailed(
        {"user": "[#00CED1]admin[/]", "ip": "[#32CD32]192.168.1.100[/]", "status": "[#1E90FF]success[/]"},
        "用户登录操作完成"
    )
    
    # 直接使用hex颜色参数
    print("\n--- 直接使用hex颜色参数 ---")
    info_colored("这是自定义颜色消息", color="#8A2BE2")  # 蓝紫色
    warning_colored("警告消息", color="#FF4500")  # 橙红色
    
    # 降级测试（使用基本颜色名称）
    print("\n--- 基本颜色名称测试 ---")
    log.info("基本颜色：[red]红色[/]、[green]绿色[/]、[blue]蓝色[/]")
    log.info("亮色：[bright_red]亮红[/]、[bright_green]亮绿[/]、[bright_blue]亮蓝[/]")
    log.info("背景色：[bg_red]红底[/]、[bg_green]绿底[/]、[bg_blue]蓝底[/]")
    
    # 性能测试
    print("\n--- 性能测试（多次样式应用） ---")
    import time
    start_time = time.time()
    
    for i in range(10):  # 减少测试数量
        info_program(f"[#{(i * 25) % 255:02X}0000]Service{i}[/]", f"消息编号 [#00{(i * 25) % 255:02X}00]{i}[/]")
    
    end_time = time.time()
    print(f"处理10条带hex颜色的日志耗时: {end_time - start_time:.3f}秒")