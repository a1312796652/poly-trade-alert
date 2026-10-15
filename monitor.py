from datetime import datetime, timedelta, timezone
import os
import re
import subprocess
import time
import requests

# 环境变量获取
ADDRESS = os.getenv("POLYMARKET_ADDRESS", "").strip().lower()
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "")

HISTORY_FILE = "sent_history.txt"


def load_sent_history():
  """从本地读取已发送过的订单记录"""
  if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
      return set(line.strip() for line in f if line.strip())
  return set()


def save_sent_history(tx_id):
  """将新发送的订单 ID 写入文件，并自动提交到 GitHub 仓库保存"""
  with open(HISTORY_FILE, "a", encoding="utf-8") as f:
    f.write(f"{tx_id}\n")
  print(f"📝 已将交易 {tx_id} 写入本地历史记录。")

  if GITHUB_TOKEN and REPO_NAME:
    try:
      print("🔄 正在将历史记录自动同步到 GitHub 仓库...")
      subprocess.run(
          ["git", "config", "--global", "user.name", "github-actions[bot]"],
          check=True,
      )
      subprocess.run(
          [
              "git",
              "config",
              "--global",
              "user.email",
              "41898282+github-actions[bot]@users.noreply.github.com",
          ],
          check=True,
      )
      subprocess.run(["git", "add", HISTORY_FILE], check=True)
      subprocess.run(
          ["git", "commit", "-m", f"chore: update sent history for {tx_id}"],
          check=True,
      )
      remote_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{REPO_NAME}.git"
      subprocess.run(["git", "push", remote_url, "HEAD:main"], check=True)
      print("✅ 历史记录成功持久化保存到 GitHub！")
    except Exception as e:
      print(f"⚠️ 自动同步历史记录到 Git 失败（不影响本次发送）: {e}")


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

  url = f"https://data-api.polymarket.com/activity?user={ADDRESS}&limit=10"
  headers = {"User-Agent": "Mozilla/5.0"}

  res = requests.get(url, headers=headers, timeout=15)
  if res.status_code != 200:
    print(f"❌ 请求失败，响应内容: {res.text}")
    return []

  try:
    return res.json()
  except Exception as e:
    print(f"❌ JSON 解析失败: {e}")
    return []


def translate_title_and_league(title):
  """智能正则匹配与中英文对照优化函数（无需手动维护球队字典）"""
  # 1. 常用专业术语与联赛替换
  replacements = {
      "Premier League": "英超联赛 (Premier League)",
      "La Liga": "西甲联赛 (La Liga)",
      "Serie A": "意甲联赛 (Serie A)",
      "Bundesliga": "德甲联赛 (Bundesliga)",
      "Champions League": "欧冠联赛 (Champions League)",
      "O/U": "大小球 (O/U)",
      "Over": "大球",
      "Under": "小球",
  }

  translated = title
  for eng, cn in replacements.items():
    translated = translated.replace(eng, cn)

  # 2. 智能匹配 "Will [Team] win on [Date]?" 模式
  match_win = re.match(r"Will\s+(.+?)\s+win\s+on\s+(.+?)\?", title, re.IGNORECASE)
  if match_win:
    team = match_win.group(1)
    date_str = match_win.group(2)
    translated = f"球队 [{team}] 是否能在 {date_str} 获胜？"

  # 3. 智能匹配 "Team A vs. Team B" 模式
  if " vs. " in title:
    translated = translated.replace(" vs. ", " 对阵 ")
  elif " vs " in title:
    translated = translated.replace(" vs ", " 对阵 ")

  # 4. 始终保留双语对照：上方展示优化后的中文意境，下方附带英文原名
  if translated != title:
    return f"{translated}<br><span style='color: #888; font-size: 13px;'>原标题: {title}</span>"
  else:
    return title


def main():
  print(f"🚀 开始执行监测脚本，目标地址: {ADDRESS}")
  sent_history = load_sent_history()
  print(f"📖 本地已加载历史发送记录数: {len(sent_history)}")

  activities = get_activity()
  if not activities:
    print("⚠️ 暂无活动记录。")
    return

  # 倒序遍历（从旧到新），确保按时间顺序推送
  activities.reverse()

  sent_count = 0
  for latest in activities:
    raw_timestamp = str(latest.get("timestamp", ""))
    size = str(latest.get("size", ""))
    price = str(latest.get("price", ""))
    market_title = str(latest.get("title", ""))

    if not raw_timestamp:
      continue

    tx_id = f"{raw_timestamp}_{size}_{price}_{market_title[:15]}"

    # 去重检查
    if tx_id in sent_history:
      continue

    print(f"✨ 发现未发送过的新订单！ID: {tx_id}")

    try:
      ts = int(raw_timestamp)
      if ts > 1e12:
        ts = ts / 1000
      trade_datetime_utc = datetime.fromtimestamp(ts, timezone.utc)
      dt_beijing = trade_datetime_utc.astimezone(timezone(timedelta(hours=8)))
      time_str = dt_beijing.strftime("%Y-%m-%d %H:%M:%S (北京时间)")
    except Exception as e:
      print(f"❌ 时间解析错误: {e}")
      time_str = "未知时间"

    trade_type = latest.get("type", "未知类型")
    enhanced_title = translate_title_and_league(market_title)
    outcome = latest.get("outcome", "未知选项").upper()

    size_val = float(latest.get("size", 0))
    price_val = float(latest.get("price", 0))
    total_value = size_val * price_val

    title = "Polymarket 账号动态智能提醒"
    content = f"""
      <h3>📊 交易成交提醒</h3>
      <p><b>类型：</b>{trade_type}</p>
      <p><b>市场/赛事 (智能对照)：</b><br>{enhanced_title}</p>
      <hr>
      <p><b>👉 购买选项：</b><span style="color: #007bff; font-size: 16px;"><b>{outcome}</b></span></p>
      <p><b>📦 成交份额：</b>{size_val:.2f} 股</p>
      <p><b>💲 成交价格/赔率：</b>${price_val:.3f}</p>
      <p><b>💰 订单总价值：</b><b>${total_value:.2f} USDC</b></p>
      <hr>
      <p><b>下单时间：</b>{time_str}</p>
      """

    print("📤 正在发送 PushPlus 通知...")
    if send_pushplus(title, content):
      save_sent_history(tx_id)
      sent_history.add(tx_id)
      sent_count += 1
      time.sleep(1)

  print(f"\n✅ 本次运行结束，共成功发送并记录 {sent_count} 条新交易。")


if __name__ == "__main__":
  main()
