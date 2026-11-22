# OpenCode Token Daily

> 一个完全本地的 [OpenCode](https://opencode.ai/) Token 用量统计面板。
> 统计、存储、展示全部在你的电脑上完成，不联网、不上云。

![version](https://img.shields.io/badge/version-v1.0.0--20261122-orange)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.x-green)
![data](https://img.shields.io/badge/data-100%25%20local-brightgreen)

## 截图

![OpenCode Token Daily 界面](docs/screenshot.jpg)

> 截图中的项目路径已打码。

## 功能

- **累计用量**：从第一次使用 OpenCode 到现在的总 Token
- **时间区间**：最近 24 小时 / 7 天 / 30 天 / 1 年
- **项目排行**：按项目统计 Token 消耗
- **贡献日历**：GitHub 风格格子，支持最近 30 天 / 最近 1 年；有消耗才点亮，按当日用量分 5 档颜色
- **用量趋势**：按日（30 天）或按周（1 年）汇总的柱状图
- **Token 构成**：输入 / 输出 / 推理 / 缓存读取 / 缓存写入的占比与实际费用
- **本地设置**：本地用户名（支持中文）与本地头像，只保存在本机

## 快速开始

**Windows**：双击 `启动.bat`，浏览器会自动打开 `http://127.0.0.1:8765`。

**macOS / Linux**：

```bash
chmod +x start.sh
./start.sh
```

或者手动运行（需要 Python 3，**零第三方依赖**）：

```bash
python server.py
```

服务只监听 `127.0.0.1`。按 `Ctrl+C` 或关闭窗口即可退出。

## 数据来源与统计口径

- 只读打开 OpenCode 的本地数据库 `~/.local/share/opencode/opencode.db`（`mode=ro`），不会修改 OpenCode 的数据
- 统计基于每条 AI 消息记录的 token 字段；日期按本机时区计算
- `Token 总数 = 输入 + 输出 + 推理 + 缓存读取 + 缓存写入`
- 费用直接取数据库中记录的 `cost` 值

## 隐私

- 没有服务端、没有账号、没有遥测，也不会向任何外部地址发送数据
- 用户名与头像保存在 `~/.opencode-token-daily/`
- HTTP 服务仅绑定本机回环地址

## 项目结构

```
.
├── server.py          # 本地后端：读取 SQLite、计算统计、提供 API
├── web/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── 启动.bat            # Windows 启动器
├── start.sh           # macOS / Linux 启动器
├── docs/screenshot.jpg # 界面截图（路径已打码）
├── LICENSE            # MIT
└── CONTRIBUTING.md
```

## 贡献

欢迎提交 Issue 和 PR，请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE) © 2026 OpenCode Token Daily contributors
