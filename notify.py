import asyncio
import aiohttp
import os
import logging
from base64 import b64decode
from Crypto.Cipher import AES

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class Notifier:
    def __init__(self, config, aes_key=None):
        """
        config: {
            "webhook": [...],
            "wechat": [{"corp_id": "...", "agent_id": "...", "secret_enc": "...", "to_user": "..."}],
            "bark": [...]
        }
        aes_key: 企业微信secret解密密钥（16/24/32字节），建议通过环境变量传入
        """
        self.config = config
        self.aes_key = aes_key or os.getenv("WX_AES_KEY")

    def decrypt_secret(self, secret_enc):
        # AES-ECB解密，secret_enc为base64编码
        # 检查aes_key是否为bytes类型，如果不是才进行编码
        key = self.aes_key if isinstance(self.aes_key, bytes) else self.aes_key.encode()
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = cipher.decrypt(b64decode(secret_enc))
        # 去除填充
        pad = decrypted[-1]
        return decrypted[:-pad].decode()

    async def send_webhook(self, session, url, title, content):
        payload = {"title": title, "content": content}
        try:
            async with session.post(url, json=payload, timeout=5) as resp:
                result = await resp.text()
                logging.info(f"Webhook发送成功: {url} 响应: {result}")
                return result
        except Exception as e:
            logging.error(f"Webhook发送失败: {url} 错误: {e}")
            return f"Webhook发送失败: {e}"

    async def send_wechat(self, session, conf, title, content):
        if "secret_enc" not in conf:
            logging.error(f"企业微信配置缺少secret_enc: {conf}")
            return "企业微信发送失败: 缺少secret_enc"
        try:
            secret = self.decrypt_secret(conf["secret_enc"])
            token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={conf['corp_id']}&corpsecret={secret}"
            async with session.get(token_url, timeout=5) as resp:
                token = (await resp.json())["access_token"]
            msg_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
            payload = {
                "touser": conf["to_user"],
                "msgtype": "text",
                "agentid": conf["agent_id"],
                "text": {"content": f"{title}\n{content}"},
                "safe": 0
            }
            async with session.post(msg_url, json=payload, timeout=5) as resp:
                result = await resp.text()
                logging.info(f"企业微信发送成功: {conf['corp_id']} 响应: {result}")
                return result
        except Exception as e:
            logging.error(f"企业微信发送失败: {conf.get('corp_id', '未知ID')} 错误: {e}")
            return f"企业微信发送失败: {e}"

    async def send_bark(self, session, url, title, content):
        url = b64decode(url).decode() if url.startswith("aHR0") else url
        bark_url = f"{url}/{title}/{content}"
        try:
            async with session.get(bark_url, timeout=5) as resp:
                result = await resp.text()
                logging.info(f"Bark发送成功: {url} 响应: {result}")
                return result
        except Exception as e:
            logging.error(f"Bark发送失败: {url} 错误: {e}")
            return f"Bark发送失败: {e}"

    async def notify(self, title, content, platforms=None):
        """
        platforms: ['webhook', 'wechat', 'bark']，为None则全部发送
        """
        tasks = []
        # 创建不验证SSL证书的连接器
        connector = aiohttp.TCPConnector(verify_ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            if platforms is None or "webhook" in platforms:
                for url in self.config.get("webhook", []):
                    tasks.append(self.send_webhook(session, url, title, content))
            if platforms is None or "wechat" in platforms:
                for conf in self.config.get("wechat", []):
                    tasks.append(self.send_wechat(session, conf, title, content))
            if platforms is None or "bark" in platforms:
                for url in self.config.get("bark", []):
                    tasks.append(self.send_bark(session, url, title, content))
            results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"通知任务{idx}异常: {result}")
            else:
                logging.info(f"通知任务{idx}结果: {result}")
        return results

# 使用示例
# config = {
#     "webhook": ["https://webhook.site/xxx"],
#     "wechat": [{
#         "corp_id": "xxx",
#         "agent_id": "1000002",
#         "secret_enc": "加密后的base64字符串",
#         "to_user": "@all"
#     }],
#     "bark": ["https://api.day.app/yourkey"]
# }

if __name__ == "__main__":
    from config import NOFITY_CONFIG,AES_KEY
    notifier = Notifier(NOFITY_CONFIG,AES_KEY)
    # 只发送到企业微信和Bark
    asyncio.run(notifier.notify("测试标题", "测试内容", platforms=["bark"]))
