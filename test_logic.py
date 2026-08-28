#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线逻辑测试（不依赖网络、不需要 token）：
  python test_logic.py
覆盖: 无降水 / 有雨 / 下雪 / 强度分级 / 消息格式 / 去重状态
"""
import json
import os
import sys
import tempfile
import time

import main as M


def make_minutes(precip_seq, temp):
    """precip_seq: 每分钟降水强度 mm/h 列表（不足部分补0）"""
    return [{"offset": i, "precip_mmh": v, "temp_c": temp} for i, v in enumerate(precip_seq)]


def t(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        sys.exit(1)


# ---- 1. 无降水
m = make_minutes([0] * 60, 15.0)
info = M.classify(m, 0.1, 1.0, 60)
t("无降水 → None", info is None)

# ---- 2. 30分钟后开始下雨
m = make_minutes([0] * 30 + [0.5] * 30, 12.0)
info2 = M.classify(m, 0.1, 1.0, 60)
info = info2
t("有降水且非None", info is not None)
t("起始偏移=30", info["start_offset"] == 30)
t("持续约30分钟", info["duration"] == 30)
t("非雪(12℃)", info["is_snow"] is False)
t("小雨标签", M.intensity_label(info["max_precip"], False) == "小雨")

# ---- 3. 低温下雪
m = make_minutes([0.5] * 60, -3.0)
info = M.classify(m, 0.1, 1.0, 60)
t("-3℃ → 判定为雪", info["is_snow"] is True)
t("雪强度标签", M.intensity_label(info["max_precip"], True) == "小雪")

# ---- 4. 大雨分级
m = make_minutes([10] * 60, 20.0)
info = M.classify(m, 0.1, 1.0, 60)
t("10mm/h → 大雨", M.intensity_label(info["max_precip"], False) == "大雨")

# ---- 5. 消息格式（用“30分钟后开始”的用例）
title, html = M.build_message({"name": "长春", "lat": 1, "lon": 2}, info2, "open-meteo")
t("标题含城市和'下雨'", "长春" in title and "下雨" in title)
t("内容含分钟数", "分钟后开始" in html)

# ---- 6. 去重状态
state = {"cities": {"长春_1_2": {"last_push_ts": int(time.time())}}}
t("刚推送过 → 不去重不推", M.should_push(state, "长春_1_2", int(time.time()), 90) is False)
state = {"cities": {}}
t("从未推送 → 应该推", M.should_push(state, "长春_1_2", int(time.time()), 90) is True)

# ---- 7. config 加载（无网络，只验证读取）
cfg, path = M.load_config()
t("读取到 cities", len(cfg.get("cities", [])) == 2)
t("默认提前量60", cfg.get("lookahead_minutes", 60) == 60)

print("\n全部通过 ✅")
