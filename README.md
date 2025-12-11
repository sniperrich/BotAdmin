# 🤖 Bot Admin – High-Performance Async Telegram Bot Management System
# 🤖 Bot Admin – 高性能异步 Telegram 机器人管理系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="python" />
  <img src="https://img.shields.io/badge/AsyncIO-Powered-brightgreen.svg" alt="asyncio" />
  <img src="https://img.shields.io/badge/Flask-3.x%20Async-black.svg" alt="flask" />
  <img src="https://img.shields.io/badge/Realtime-Socket.IO-ff9800.svg" alt="socketio" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="license" />
</p>

<p align="center">
  <a href="#-中文版">简体中文</a> · <a href="#-english">English</a>
</p>

---

## 🇨🇳 中文版 {#中文版}

### 🌟 项目简介 (Introduction)
Bot Admin 是一个现代化的、完全异步架构的 Telegram 机器人管理平台。它旨在通过**可视化界面**解决机器人的**创建、配置、逻辑编排与监控**问题。
经过最新的**全异步重构**，系统在处理高并发数据库操作和 I/O 密集型任务时性能显著提升。配合实时的 WebSocket 推送和安全沙盒，它不仅适合个人开发者托管多个机器人，也适合团队进行复杂的自动化流程编排。

> **核心进化**：从传统的同步阻塞架构全面升级为 `Async/Await` + `aiosqlite` 异步架构，Web 响应速度与并发能力大幅跃升。

### ✨ 核心特性 (Features)
| 模块 | 说明 |
| --- | --- |
| **⚡️ 全异步核心** | 基于 Python 异步生态（AsyncIO, aiosqlite）重写，路由与数据库全链路非阻塞。 |
| **🔐 安全沙盒** | 内置 AST 静态分析与受限执行环境，确保 Pro Script 脚本安全运行（支持 stdout 重定向）。 |
| **🧩 可视化流程** | 新一代 FlowVM 引擎，支持变量预取、异步渲染、键盘交互，逻辑编排更灵活。 |
| **📡 实时看板** | Socket.IO 实时推送机器人状态、运行日志与统计数据，告别手动刷新。 |
| **🤖 AI 驱动** | 集成 AI 接口（如 DeepSeek），一键生成 Python 伪代码、指令逻辑或流程图。 |
| **📦 模块化设计** | 清晰的 `core` (内核), `data` (数据), `interact` (交互) 分层架构，易于维护。 |

### 🧱 目录结构 (Structure)
```text
BotAdmin/
├─ config/            # 配置中心（环境加载、路径管理）
├─ core/              # 核心引擎
│  ├─ runtime.py      # 异步运行时与机器人注册表
│  ├─ flows.py        # FlowVM 流程引擎（含变量渲染与逻辑执行）
│  ├─ sandbox.py      # 安全沙盒执行环境
│  └─ ai.py           # AI 接口适配器
├─ data/              # 异步数据层 (aiosqlite DAO)
├─ interact/          # 交互层
│  ├─ routes/         # 纯异步 Flask 路由蓝图
│  └─ socket.py       # WebSocket 实时推送逻辑
├─ static/            # 前端资源 (SPA + TailwindCSS)
├─ main.py            # 启动入口
└─ requirements.txt   # 依赖清单
```

### ⚙️ 快速开始 (Quick Start)

#### 1. 环境准备
确保 Python 3.10+ 环境。

#### 2. 安装依赖
由于系统使用了异步 Flask 特性，请务必安装 `flask[async]` 或确保包含 `asgiref`。
```bash
git clone https://github.com/sniperrich/BotAdmin.git
cd BotAdmin
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install "flask[async]" # 确保异步支持
```

#### 3. 环境变量 (可选)
复制 `.env.example` (如有) 或直接设置：
```bash
export APP_SECRET="your_secret_key"
export DEEPSEEK_API_KEY="sk-xxxx" # AI 功能需要
```

#### 4. 启动服务
```bash
python main.py
```
服务默认运行在 `http://0.0.0.0:8780` (端口可在 main.py 修改)。

### 🛠 使用指南
1. **添加机器人**：在 BotFather 申请 Token，在后台添加。
2. **编写逻辑**：
   - **固定指令**：简单的文本/图片回复。
   - **Pro Scripts**：Python 脚本（运行在安全沙盒中）。
   - **Flows**：复杂对话流，支持跳转、变量存储。
3. **监控**：在 Dashboard 查看实时日志流。

---

## 🇺🇸 English {#english}

### 🌟 Introduction
Bot Admin is a state-of-the-art, **fully asynchronous** management console for Telegram Bots. It streamlines the lifecycle of bot development: **creation, configuration, orchestration, and monitoring**.
With the latest **async refactor**, Bot Admin now leverages `aiosqlite` and `async/await` throughout its core, delivering superior performance for high-concurrency scenarios. Combined with real-time WebSockets and a secure execution sandbox, it's the ultimate tool for both hobbyists and engineering teams.

> **Evolution**: Upgraded from synchronous blocking I/O to a modern `AsyncIO` architecture, significantly reducing latency and increasing throughput.

### ✨ Key Features
| Module | Description |
| --- | --- |
| **⚡️ Async Core** | Rewritten with Python's AsyncIO and `aiosqlite` for non-blocking database and I/O operations. |
| **🔐 Secure Sandbox** | AST-based static analysis and restricted execution environment for "Pro Scripts". |
| **🧩 FlowVM V2** | Enhanced Flow engine supporting async variable pre-fetching, rendering, and complex interactions. |
| **📡 Realtime Dashboard** | Live status updates, logs, and statistics pushed via Socket.IO. |
| **🤖 AI Copilot** | Integrated AI handlers (e.g., DeepSeek) to generate pseudocode, commands, and logic automatically. |
| **📦 Modular Arch** | Clean separation of concerns: `core` (kernel), `data` (persistence), `interact` (API/WS). |

### 🧱 Project Structure
```text
BotAdmin/
├─ config/            # Configuration & Path Management
├─ core/              # Kernel Modules
│  ├─ runtime.py      # Async Runtime & Bot Registry
│  ├─ flows.py        # FlowVM Engine (Rendering & Execution)
│  ├─ sandbox.py      # Security Sandbox
│  └─ ai.py           # AI Adapters
├─ data/              # Data Access Layer (aiosqlite)
├─ interact/          # Interface Layer
│  ├─ routes/         # Async Flask Blueprints
│  └─ socket.py       # WebSocket Bridge
├─ static/            # Frontend Assets
├─ main.py            # Entry Point
└─ requirements.txt   # Dependencies
```

### ⚙️ Getting Started

#### 1. Prerequisites
Python 3.10+ is required.

#### 2. Installation
Ensure to install Flask with async extras.
```bash
git clone https://github.com/sniperrich/BotAdmin.git
cd BotAdmin
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install "flask[async]" # Crucial for async routes
```

#### 3. Configuration (Optional)
Set environment variables:
```bash
export APP_SECRET="your_secure_secret"
export DEEPSEEK_API_KEY="sk-xxxx" # For AI features
```

#### 4. Run
```bash
python main.py
```
Access the console at `http://0.0.0.0:8780` (or configured port).

### 🛠 Usage
1. **Register Bots**: Add your bot tokens from BotFather.
2. **Define Logic**:
   - **Commands**: Simple auto-replies.
   - **Pro Scripts**: Python code running in a secure, sandboxed environment.
   - **Flows**: Visual conversation flows with state management.
3. **Monitor**: Watch real-time logs and status on the dashboard.

---

<p align="center">Made with ❤️ for the Telegram Bot Community.</p>
