# 微信雨雪提醒（长春 + 阳泉）

> 👉 **不熟悉 GitHub 的朋友先看这个：** [`小白部署步骤.md`](小白部署步骤.md) —— 全程浏览器操作，照着点就行。

**7×24 小时自动监控长春、阳泉两市的分钟级降水预报，如果未来 1 小时内可能下雨或下雪，通过 PushPlus 推送到你的个人微信。**

你不需要电脑常开 —— 整个检查循环跑在 GitHub Actions 免费云定时上，每 15 分钟一次，全天候运行。

---

## 它是怎么工作的

```
GitHub Actions 定时器（每15分钟）
        │
        ▼
  获取两市分钟级降水预报
  （和风天气雷达外推，最准；失败或无key时自动切换 Open-Meteo，免注册）
        │
        ▼
 未来 60 分钟内任一分钟降水强度 ≥ 0.1 mm/h？
        │
        ├─ 否 → 什么都不做，等下一轮
        │
        └─ 是 → 判断雨/雪（气温 ≤ 1℃ 记为雪）
                    │
                    ▼
         通过 PushPlus 推送到你的微信
         （同一城市 90 分钟内不重复打扰，避免连发轰炸）
```

## 你需要准备什么

| 项目 | 是否必须 | 说明 |
|---|---|---|
| GitHub 账号 | ✅ 必须 | 免费；托管定时任务 |
| PushPlus token | ✅ 必须 | 免费；负责把消息推到你微信 |
| 和风天气 key | ⬜ 可选 | 免费；更准的分钟级降水。不填也能用（自动用 Open-Meteo） |

> 两个城市（长春、阳泉）和坐标已经预设在 `config.example.json` 里，无需修改即可使用。
> 代码只用 Python 标准库、零第三方依赖，GitHub 云端自带 Python，你**本机甚至不需要装 Python**。

---

## 第一步：注册 PushPlus 拿到 token

1. 打开 <https://www.pushplus.plus/> ，用微信扫码登录
2. 按提示**关注公众号「pushplus 推送加」**（不关注收不到消息）
3. 登录后首页会显示你的 **token**（一长串字符），复制保存
4. 免费额度对"下雨才提醒"这种低频推送完全够用

## 第二步（可选）：注册和风天气拿 key

1. 打开 <https://dev.qweather.com/> → 注册 → 控制台创建项目
2. 订阅选「免费版」即可，拿到 `API Key`（以及控制台里的 API Host，如 `https://xxx.re.qweatherapi.com`）
3. 免费版每天 1000 次调用，本方案每天只用约 192 次，绰绰有余
4. 如果 key 没有分钟级降水权限，程序会自动切到 Open-Meteo，不会中断

---

## 第三步：上传代码到 GitHub 并开启自动定时

### 3.1 新建 GitHub 仓库

打开 <https://github.com/new> ，仓库名填 `weather-reminder`，选 **Public（公开）**。
> 推荐公开：公开仓库的 Actions 分钟数**无限**，定时任务也不会因仓库闲置 60 天被暂停。
> 密钥都放在 GitHub Secrets 里（见 3.3），不会泄露到代码中。

### 3.2 把代码推上去

在命令行（或 Git Bash）里，进入本项目文件夹后执行：

```bash
git init
git add .
git commit -m "init: 微信雨雪提醒"
git branch -M main
git remote add origin https://github.com/你的用户名/weather-reminder.git
git push -u origin main
```

（如果你更习惯网页操作：也可以把本文件夹里的文件直接拖到仓库网页的"上传文件"页面。）

### 3.3 添加密钥（Secrets）

仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**：

| 名称 | 值 |
|---|---|
| `PUSHPLUS_TOKEN` | 第一步复制的 PushPlus token |
| `QWEATHER_KEY` | 第二步的和风 key（可跳过） |

### 3.4 手动验证一次

仓库页面 → **Actions** → 左侧选中「微信雨雪提醒」工作流 → 右侧 **Run workflow** → 模式选 `test` → 点绿色按钮。

等 1~2 分钟运行结束后，你的微信应该收到类似：

> ✅ 测试消息：长春 提醒服务正常

收到即代表全链路打通，之后每 15 分钟自动检查一次，不再需要你做任何操作。

