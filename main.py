import aiohttp
import asyncio
import logging
import time
from notify import Notifier
from config import NOFITY_CONFIG, AES_KEY

# 添加lxml可用性检查，当lxml不可用时使用html.parser作为备用方案
try:
    from bs4 import BeautifulSoup
    # 尝试导入lxml解析器
    import lxml
    PARSER = 'lxml'
except ImportError:
    # 如果lxml不可用，使用默认的html.parser
    from bs4 import BeautifulSoup
    PARSER = 'html.parser'
    logging.warning("lxml解析器不可用，将使用默认的html.parser作为备用方案")

class ColorFormatter(logging.Formatter):
    # ANSI颜色码
    GREY = '\033[90m'
    GREEN = '\033[92m'
    RESET = '\033[0m'

    def format(self, record):
        msg = record.getMessage()
        # 判断result内容
        if hasattr(record, 'result') and record.result is not None and 'full' in record.result.lower():
            color = self.GREY
            group = f"{color}{record.group}{self.RESET}"
            url = f"{color}{record.url}{self.RESET}"
            result = f"{color}{record.result}{self.RESET}"
        else:
            color = self.GREEN
            group = f"{color}{record.group}{self.RESET}"
            url = f"{color}{record.url}{self.RESET}"
            result = f"{color}{record.result}{self.RESET}"
        return f"{group} - {url}: {result}"

def setup_logger():
    logger = logging.getLogger("testflight")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logger.handlers = [handler]
    return logger

async def get_beta_status_text(session, url, sem):
    async with sem:
        try:
            async with session.get(url) as response:
                text = await response.text()
                # 只解析 beta-status 部分，减少解析量
                start = text.find('class="beta-status"')
                if start != -1:
                    sub_text = text[max(0, start-100):start+500]
                    try:
                        # 使用动态选择的解析器
                        soup = BeautifulSoup(sub_text, PARSER)
                        div = soup.find('div', class_='beta-status')
                        if div and div.span:
                            return div.span.get_text(strip=True)
                    except Exception as e:
                        logging.error(f"解析HTML时出错 (URL: {url}): {str(e)}")
                        return None
                return None
        except Exception as e:
            logging.error(f"获取URL时出错 (URL: {url}): {str(e)}")
            return None

async def check_and_notify():
    from config import TESTFLIGHT_URLS
    logger = setup_logger()
    start_time = time.time()
    connector = aiohttp.TCPConnector(ssl=False, enable_cleanup_closed=True)
    sem = asyncio.Semaphore(500)  # 再提升并发数
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        task_info = []
        for group, urls in TESTFLIGHT_URLS.items():
            if group == "exampleGroup":
                continue
            for url in urls:
                tasks.append(asyncio.create_task(get_beta_status_text(session, url, sem)))
                task_info.append((group, url))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 收集需要通知的结果
        notify_results = []
        for (group, url), result in zip(task_info, results):
            if isinstance(result, Exception):
                continue
            if result:
                logger.info('', extra={'group': group, 'url': url, 'result': result})
                # 如果不是"full"状态，则添加到通知列表
                if 'full' not in result.lower():
                    notify_results.append(f"{group} - {url}: {result}")
        
        # 如果有需要通知的结果，则发送通知
        if notify_results:
            notifier = Notifier(NOFITY_CONFIG, AES_KEY)
            title = "TestFlight 状态更新"
            content = "\n".join(notify_results)
            await notifier.notify(title, content, platforms=["bark"])
            
    end_time = time.time()
    print(f"总耗时: {end_time - start_time:.2f} 秒")

async def main():
    if ENABLE_LOOP:
        # 循环运行模式
        start_time = time.time()
        loop_count = 0
        while True:
            loop_count += 1
            print(f"\n第 {loop_count} 轮检查开始...")
            await check_and_notify()
            
            # 检查是否达到循环总时长
            if LOOP_DURATION > 0 and (time.time() - start_time) >= LOOP_DURATION:
                print("达到设定的循环总时长，停止运行")
                break
                
            print(f"等待 {LOOP_INTERVAL} 秒后进行下一轮检查...")
            # 动态显示剩余等待秒数
            for i in range(LOOP_INTERVAL, 0, -1):
                print(f"\r剩余等待时间: {i} 秒", end="", flush=True)
                await asyncio.sleep(1)
            print()  # 换行
    else:
        # 单次运行模式
        await check_and_notify()

if __name__ == '__main__':
    asyncio.run(main())