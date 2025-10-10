# 🤖 Bot Admin – Telegram 机器人可视化控制台 · Visual Management Console

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="python" />
  <img src="https://img.shields.io/badge/Flask-3.x-black.svg" alt="flask" />
  <img src="https://img.shields.io/badge/Realtime-Socket.IO-ff9800.svg" alt="socketio" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="license" />
</p>

<p align="center">
  <a href="#-中文版">简体中文</a> · <a href="#-english">English</a>
</p>

---

## 🇨🇳 中文版 {#中文版}

### 🌟 项目简介
Bot Admin 是一款为 Telegram 机器人量身打造的 Web 管理后台，让你无需编写繁琐脚本，即可完成 **创建 / 配置 / 部署 / 运营 / 监控** 的全流程。全新的实时架构和模块化目录结构，让多人协作、团队托管、自动化扩展都变得轻而易举。

> **零代码 & 专业级并行**：支持固定命令、可视化流程（Blockly）、专业 Python 沙盒、中文伪代码和 AI 自动生成——同一个平台满足从运营到工程的不同角色。

### ✨ 功能亮点
| 功能 | 说明 |
| --- | --- |
| 多用户与多机器人 | 支持注册登录，Bot 数据隔离管理，可同时维护多个 Telegram Bot。
| 实时状态看板 | 前端通过 Socket.IO 收取推送，机器人卡片、运行监控、统计面板秒级更新。
| 指令管理矩阵 | 固定指令 / Blockly 流程 / 专业 Python 脚本 / 中文伪代码互相补充，满足不同复杂度需求。
| AI 智能辅助 | 可接入 DeepSeek（或任意 OpenAI 兼容接口）自动生成命令模板、伪代码；离线模式下提供兜底模板。
| 沙盒调试与日志 | 提供伪代码沙盒执行、实时日志流、错误高亮，方便定位问题。
| 结构化目录 | `config/`、`core/`、`data/`、`interact/` 等分层，便于快速理解、二次开发与测试。

### 🧱 目录结构
```text
BotAdmin/
├─ config/            # 全局配置（路径、密钥、静态目录）
├─ data/              # 数据访问层（SQLite 读写、DAO 方法）
├─ core/              # 业务核心（AI、伪代码、流程引擎、运行时）
├─ interact/          # Web 接口层（Flask + Socket.IO 蓝图）
├─ static/            # 前端单页应用（Tailwind + Socket.IO 客户端）
├─ requirements.txt   # 依赖清单
├─ main.py            # 开发入口（socketio.run）
└─ README.md
```

### ⚙️ 运行前准备
1. **环境需求**：Python 3.10+，SQLite（内置），Node 无需安装。
2. **安装依赖**：
   ```bash
   git clone https://github.com/sniperrich/BotAdmin.git
   cd BotAdmin
   python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **环境变量（可选）**：
   ```bash
   export APP_SECRET="your_random_secret"        # Session 加密
   export DEEPSEEK_API_KEY="sk-xxxx"            # 可选，启用 AI 自动生成
   export DEEPSEEK_BASE_URL="https://api.deepseek.com"  # 可选，兼容其他 OpenAI 接口
   ```
4. **启动服务**：
   ```bash
   python main.py
   ```
   默认监听 `http://127.0.0.1:8000`，浏览器访问即可。

### 🚀 快速上手
1. **注册登录**：首次访问创建账户后登录。
2. **创建 Bot**：在 Telegram `@BotFather` 获取 Token，填写于“我的 Bots”面板，一键添加。
3. **配置行为**：在控制中心依次切换“固定指令 / 流程编排 / 中文伪代码 / 专业模式”标签进行配置。
4. **启动调试**：点击“启动/重载”让新配置生效，实时监控面板与日志将立即刷新。
5. **AI 协作**：在对应面板填写提示词，调用 DeepSeek（若已配置密钥）快速生成命令或伪代码。

### 🛠 常用命令
| 场景 | 命令 |
| --- | --- |
| 安装依赖 | `pip install -r requirements.txt` |
| 代码静态检查 | `python -m py_compile $(git ls-files '*.py')` |
| 启动后端 | `python main.py` |
| 导出数据库 | `sqlite3 bot_admin.db .dump > backup.sql` |

### 🔒 配置说明
| 变量 | 说明 |
| --- | --- |
| `APP_SECRET` | Flask Session 密钥（强烈建议自定义）。 |
| `BOT_ADMIN_DB` | 可自定义数据库路径，默认项目根目录下 `bot_admin.db`。 |
| `DEEPSEEK_API_KEY` / `AI_API_KEY` | 启用 AI 自动生成功能时需要。 |
| `DEEPSEEK_BASE_URL` / `AI_BASE_URL` | 若使用第三方 OpenAI 兼容服务可指定。 |

### 🧭 技术架构
- **后端**：Flask + Flask-SocketIO，REST API + WebSocket 实时推送。
- **业务层**：`core.runtime.BotRegistry` 提供多线程异步调度，支持自动重启/命令同步。
- **数据层**：`data.database` 中实现了所有 SQLite CRUD 方法，便于单元化测试。
- **AI 适配**：`core.ai` 统一封装 DeepSeek/OpenAI 客户端，自动降级到本地模板。
- **前端**：原生单页 + TailwindCSS，自带命令卡片、流程预览、伪代码沙盒、日志面板。

### 🧪 测试建议
- 针对 `core/` 和 `data/` 模块可使用 `pytest` 配合临时数据库进行单元测试。
- 使用 `python -m py_compile` 保证语法完整；前端可通过浏览器 DevTools 观察 WebSocket 数据。

