from datetime import datetime, timedelta, timezone
import os
import time
import requests

# 环境变量获取
ADDRESS = os.getenv("POLYMARKET_ADDRESS", "").strip().lower()
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "").strip()


def send_pushplus(title, content):
  if not PUSHPLUS_TOKEN:
    print("❌ 未配置 PUSHPLUS_TOKEN，跳过推送")
    return False
  url = "http://www.pushplus.plus/send"
  data = {
      "token": PUSHPLUS_TOKEN,
      "title": title,
      "content": content,
      "template": "html",
  }
  try:
    res = requests.post(url, json=data, timeout=10)
    print(f"🌐 PushPlus 推送响应状态码: {res.status_code}, 内容: {res.text}")
    return True
  except Exception as e:
    print(f"❌ PushPlus 推送异常: {e}")
    return False


def get_activity():
  if not ADDRESS:
    raise ValueError("未配置 POLYMARKET_ADDRESS 环境变量")

  # 拉取最近 10 条活动记录
  url = f"https://data-api.polymarket.com/activity?user={ADDRESS}&limit=10"
  headers = {"User-Agent": "Mozilla/5.0"}

  print(f"🔍 正在请求 Polymarket API: {url}")
  res = requests.get(url, headers=headers, timeout=15)
  print(f"📥 API 响应状态码: {res.status_code}")

  if res.status_code != 200:
    print(f"❌ 请求失败，响应内容: {res.text}")
    return []

  try:
    data = res.json()
    print(f"📦 成功解析 JSON 数据，共获取到 {len(data)} 条记录")
    return data
  except Exception as e:
    print(f"❌ JSON 解析失败: {e}")
    return []


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
      "FC Dinamo Minsk": "明斯克迪纳摩 (FC Dinamo Minsk)",
      "Slavia Mozyr": "莫济里斯拉维亚 (Slavia Mozyr)",
  }

  translated_desc = title
  for eng, cn in league_map.items():
    if eng in translated_desc:
      translated_desc = translated_desc.replace(eng, cn)

  return translated_desc


def main():
  print(f"🚀 开始执行监测脚本，目标地址: {ADDRESS}")
  activities = get_activity()

  if not activities:
    print("⚠️ 暂无活动记录或接口返回为空。")
    return

  current_time_utc = datetime.now(timezone.utc)
  sent_count = 0

  # 遍历获取到的每一条记录
  for idx, latest in enumerate(activities):
    print(f"\n-------------------- 正在检查第 {idx + 1} 条记录 --------------------")
    print(f"原始数据片段: {latest}")

    raw_timestamp = latest.get("timestamp")
    if not raw_timestamp:
      print("⚠️ 该条记录无 timestamp 字段，跳过。")
      continue

    try:
      ts = int(raw_timestamp)
      if ts > 1e12:
        ts = ts / 1000  # 兼容毫秒

      trade_datetime_utc = datetime.fromtimestamp(ts, timezone.utc)
      time_diff_seconds = (current_time_utc - trade_datetime_utc).total_seconds()

      dt_beijing = trade_datetime_utc.astimezone(timezone(timedelta(hours=8)))
      time_str = dt_beijing.strftime("%Y-%m-%d %H:%M:%S (北京时间)")

      print(
          f"⏱️ 订单时间: {time_str} | 距今约 {int(time_diff_seconds // 60)}"
          f" 分钟前 ({int(time_diff_seconds)}秒)"
      )

      # 放宽时间限制：检查 24 小时内（86400秒）的订单，确保不会漏掉
      if time_diff_seconds > 86400:
        print("⏳ 订单超过 24 小时，属于过旧订单，跳过。")
        continue

    except Exception as e:
      print(f"❌ 时间解析错误: {e}")
      continue

    # 提取交易核心字段
    trade_type = latest.get("type", "未知类型")
    original_title = latest.get("title", "未知市场")
    enhanced_title = translate_title_and_league(original_title)
    outcome = latest.get("outcome", "未知选项").upper()

    size = float(latest.get("size", 0))
    price = float(latest.get("price", 0))
    total_value = size * price

    # 构造富文本 HTML 通知内容
    title = "Polymarket 账号动态智能提醒"
    content = f"""
      <h3>📊 交易成交提醒</h3>
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

    print("📤 准备发送 PushPlus 通知...")
    if send_pushplus(title, content):
      sent_count += 1
      time.sleep(1)  # 暂停1秒防止请求过快

  print(f"\n✅ 本次运行结束，共成功发送 {sent_count} 条通知。")


if __name__ == "__main__":
  main()
