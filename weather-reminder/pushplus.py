#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PushPlus(推送加) 微信推送客户端（仅标准库）。"""

import json
import urllib.request

SEND_URL = "https://www.pushplus.plus/send"
USER_AGENT = "weather-reminder/1.0"


def send_pushplus(token, title, content_html, template="html"):
    """发送微信推送，返回响应 dict；失败抛异常。"""
    payload = {
        "token": token,
        "title": title,
        "content": content_html,
        "template": template,
    }
    req = urllib.request.Request(
        SEND_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if str(data.get("code")) != "200":
        raise RuntimeError(f"PushPlus 返回异常: {data}")
    return data