### 📅 开发路线
- [ ] 支持 Docker 一键部署方案。
- [ ] Flow 编辑器增加导入导出与协作模板。
- [ ] Pro Script 沙盒提供更详细的资源配额与 API 白名单。
- [ ] 接入更多 AI 模型（如 gpt-4o / 文心等）。

### 🤝 贡献指南
1. Fork 仓库并创建分支：`git checkout -b feature/awesome`
2. 提交更改：`git commit -m "Add awesome feature"`
3. 推送并发起 Pull Request。

### 📄 开源协议
项目基于 [MIT License](LICENSE)。欢迎自由使用、修改与分发。

---

## 🇺🇸 English {#english}

### 🌟 Overview
Bot Admin is a web-based control center tailored for Telegram bots. It offers a full workflow—from bootstrapping a new bot, configuring commands, orchestrating complex flows, to monitoring production traffic. The latest version ships with a real-time Socket.IO layer and a clean, layered directory structure to support teamwork and large-scale automation.

> **Zero-code meets Pro-code**: fixed commands, visual flows (Blockly), Pro Python sandbox, Chinese pseudocode, and AI co-pilot are all available in the same workspace.

### ✨ Highlights
| Feature | Description |
| --- | --- |
| Multi-user & Multi-bot | User accounts with isolated data scopes; manage any number of Telegram bots side-by-side. |
| Realtime dashboard | Frontend consumes Socket.IO events—bot cards, runtime panels, and stats update instantly. |
| Rich authoring modes | Fixed command replies, Blockly flow orchestration, Python sandbox scripts, and Chinese pseudocode complement each other. |
| AI assistance | Plug in DeepSeek (or any OpenAI-compatible endpoint) to generate command templates or pseudocode in seconds; offline fallbacks included. |
| Sandbox & logs | Built-in pseudocode sandbox, live log stream, and error tracing speed up debugging. |
| Layered architecture | `config/`, `core/`, `data/`, `interact/`, `static/` keep business logic, persistence, and presentation neatly separated. |

### 🧱 Project Layout
```
BotAdmin/
├─ config/            # Global settings helper
├─ data/              # SQLite helpers / data access methods
├─ core/              # Domain logic (AI adapters, pseudocode, flow engine, runtime)
├─ interact/          # Flask app factory, REST routes, Socket.IO bindings
├─ static/            # SPA assets (TailwindCSS + Socket.IO client)
├─ requirements.txt   # Python dependencies
├─ main.py            # Dev entrypoint using socketio.run
└─ README.md
```

### ⚙️ Prerequisites
1. **Environment**: Python 3.10+, Git, SQLite (bundled).
2. **Install dependencies**:
   ```bash
   git clone https://github.com/sniperrich/BotAdmin.git
   cd BotAdmin
   python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Environment variables (optional)**:
   ```bash
   export APP_SECRET="your_random_secret"
   export DEEPSEEK_API_KEY="sk-xxxx"
   export DEEPSEEK_BASE_URL="https://api.deepseek.com"
   ```
4. **Run the app**:
   ```bash
   python main.py
   ```
   Browse to `http://127.0.0.1:8000`.

### 🚀 Workflow
1. **Sign up / Sign in** to obtain a personal workspace.
2. **Add bots** using tokens issued by Telegram `@BotFather`.
3. **Configure behaviour** via the Control Center tabs (Fixed commands, Flows, Pseudocode, Pro mode).
4. **Hit “Start/Reload”** to apply changes; the WebSocket dashboard and log panel will refresh immediately.
5. **Leverage AI** prompts to co-create command templates or pseudocode when DeepSeek/API keys are configured.

### 🛠 Handy Commands
| Use case | Command |
| --- | --- |
| Install dependencies | `pip install -r requirements.txt` |
| Syntax sanity check | `python -m py_compile $(git ls-files '*.py')` |
| Launch backend | `python main.py` |
| DB export | `sqlite3 bot_admin.db .dump > backup.sql` |

### 🔧 Configuration
| Variable | Purpose |
| --- | --- |
| `APP_SECRET` | Flask session secret (generate your own). |
| `BOT_ADMIN_DB` | Optional path override for the SQLite file. |
| `DEEPSEEK_API_KEY` / `AI_API_KEY` | Enable AI-assisted generation. |
| `DEEPSEEK_BASE_URL` / `AI_BASE_URL` | Point to any OpenAI-compatible endpoint. |

### 🧭 Architecture Notes
- **Backend**: Flask + Flask-SocketIO; REST for CRUD, WebSocket for live updates.
- **Runtime**: `core.runtime.BotRegistry` orchestrates threaded Telegram bot workers with auto-restart and menu sync.
- **Persistence**: `data.database` centralizes SQLite access—perfect for unit testing and future ORM migration.
- **AI bridge**: `core.ai` wraps DeepSeek/OpenAI clients with graceful fallback templates.
- **Frontend**: single-page app using TailwindCSS, Socket.IO, and vanilla JS components for cards, editors, and logs.

### 🧪 Testing Tips
- Use `pytest` with temporary SQLite files to cover `core/` and `data/` logic.
- `python -m py_compile` keeps syntax clean; check browser DevTools Network + Console for WebSocket streams.

### 🗺 Roadmap
- [ ] Dockerized deployment stack (Dockerfile + docker-compose).
- [ ] Flow editor import/export & collaborative templates.
- [ ] Enhanced Pro-script sandbox with quota and API allowlists.
- [ ] Additional AI providers (e.g., GPT-4o, Wenxin, Claude).

### 🤝 Contributing
1. Fork the repo & create a branch: `git checkout -b feature/awesome`
2. Commit your changes: `git commit -m "Add awesome feature"`
3. Push & open a pull request.

### 📄 License
Released under the [MIT License](LICENSE). Enjoy building automation for your Telegram bots!

---

<p align="center">Made with ❤️ for builders who love automating Telegram bots.</p>
