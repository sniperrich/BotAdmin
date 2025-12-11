# Bot Admin

<div align="center">

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Async Framework](https://img.shields.io/badge/Async-Powered-green.svg)](https://docs.python.org/3/library/asyncio.html)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot%20API-FEC400.svg)](https://core.telegram.org/bots/api)

**The High-Performance Control Plane for Telegram Automations**  
**专为 Telegram 机器人打造的高性能异步管理控制台**

[English](#-english) | [简体中文](#-简体中文)

</div>

---

## 🚀 English

### What is Bot Admin?

Bot Admin is a self-hosted platform designed to manage, orchestrate, and monitor multiple Telegram bots from a single interface. Built on a fully **asynchronous architecture** (Python AsyncIO + aiosqlite), it handles high-concurrency workloads with ease while providing a seamless real-time experience.

Whether you are running a simple auto-reply bot or a complex mesh of AI-driven agents, Bot Admin provides the primitives you need: **Flows**, **Pro Scripts**, and **AI Copilots**.

### Key Features

- **⚡️ Native Async Core**: Built from the ground up with `async/await`. I/O operations (database, network) are non-blocking, ensuring your bots remain responsive even under load.
- **🧠 AI-Assisted Logic**: Integrated with LLMs (e.g., DeepSeek). Describe your bot's behavior in natural language, and let the AI generate the code or flow for you.
- **🛡️ Sandboxed Execution**: Run custom Python scripts safely. Our AST-based sandbox prevents malicious operations while allowing powerful logic execution.
- **loop FlowVM Engine**: A visual flow engine that supports complex conversations, variable state management, and conditional branching—no coding required.
- **📡 Real-Time Telemetry**: Watch your bots in action. Logs, status changes, and user interactions are pushed instantly to your dashboard via WebSockets.

### Installation

**1. Clone & Prep**
```bash
git clone https://github.com/sniperrich/BotAdmin.git
cd BotAdmin
python -m venv .venv
source .venv/bin/activate
```

**2. Install Deps**
> **Note**: System requires async extras for Flask.
```bash
pip install -r requirements.txt
pip install "flask[async]"
```

**3. Launch**
```bash
python main.py
```
Visit `http://localhost:8780` and start automating.

### Environment Configuration

Configure your instance via environment variables or a `.env` file.

```bash
# Security
APP_SECRET="change_this_to_something_random"

# AI Capabilities (Optional)
DEEPSEEK_API_KEY="sk-your-key-here"
```

### Development

This project uses a modular design:
- `core/`: The async brain (Runtime, VM, Sandbox).
- `interact/`: The interface layer (Async Flask Routes, Socket.IO).
- `data/`: The storage layer (aiosqlite).

To extend functionality, check `interact/routes` for API endpoints or `core/flows.py` for VM logic.

---

## 🇨🇳 简体中文

### 简介

Bot Admin 是一个现代化的 Telegram 机器人私有化管理平台。它不仅仅是一个简单的配置面板，更是一个**全异步的高性能自动化引擎**。

通过 Bot Admin，你可以统一管理多个机器人实例，并使用多种方式定义机器人的行为：从简单的关键词回复，到可视化的流程图编排，再到专业级的 Python 脚本控制。配合内置的 AI 辅助功能，让机器人开发从未如此简单。

### 核心能力

*   **⚡️ 全链路异步化**
    摒弃传统的同步阻塞模型，采用 `AsyncIO` + `aiosqlite` + `Async Flask` 构建。数据库读写与网络请求完全非阻塞，单节点即可支撑高并发场景。

*   **🛡️ 安全沙盒脚本 (Pro Scripts)**
    允许在平台内直接编写 Python 代码来控制机器人。内置基于 AST 的静态分析沙盒，在提供灵活性的同时确保宿主机的安全。

*   **🧩 可视化流程引擎 (FlowVM)**
    全新设计的流程虚拟机。支持变量预取、状态保持、条件判断与循环。无需写代码，通过拖拽即可实现复杂的对话逻辑。

*   **🤖 AI 智能副驾驶**
    深度集成 LLM（如 DeepSeek）。在此输入：“写一个能查天气的机器人”，AI 将自动为你生成相应的伪代码或流程配置。

*   **📡 毫秒级实时监控**
    基于 WebSocket 的实时遥测系统。机器人的每一条日志、每一次状态变更都会实时推送到你的浏览器，无需手动刷新。

### 快速开始

**1. 获取代码**
```bash
git clone https://github.com/sniperrich/BotAdmin.git
cd BotAdmin
```

**2. 安装依赖**
即使你使用 Windows，也推荐在虚拟环境中运行。
```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 安装核心依赖
pip install -r requirements.txt
# 确保安装异步 Flask 支持
pip install "flask[async]"
```

**3. 运行**
```bash
python main.py
```
服务启动后，打开浏览器访问 `http://127.0.0.1:8780`。

### 配置说明

建议在生产环境中通过环境变量配置密钥：

*   `APP_SECRET`: Session 加密密钥（生产环境请务必修改）。
*   `DEEPSEEK_API_KEY`: 配置后可开启 AI 辅助生成功能。

### 目录指引

*   `core/`: 核心逻辑层。包含异步运行时 (`runtime.py`)、流程虚拟机 (`flows.py`) 和沙盒 (`sandbox.py`)。
*   `interact/`: 接口交互层。包含所有异步 API 路由 (`routes/`) 和 WebSocket 处理逻辑 (`socket.py`)。
*   `data/`: 数据持久层。封装了所有基于 `aiosqlite` 的异步数据库操作。

---

<div align="center">
    Built with ❤️ by Developers for Developers.
</div>