---

## 第四步（可选）：本机手动运行 / 测试

电脑临时开着时可以直接本地跑（需本机装有 Python 3.9+，无需任何 pip 安装）：

- 双击 `test_push.bat` —— 发一条测试消息（需要先在本文件夹的 `config.json` 里填 token，或设置环境变量 `PUSHPLUS_TOKEN`）
- 双击 `run_local.bat` —— 跑一轮正常检查
- 命令行 `python main.py --dry-run` —— 只看判断结果、不推送、不改状态

```jsonc
// config.json（复制自 config.example.json，已被 .gitignore 忽略，不会提交）
{
  "pushplus_token": "你的token",   // 本地运行需要填；GitHub 上用 Secrets，不填
  "qweather_key": "",              // 可选
  ...
}
```

---

## 自定义设置（config.example.json）

| 配置项 | 默认值 | 含义 |
|---|---|---|
| `provider` | `"auto"` | `auto` 智能切换 / `qweather` 只用和风 / `openmeteo` 只用 Open-Meteo |
| `lookahead_minutes` | `60` | 提前多久提醒（"未来 1 小时"） |
| `precip_threshold_mmh` | `0.1` | 降水强度阈值 mm/h，超过才算"会下雨"（调大更保守） |
| `snow_temp_c` | `1.0` | 气温 ≤ 此值判定为雪/雨夹雪 |
| `dedupe_minutes` | `90` | 同一城市两次提醒的最小间隔 |
| `cities` | 长春、阳泉 | 增删城市：填 `name` 和 `lat`/`lon`（可用高德/百度地图查坐标） |

## 费用与限额说明

- **GitHub Actions**：公开仓库免费、定时任务无限次；若用私有仓库，免费 2000 分钟/月（每 15 分钟≈2880 分钟会超，可把工作流里的 cron 改成 `*/30`，或仓库公开）
- **PushPlus**：免费额度约 200 条/天，我们只在"预报有雨"且去重窗口过后才发，实际消耗很少
- **和风天气**：免费 1000 次/天，本方案 192 次/天；Open-Meteo 免费无 key，兜底不花钱

## 常见问题

**Q：收不到消息？**
先到 Actions 页面看最近一次运行是否绿色成功。再检查：① 是否关注了 pushplus 公众号；② Secrets 名字是否完全一致（`PUSHPLUS_TOKEN`）；③ 用 `mode: test` 手动跑一次看日志。

**Q：GitHub 定时不精准？**
GitHub 的 cron 是"尽力而为"，高峰期可能延迟几分钟，属正常现象。想更准时可改本地/云函数方案。

**Q：私有仓库 60 天没活动定时会停？**
是的，GitHub 会暂停私有仓库的定时任务；公开仓库不受影响，或偶尔提交一次代码即可恢复。

**Q：和风天气一直报错（404/401）？**
新版和风控制台的 key 与 API Host 是绑定的，请把控制台里项目的 API Host 填到 `qweather_base`（如 `https://xxx.re.qweatherapi.com`），并把 key 填到 `qweather_key`。程序同时兼容新版 `X-QW-Api-Key` 请求头和旧版 `key` 参数；如果 key 没有分钟级降水权限，会自动切到 Open-Meteo（日志会提示），不影响使用。

**Q：想先验证一下判断逻辑？**
本机装有 Python 3.9+ 时运行 `python test_logic.py`，会离线跑 15 项自检（无降水/下雨/下雪/强度分级/去重/消息格式），全部通过会打印「全部通过 ✅」。

---

## 后续计划：手机实时定位版（GPS）

当前版本按固定城市（长春、阳泉）工作。要变成"跟着手机定位走"，思路是：

1. 手机上用 iOS 快捷指令 / 安卓 Tasker，每隔 N 分钟把 GPS 坐标 POST 到一个接收端
2. 接收端（如家里 NAS 上的小服务，或腾讯云函数）把最新坐标写进一个公开可读的地址
3. 本程序把 `cities` 从固定列表改成读取那个地址的实时坐标

如果你之后想要这个功能，告诉我你用的是 iPhone 还是安卓、有没有可常开的接收端，我再帮你把这一层加上。
