#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分钟级降水预报数据源（仅标准库）。

- 和风天气 (qweather)：雷达外推的分钟级降水预报，最准（需要免费 key，可选）
- Open-Meteo (openmeteo)：免注册、无 key，15 分钟粒度的降水/温度，兜底用

provider 配置项：
  "auto"      有和风 key 用和风，失败或没 key 自动切 Open-Meteo（推荐）
  "qweather"  强制和风
  "openmeteo" 强制 Open-Meteo
"""

import datetime as dt
import json
import urllib.parse
import urllib.request

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "weather-reminder/1.0 (+https://pushplus.plus)"


class ProviderError(RuntimeError):
    pass


def _http_get_json(url, params=None, headers=None, timeout=20):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_forecast(city, cfg, lookahead_minutes):
    """
    返回:
      {
        "provider": "qweather" | "open-meteo",
        "summary": str,            # 数据源自带的文字总结（可能为空）
        "minutes": [ { "offset": 分钟偏移, "precip_mmh": mm/h, "temp_c": 气温或None }, ... ]
      }
    """
    errors = []
    provider = str(cfg.get("provider", "auto")).lower()
    if provider in ("qweather", "auto") and cfg.get("qweather_key"):
        try:
            return _qweather(city, cfg, lookahead_minutes)
        except Exception as exc:
            errors.append(f"和风天气: {exc}")
            print(f"[{city['name']}] 和风天气查询失败({exc})，尝试备用数据源…")
    try:
        return _openmeteo(city, cfg, lookahead_minutes)
    except Exception as exc:
        errors.append(f"Open-Meteo: {exc}")
    raise ProviderError("所有天气数据源均失败: " + " | ".join(errors))


# ---------------------------------------------------------------- 和风天气
def _qweather(city, cfg, lookahead):
    base = str(cfg.get("qweather_base", "https://devapi.qweather.com")).rstrip("/")
    key = str(cfg["qweather_key"]).strip()
    loc = f"{city['lon']},{city['lat']}"

    # 同时支持旧版 key 参数与新控制台的 X-QW-Api-Key 请求头
    auth_headers = {"X-QW-Api-Key": key}
    data = _http_get_json(f"{base}/v7/precipitation/minutely",
                          {"location": loc, "key": key}, headers=auth_headers)
    if str(data.get("code")) != "200":
        raise ProviderError(f"code={data.get('code')} {data.get('msg', '')}".strip())
    minutely = data.get("minutely") or []

    # 逐小时温度（用于判断雨/雪）
    temp_by_hour, temp_now = {}, None
    try:
        rh = _http_get_json(f"{base}/v7/weather/24h", {"location": loc, "key": key},
                            headers=auth_headers)
        if str(rh.get("code")) == "200":
            for h in rh.get("hourly") or []:
                try:
                    fx = dt.datetime.fromisoformat(h["fxTime"])
                    temp_by_hour[fx.hour] = float(h.get("temp") or 0)
                except Exception:
                    pass
            temp_now = temp_by_hour.get(_now_local().hour)
    except Exception:
        pass

    minutes = []
    for i in range(lookahead):
        if i < len(minutely):
            try:
                precip = float(minutely[i])
            except (TypeError, ValueError):
                precip = 0.0
            hour = (_now_local().hour + i // 60) % 24
            temp = temp_by_hour.get(hour, temp_now)
        else:
            precip, temp = 0.0, temp_now
        minutes.append({"offset": i, "precip_mmh": precip, "temp_c": temp})
    return {"provider": "qweather", "summary": str(data.get("summary") or ""), "minutes": minutes}


# ---------------------------------------------------------------- Open-Meteo
def _openmeteo(city, cfg, lookahead):
    slots_needed = max(1, -(-lookahead // 15) + 1)  # ceil(lookahead/15) + 1 保险
    params = {
        "latitude": city["lat"],
        "longitude": city["lon"],
        "minutely_15": "precipitation,temperature",
        "forecast_minutely_15": min(slots_needed, 96),  # 最多取4天
        "timezone": "Asia/Shanghai",
    }
    d = _http_get_json(OPENMETEO_URL, params)
    m = d.get("minutely_15") or {}
    times = m.get("time") or []
    prec = m.get("precipitation") or []
    temps = m.get("temperature") or []
    if not times:
        raise ProviderError("Open-Meteo 未返回分钟级数据")

    minutes = []
    for i in range(lookahead):
        slot = i // 15
        if slot < len(prec) and prec[slot] is not None:
            precip = float(prec[slot]) * 4.0  # mm/15min -> mm/h
        else:
            precip = 0.0
        temp = None
        if slot < len(temps) and temps[slot] is not None:
            temp = float(temps[slot])
        minutes.append({"offset": i, "precip_mmh": precip, "temp_c": temp})
    return {"provider": "open-meteo", "summary": "", "minutes": minutes}


def _now_local():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
