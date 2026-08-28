#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
未来 1 小时降水（雨/雪）微信提醒 —— 主程序。

用法:
  python main.py            正常检查：有降水则推送微信
  python main.py --dry-run  只打印判断结果，不推送、不改状态
  python main.py --test     给每个城市发一条测试消息（验证 token）
"""

import argparse
import json
import os
import sys
import time

from pushplus import send_pushplus
from weather_provider import fetch_forecast

DEFAULT_LOOKAHEAD = 60


def load_config():
    """优先读取 config.json（已 gitignore），否则用 config.example.json；环境变量覆盖密钥。"""
    path = "config.json" if os.path.exists("config.json") else "config.example.json"
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    if os.environ.get("PUSHPLUS_TOKEN"):
        cfg["pushplus_token"] = os.environ["PUSHPLUS_TOKEN"].strip()
    if os.environ.get("QWEATHER_KEY"):
        cfg["qweather_key"] = os.environ["QWEATHER_KEY"].strip()
    return cfg, path


def classify(minutes, threshold, snow_temp_c, lookahead):
    """在未来 lookahead 分钟内找降水。无降水返回 None，否则返回信息 dict。"""
    window = minutes[:lookahead]
    wet = [m for m in window if m["precip_mmh"] >= threshold]
    if not wet:
        return None
    first = wet[0]
    return {
        "start_offset": first["offset"],
        "duration": len(wet),                                     # 粗略持续分钟数
        "max_precip": max(m["precip_mmh"] for m in wet),          # mm/h
        "total_mm": sum(m["precip_mmh"] / 60.0 for m in wet),     # 未来1h累计 mm
        "temp": first["temp_c"],
        "is_snow": first["temp_c"] is not None and first["temp_c"] <= snow_temp_c,
    }


def intensity_label(max_precip_mmh, is_snow):
    if is_snow:
        levels = [(1.0, "小雪"), (2.5, "中雪"), (5.0, "大雪"), (999.0, "暴雪")]
    else:
        levels = [(2.5, "小雨"), (8.0, "中雨"), (16.0, "大雨"), (999.0, "暴雨")]
    for upper, label in levels:
        if max_precip_mmh < upper:
            return label
    return levels[-1][1]


def build_message(city, info, provider):
    kind = "下雪" if info["is_snow"] else "下雨"
    icon = "❄️" if info["is_snow"] else "🌧"
    label = intensity_label(info["max_precip"], info["is_snow"])
    start = info["start_offset"]
    start_text = "即将开始" if start <= 1 else f"约 {start} 分钟后开始"
    lines = [
        f'<b>{icon} {city["name"]} · 未来1小时内可能{kind}</b>',
        f'预计 {start_text}{kind}，持续约 {info["duration"]} 分钟',
        f'未来1小时累计降水约 {info["total_mm"]:.1f} mm，最大强度 {info["max_precip"]:.1f} mm/h（{label}）',
    ]
    if info["temp"] is not None:
        lines.append(f'当前气温约 {info["temp"]:.0f}℃')
    lines.append(f'<small style="color:#888">数据来源：{provider} · 每15分钟自动检查</small>')
    title = f'{icon} {city["name"]} 1小时内可能{kind}'
    return title, "<br>".join(lines)


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"cities": {}}


def save_state(path, state):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def should_push(state, city_key, now, dedupe_minutes):
    last = state.get("cities", {}).get(city_key, {}).get("last_push_ts", 0)
    return (now - last) >= dedupe_minutes * 60


def run(args):
    cfg, cfg_path = load_config()
    lookahead = int(cfg.get("lookahead_minutes", DEFAULT_LOOKAHEAD))
    threshold = float(cfg.get("precip_threshold_mmh", 0.1))
    snow_temp = float(cfg.get("snow_temp_c", 1.0))
    dedupe_minutes = int(cfg.get("dedupe_minutes", 90))
    state_path = cfg.get("state_file", "state.json")
    token = (cfg.get("pushplus_token") or "").strip()

    if args.test and not token:
        print("缺少 PushPlus token：请填写 config.json 或设置环境变量 PUSHPLUS_TOKEN")
        return 2

    print(f"使用配置: {cfg_path} | 提前量 {lookahead} 分钟 | 降水阈值 {threshold} mm/h | provider={cfg.get('provider')}")
    state = load_state(state_path)
    now = int(time.time())
    changed = False

    for city in cfg.get("cities", []):
        key = f"{city['name']}_{city['lat']}_{city['lon']}"
        fc = None
        try:
            fc = fetch_forecast(city, cfg, lookahead)
        except Exception as exc:
            print(f"[{city['name']}] 获取预报失败: {exc}")
            if not args.test:
                continue

        if args.test:
            src = fc["provider"] if fc else "N/A"
            title = f"✅ 测试消息：{city['name']} 提醒服务正常"
            html = (f'<b>{city["name"]} 测试推送成功</b><br>'
                    f'配置：提前量 {lookahead} 分钟，阈值 {threshold} mm/h<br>'
                    f'<small>数据源：{src}</small>')
            if _send(token, title, html):
                print(f"[{city['name']}] 测试推送成功（数据源 {src}）")
            else:
                print(f"[{city['name']}] 测试推送失败")
            continue

        if fc is None:
            continue

        info = classify(fc["minutes"], threshold, snow_temp, lookahead)
        if info is None:
            print(f"[{city['name']}] 未来 {lookahead} 分钟内无降水（{fc['provider']}）")
            continue

        title, html = build_message(city, info, fc["provider"])
        print(f"[{city['name']}] 检测到: {title}")

        if args.dry_run:
            print(f"    (dry-run，不会发送) {html}")
            continue

        if should_push(state, key, now, dedupe_minutes):
            if _send(token, title, html):
                state.setdefault("cities", {})[key] = {"last_push_ts": now}
                changed = True
                print(f"[{city['name']}] 已推送微信")
            else:
                print(f"[{city['name']}] 推送失败")
        else:
            print(f"[{city['name']}] 在去重窗口内（{dedupe_minutes} 分钟），跳过推送")

    if changed:
        save_state(state_path, state)
    return 0


def _send(token, title, html):
    if not token:
        print("    缺少 PushPlus token，跳过推送")
        return False
    try:
        send_pushplus(token, title, html)
        return True
    except Exception as exc:
        print(f"    推送异常: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="未来1小时降水(雨/雪)微信提醒")
    parser.add_argument("--test", action="store_true", help="给每个城市发一条测试消息")
    parser.add_argument("--dry-run", action="store_true", help="只打印判断结果，不推送")
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
