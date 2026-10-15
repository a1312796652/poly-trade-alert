from datetime import datetime, timedelta, timezone
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
      "template": "html",
  }
  try:
    res = requests.post(url, json=data, timeout=10)
    print("PushPlus 推送响应:", res.text)
  except Exception as e:
    print("PushPlus 推送失败:", e)


def get_activity():
  if not ADDRESS:
    raise ValueError("未配置 POLYMARKET_ADDRESS 环境变量")

  # 使用 Polymarket 公开 Data API 查询活动日志 (订单/成交)
  url = f"https://data-api.polymarket.com/activity?user={ADDRESS}&limit=10"
  headers = {"User-Agent": "Mozilla/5.0"}

  res = requests.get(url, headers=headers, timeout=15)
  if res.status_code != 200:
    print(f"请求失败，状态码: {res.status_code}，响应: {res.text}")
    return []

  return res.json()


def translate_title_and_league(title):
  """基础的中英文映射和语义优化函数"""
  league_map = {
      "Premier League": "英超联赛 (Premier League)",
      "La Liga": "西甲联赛 (La Liga)",
      "Serie A": "意甲联赛 (Serie A)",
      "Bundesliga": "德甲联赛 (Bundesliga)",
      "Champions League": "欧冠联赛 (Champions League)",
      "Hong Kong Premier League": "香港超级联赛 (Hong Kong Premier League)",
      "Tai Po FC": "大埔足球俱乐部 (Tai Po FC)",
  }

  translated_desc = title
  for eng, cn in league_map.items():
    if eng in translated_desc:
      translated_desc = translated_desc.replace(eng, cn)

  return translated_desc


def main():
  print(f"开始验证地址: {ADDRESS}")
  activities = get_activity()
  print(f"拉取到 {len(activities)} 条最近活动数据")

  if not activities:
    print("暂无活动记录。")
    return

  # 获取最新一条记录
  latest = activities[0]

  # 1. 检查交易时间，过滤掉旧消息（防重复推送核心逻辑）
  raw_timestamp = latest.get("timestamp")
  if not raw_timestamp:
    print("未获取到有效时间戳，跳过。")
    return

  try:
    ts = int(raw_timestamp)
    if ts > 1e12:
      ts = ts / 1000  # 兼容毫秒级时间戳

    trade_datetime_utc = datetime.fromtimestamp(ts, timezone.utc)
    current_time_utc = datetime.now(timezone.utc)

    # 计算交易距离当前时间过去了几秒
    time_diff_seconds = (current_time_utc - trade_datetime_utc).total_seconds()

    # 如果这笔交易已经过去超过 15 分钟（900秒），说明是旧交易，直接跳过不发！
    if time_diff_seconds > 900:
      print(
          f"最新交易产生于 {int(time_diff_seconds // 60)} 分钟前，属于旧消息，"
          "跳过推送。"
      )
      return

    # 转换为北京时间展示
    dt_beijing = trade_datetime_utc.astimezone(timezone(timedelta(hours=8)))
    time_str = dt_beijing.strftime("%Y-%m-%d %H:%M:%S (北京时间)")
  except Exception as e:
    print(f"时间解析错误: {e}")
    return

  # 2. 提取交易核心字段
  trade_type = latest.get("type", "未知类型")
  original_title = latest.get("title", "未知市场")
  enhanced_title = translate_title_and_league(original_title)

  # 提取买入选项 (YES / NO)
  outcome = latest.get("outcome", "未知选项").upper()

  size = float(latest.get("size", 0))
  price = float(latest.get("price", 0))
  total_value = size * price  # 计算成交总价值

  # 3. 构造富文本 HTML 通知内容
  title = "Polymarket 账号动态智能提醒"
  content = f"""
    <h3>📊 最新交易成交提醒</h3>
    <p><b>类型：</b>{trade_type}</p>
    <p><b>市场/赛事 (中英对照)：</b><br>{enhanced_title}</p>
    <hr>
    <p><b>👉 购买选项：</b><span style="color: #007bff; font-size: 16px;"><b>{outcome}</b></span></p>
    <p><b>📦 成交份额：</b>{size:.2f} 股</p>
    <p><b>💲 成交价格/赔率：</b>${price:.3f}</p>
    <p><b>💰 订单总价值：</b><b>${total_value:.2f} USDC</b></p>
    <hr>
    <p><b>下单时间：</b>{time_str}</p>
    """

  print("检测到新交易，触发推送...")
  send_pushplus(title, content)


if __name__ == "__main__":
  main()
