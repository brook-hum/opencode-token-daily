# Contributing

感谢参与改进 OpenCode Token Daily。

## 开发环境

只需要 Python 3（仅使用标准库，无需安装第三方依赖）：

```bash
git clone https://github.com/brook-hum/opencode-token-daily.git
cd opencode-token-daily
python server.py
```

打开 `http://127.0.0.1:8765` 即可。Windows 用户可以直接双击 `启动.bat`。

## 代码结构

- `server.py`：只读解析 OpenCode 本地 SQLite 数据库，计算统计，并提供本地 HTTP 接口
- `web/index.html`、`web/style.css`、`web/app.js`：前端界面

## 提交改动

1. Fork 本仓库并创建分支
2. 保持改动聚焦，必要时补充 README
3. 确认 `python -m py_compile server.py` 与 `node --check web/app.js` 通过
4. 提交 PR，并说明改动动机与验证方式

## 原则

- 所有计算必须留在本地，不得引入任何上报、遥测或云同步
- 不修改 OpenCode 自身的数据库，只用 `mode=ro` 只读打开
- 保持零第三方依赖，方便任何人直接运行
