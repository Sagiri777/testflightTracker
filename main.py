import aiohttp
import asyncio
import time
import os
from typing import Optional, Dict, List, Set, Tuple, Any
from notify import Notifier
from config import NOFITY_CONFIG, AES_KEY

ENABLE_LOOP: bool = True  # 是否启用循环运行
LOOP_INTERVAL: int = 300  # 循环间隔时间（秒）
LOOP_DURATION: int = 3600  # 循环总时长（秒），设为0表示无限循环
CONCURRENCY_LIMIT: int = int(os.getenv("CONCURRENCY_LIMIT", "500"))  # 并发上限可配置，默认500
WAIT_UPDATE_STEP: int = int(os.getenv("WAIT_UPDATE_STEP", "5"))  # 倒计时刷新步长，默认5秒

from logger import get_service_logger, REQUEST_SERVICE

# 主逻辑主要发起请求，使用请求服务名的 logger
logger = get_service_logger(REQUEST_SERVICE)

# 添加lxml可用性检查，当lxml不可用时使用html.parser作为备用方案
from bs4 import BeautifulSoup, SoupStrainer
try:
    import lxml  # type: ignore
    parser: str = 'lxml'
except Exception:
    parser = 'html.parser'
    logger.warning("lxml解析器不可用，将使用默认的html.parser作为备用方案")

async def get_beta_status_text(session: aiohttp.ClientSession, url: str, sem: asyncio.Semaphore) -> Optional[str]:
    async with sem:
        try:
            text = None
            last_err = None
            for attempt in range(3):
                try:
                    async with session.get(url) as response:
                        text = await response.text()
                        break
                except Exception as e:
                    last_err = e
                    await asyncio.sleep(0.5 * (2 ** attempt))
            if text is None:
                logger.error(f"获取URL重试失败 (URL: {url}): {last_err}")
                return None
            # 只解析 beta-status 部分，减少解析量
            start = text.find('class="beta-status"')
            if start != -1:
                sub_text = text[max(0, start-100):start+500]
                try:
                    # 使用SoupStrainer精确解析beta-status区域
                    strainer = SoupStrainer('div', class_='beta-status')
                    soup = BeautifulSoup(sub_text, parser, parse_only=strainer)
                    div = soup.find('div', class_='beta-status')
                    if div:
                        span = div.find('span')
                        if span:
                            text_result: Optional[str] = span.get_text(strip=True)  # type: ignore
                            return text_result
                except Exception as e:
                    logger.error(f"解析HTML时出错 (URL: {url}): {str(e)}")
                    return None
            return None
        except Exception as e:
            logger.error(f"获取URL时出错 (URL: {url}): {str(e)}")
            return None

async def check_and_notify():
    from config import TESTFLIGHT_URLS
    
    start_time = time.time()
    connector = aiohttp.TCPConnector(ssl=False, enable_cleanup_closed=True, use_dns_cache=True, ttl_dns_cache=60, keepalive_timeout=30)
    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)  # 并发上限可配置
    timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_connect=5, sock_read=10)
    headers = {"Accept-Encoding": "gzip, deflate", "User-Agent": "testflightTracker/1.0"}
    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
        tasks: List[asyncio.Task[Optional[str]]] = []
        task_map: Dict[asyncio.Future[Optional[str]], Tuple[str, str]] = {}
        for group, urls in TESTFLIGHT_URLS.items():
            if group == "exampleGroup":
                continue
            for url in urls:
                t = asyncio.create_task(get_beta_status_text(session, url, sem))
                tasks.append(t)
                task_map[t] = (group, url)
        # 流式处理已完成任务，加快首批结果产出并降低峰值内存
        notify_results: List[str] = []
        seen: Set[Tuple[str, str, str]] = set()
        for t in asyncio.as_completed(tasks):
            try:
                result = await t
            except Exception:
                continue
            task_result: Optional[Tuple[str, str]] = task_map.get(t)
            if task_result:
                group, url = task_result
            else:
                group, url = "", ""
            if result:
                # 对“full”状态降级为debug，非full保持info并参与去重与通知
                if isinstance(result, str) and 'full' in result.lower():
                    logger.debug('', extra={'group': group, 'url': url, 'result': result})
                else:
                    logger.info('', extra={'group': group, 'url': url, 'result': result})
                    if isinstance(result, str):
                        key = (group, url, result.lower())
                        if key not in seen:
                            notify_results.append(f"{group} - {url}: {result}")
                            seen.add(key)
        
        # 如果有需要通知的结果，则发送通知
        if notify_results:
            notifier = Notifier(NOFITY_CONFIG, AES_KEY)
            title = "TestFlight 状态更新"
            content = "\n".join(notify_results)
            await notifier.notify(title, content, platforms=["bark"])
            logger.info(f"本轮通知数量: {len(notify_results)}")
            
    end_time = time.time()
    logger.info(f"总耗时: {end_time - start_time:.2f} 秒")

async def main() -> None:
    if ENABLE_LOOP:
        # 循环运行模式
        start_time = time.time()
        loop_count = 0
        while True:
            loop_count += 1
            logger.info(f"\\n第 {loop_count} 轮检查开始...")
            await check_and_notify()
            
            # 检查是否达到循环总时长
            if LOOP_DURATION > 0 and (time.time() - start_time) >= LOOP_DURATION:
                logger.info("达到设定的循环总时长，停止运行")
                break
                
            logger.info(f"等待 {LOOP_INTERVAL} 秒后进行下一轮检查...")
            # 在终端原地更新剩余等待时间（覆盖同一行）
            import sys
            remaining = LOOP_INTERVAL
            while remaining > 0:
                sys.stdout.write("\r剩余等待时间: {} 秒{}".format(remaining, " " * 10))
                sys.stdout.flush()
                await asyncio.sleep(WAIT_UPDATE_STEP)
                remaining = max(0, remaining - WAIT_UPDATE_STEP)
            sys.stdout.write("\n")
    else:
        # 单次运行模式
        await check_and_notify()

if __name__ == '__main__':
    asyncio.run(main())