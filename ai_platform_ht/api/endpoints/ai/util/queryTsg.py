import json
import time
import logging
import os
import platform
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager  # 需要安装：pip install webdriver-manager

# 抑制第三方库（Selenium、urllib3、WDM等）的冗余日志打印
os.environ['WDM_LOG'] = '0'
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("WDM").setLevel(logging.WARNING)

# 配置当前模块日志
logger = logging.getLogger(__name__)

def search_books(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    根据关键字在图书馆系统搜索书籍，并返回前几条记录。
    
    :param keyword: 搜索关键字（书名、作者、出版社等）
    :param limit: 返回的最大记录数，默认为 5
    :return: 包含书籍信息的字典列表，主要包含：callNo, location, author, publisher, title 等字段
    """
    # 设置 Chrome 选项
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")  # 使用新版无头模式，解决很多崩溃问题
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")  # 兼容 Linux (Ubuntu) 系统，解决 /dev/shm 共享内存不足的问题
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data")  # 指定一个有权限写入的目录，防止非 root 用户权限不足导致崩溃
    chrome_options.add_argument("--remote-debugging-port=9222") # 暴露调试端口，有时候能防止异常退出
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")  # 抑制 Chromium 自身的终端日志
    # 启用性能日志
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # 自动识别系统和架构以决定驱动加载方式
    system_os = platform.system().lower()
    machine_arch = platform.machine().lower()

    if system_os == "linux" and machine_arch in ["aarch64", "arm64"]:
        # 在 Ubuntu ARM64 (如 Thor) 环境下，不使用 webdriver-manager，而是使用系统安装的 chromium-chromedriver
        # 需确保系统中已安装: sudo apt install -y chromium-browser chromium-chromedriver
        chrome_options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
    else:
        # 其他环境（如 Windows）继续使用 webdriver-manager 自动下载并管理驱动
        service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    result_list = []

    try:
        logger.info(f"🚀 正在启动浏览器 (无头模式)，准备搜索关键字: '{keyword}'...")
        driver.get("https://inventory-robot.st-saas.com/#/")
        wait = WebDriverWait(driver, 15)
        
        logger.info("🔍 正在定位搜索框...")
        input_element = wait.until(EC.presence_of_element_located((By.ID, "van-search-1-input")))
        input_element.clear()
        input_element.send_keys(keyword)
        
        # 触发 change 事件以启动搜索
        logger.info("⌨️ 正在触发搜索请求...")
        driver.execute_script(
            "var event = new Event('change', { bubbles: true });"
            "arguments[0].dispatchEvent(event);",
            input_element
        )
        
        # 等待网络请求完成
        logger.info("⏳ 等待接口响应...")
        time.sleep(5)
        
        # 获取性能日志并解析
        logs = driver.get_log('performance')
        target_url_fragment = "/api/bookInfo/page"
        found = False
        
        for entry in logs:
            log = json.loads(entry['message'])['message']
            if log['method'] == 'Network.responseReceived':
                url = log['params']['response']['url']
                if target_url_fragment in url:
                    request_id = log['params']['requestId']
                    try:
                        # 使用 CDP 获取响应正文
                        response_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                        data = json.loads(response_body['body'])
                        
                        # 提取并处理 records
                        records = data.get('result', {}).get('records', [])
                        # 检查 records 是否为空
                        if records:
                            logger.info(f"✅ 成功截获接口: {url}，共获取 {len(records)} 条记录")
                            found = True
                            
                            # 提取前 limit 条，并过滤所需字段
                            for i, record in enumerate(records):
                                if i >= limit:
                                    break
                                
                                result_list.append({
                                    "id": record.get("id", ""),
                                    "tagId": record.get("tagId", ""),
                                    "classifyName": record.get("classifyName", ""),
                                    "barCode": record.get("barCode", ""),
                                    "title": record.get("title", ""),
                                    "callNo": record.get("callNo", ""),
                                    "floor": record.get("floor", ""),
                                    "location": record.get("location", ""),
                                    "author": record.get("author", ""),
                                    "publisher": record.get("publisher", ""),
                                    "coverSrc": record.get("coverSrc", ""),
                                    "locationSrc": record.get("locationSrc", ""),
                                    "status": record.get("status", 1),
                                    "shape": record.get("shape", ""),
                                    "creatorBy": record.get("creatorBy"),
                                    "creatorTime": record.get("creatorTime"),
                                    "menderBy": record.get("menderBy"),
                                    "menderTime": record.get("menderTime")
                                })
                            break # 找到接口并提取数据后即可退出循环
                        else:
                            logger.warning("⚠️ 接口响应成功，但 records 列表为空。")
                    except Exception as e:
                        # 某些情况下响应可能已被回收或无法获取
                        logger.error(f"❌ 解析响应体时出错: {e}")
                        pass
        
        if not found:
            logger.warning(f"❌ 未能在性能日志中找到包含 '{target_url_fragment}' 的接口响应。")

    except Exception as e:
        logger.error(f"❌ 运行出错: {e}")
    finally:
        driver.quit()
        logger.info("👋 浏览器已关闭。")
        
    return result_list