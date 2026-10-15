import os
import time
import requests

# 环境变量获取
ADDRESS = os.getenv("POLYMARKET_ADDRESS", "").strip().lower()
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "").strip()

def send_pushplus(title, content):
    if not PUSHPLUS_TOKEN:
        print("未配置 PUSHPLUS_TOKEN，跳过推送")
        return
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        res = requests.post(url, json=data, timeout=10)
        print("PushPlus 推送响应:", res.text)
    except Exception as e:
        print("PushPlus 推送失败:", e)

def get_activity():
    if not ADDRESS:
        raise ValueError("未配置 POLYMARKET_ADDRESS 环境变量")
    
    # 使用 Polymarket 公开 Data API 查询活动日志（订单/成交）
    url = f"https://data-api.polymarket.com/activity?user={ADDRESS}&limit=10"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    res = requests.get(url, headers=headers, timeout=15)
    if res.status_code != 200:
        print(f"请求失败，状态码: {res.status_code}, 响应: {res.text}")
        return []
    
    return res.json()

def main():
    print(f"开始轮询地址: {ADDRESS}")
    activities = get_activity()
    print(f"拉取到 {len(activities)} 条最近活动数据")
    
    if not activities:
        print("暂无活动记录。")
        return
    
    # 模拟通知：打印最新一条记录
    latest = activities[0]
    title = "Polymarket 账号动态提醒"
    content = f"""
    <h3>最新活动记录</h3>
    <p><b>类型:</b> {latest.get('type', '未知')}</p>
    <p><b>市场:</b> {latest.get('title', '未知市场')}</p>
    <p><b>数量:</b> {latest.get('size', '0')} | <b>价格:</b> ${latest.get('price', '0')}</p>
    <p><b>时间:</b> {latest.get('timestamp', '')}</p>
    """
    print("触发推送测试...")
    send_pushplus(title, content)

if __name__ == "__main__":
    main()
