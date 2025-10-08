# 🤖 Bot Admin - Telegram 机器人可视化管理后台

Bot Admin 是一个为 Telegram 机器人设计的、功能全面的 Web 管理面板。它允许用户通过一个直观的网页界面，轻松地创建、管理和部署多个机器人，无需编写复杂的后端代码。

本项目的核心特色在于提供了从**零代码**到**专业代码**的全方位机器人逻辑定义方式，无论您是产品经理、运营人员还是专业开发者，都能找到适合自己的工作流。

## ✨ 核心功能

*   **👤 用户与认证**: 支持多用户注册和登录，每个用户只能管理自己创建的机器人。
*   **🧩 多机器人管理**:
    *   在一个界面中添加、配置和删除多个 Telegram Bot。
    *   一键启动、停止、重载机器人进程。
    *   实时监控机器人运行状态、在线时长和消息统计。
*   **🎨 多样化的指令定义方式**:
    *   **固定指令**: 快速创建简单的“命令-回复”式交互，支持文本、图片、文档等多种消息类型。
    *   **流程编排 (Blockly)**: 通过拖拽积木来设计复杂的多步对话流、API交互和条件逻辑，实现零代码构建强大功能。
    *   **专业模式 (Python)**: 为高级用户提供一个安全的沙箱环境，可以直接编写 Python 代码来处理机器人逻辑，拥有最高自由度。
    *   **中文伪代码**: 使用自然语言描述机器人行为，一键将其转换为可视化的流程编排，并支持 AI 辅助生成。
*   **🚀 AI 辅助生成**:
    *   集成 DeepSeek AI（或其他兼容 OpenAI 的模型），只需一句话描述需求，即可自动生成指令模板和中文伪代码。
    *   在未配置 API Key 的情况下，提供离线模板作为备用方案。
*   **📊 运行监控**:
    *   查看每个机器人的实时运行状态、在线时长、收发消息数和错误数。
    *   实时查看后台日志，方便快速排错。

## 🛠️ 技术栈

*   **后端**: Python 3, Flask
*   **机器人框架**: `python-telegram-bot`
*   **前端**: 原生 HTML, JavaScript, Tailwind CSS (CDN)
*   **数据库**: SQLite
*   **可视化编程**: Google Blockly

## 🚀 快速开始

### 1. 环境准备

*   确保您已安装 Python 3.8 或更高版本。
*   拥有一个可以访问互联网的环境。

### 2. 克隆项目

```bash
git clone <your-repository-url>
cd <project-directory>
```

### 3. 安装依赖

项目的所有依赖项都已列在 `requirements.txt` 文件中。

```bash
# 建议在虚拟环境中操作
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

**requirements.txt 内容**:
```txt
# Web 框架
Flask

# Telegram Bot 核心库
python-telegram-bot

# AI 功能需要 (可选)
openai

# 流程引擎和Pro脚本中的 HTTP 请求需要
aiohttp
```

### 4. 配置环境变量

在项目根目录下创建一个名为 `.env` 的文件，并填入以下内容。

```env
# [必填] Flask 应用的加密密钥，用于保护 session。请替换为一串随机字符。
# 可以使用 python -c 'import secrets; print(secrets.token_hex(16))' 生成
APP_SECRET="your_strong_random_secret_string"

# [可选] AI 功能配置
# 如果您想使用 AI 辅助生成功能，请提供您的 DeepSeek API Key
# 也可使用任何兼容 OpenAI 接口的 Key
DEEPSEEK_API_KEY="your_deepseek_api_key"

# [可选] 如果您使用第三方兼容 OpenAI 的服务，请指定其 Base URL
# DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

### 5. 初始化与运行

项目首次运行时会自动创建 `bot_admin.db` 数据库文件。

```bash
python app.py
```

服务将启动在 `http://127.0.0.1:8000`。

### 6. 访问

打开浏览器，访问 **http://127.0.0.1:8000**。

## 📖 使用指南

1.  **注册与登录**: 首次使用请先注册一个管理员账户，然后登录。
2.  **添加机器人**:
    *   从 Telegram 的 `@BotFather` 获取您的机器人 `Token`。
    *   在“我的 Bots”板块，填入机器人名称和 Token，点击“添加”。
3.  **选择与配置**:
    *   点击新创建的机器人卡片，下方将展开“Bot 控制中心”。
    *   **固定指令**: 用于创建简单的问答，如 `/start` -> "欢迎使用！"。
    *   **流程编排**: 点击“积木编排”按钮，在新窗口中拖拽积木来设计复杂流程。**保存后，需要返回主页点击“启动/重载”才能生效。**
    *   **专业模式**: 编写 Python 代码，实现最灵活的功能。同样需要**保存并重载**。
    *   **中文伪代码**: 用中文描述流程，然后点击“生成流程”，它会自动为您创建一个 Blockly 流程。
4.  **启动机器人**: 在卡片上或控制中心点击“启动/重载”按钮。
5.  **测试**: 前往 Telegram，与您的机器人对话，测试您配置的各项功能。

> **重要提示**: 每当您修改了任何指令、流程或脚本后，都需要点击 **“启动/重载”** 按钮来应用更改。

## 📁 项目结构

```
.
├── static/
│   ├── index.html       # 主管理界面
│   └── blocks.html      # Blockly 流程编辑器
├── ai_client.py         # AI 模型接口客户端
├── app.py               # Flask Web 应用主文件 (API 路由)
├── bot_registry.py      # 机器人进程管理核心，负责启动、停止和监控
├── db.py                # 数据库初始化与所有数据读写操作
├── flow_engine.py       # Blockly 流程的执行引擎
├── pseudo_convert.py    # 中文伪代码解析与转换逻辑
├── requirements.txt     # 项目依赖
└── bot_admin.db         # SQLite 数据库文件 (首次运行后生成)
```

## 🔮 未来展望

*   [ ] **实时化改造**: 使用 WebSocket 替代前端轮询，实现真正的实时日志和状态更新。
*   [ ] **计划任务**: 在“专业模式”中增加定时触发器（Job Queue），实现每日推送、定时提醒等功能。
*   [ ] **高级代码编辑器**: 为“专业模式”引入 Monaco Editor 或 CodeMirror，提供语法高亮和代码补全。
*   [ ] **用户角色与权限**: 增加不同角色的用户，实现更精细的权限管理。
*   [ ] **一键部署**: 提供 Dockerfile 和 `docker-compose.yml`，简化部署流程。
