🤖 Bot Admin - 可视化 Telegram 机器人管理后台
![alt text](https://img.shields.io/badge/Language-Python-blue.svg)

![alt text](https://img.shields.io/badge/Framework-Flask-black.svg)

![alt text](https://img.shields.io/badge/License-MIT-green.svg)

![alt text](https://img.shields.io/github/stars/sniperrich/BotAdmin?style=social)
English | 简体中文
Bot Admin 是一个功能强大、对用户友好的 Web 管理面板，专为 Telegram 机器人设计。它让用户能够通过一个直观的网页界面，轻松地创建、管理和部署多个机器人，而无需深入复杂的后端代码。
本项目的核心理念是提供一个从 零代码 到 专业代码 的全链路解决方案，无论您是产品经理、运营人员还是专业开发者，都能找到最高效的工作流。
![alt text](https://raw.githubusercontent.com/sniperrich/BotAdmin/main/screenshot.png)
✨ 核心功能
👤 多用户 & 认证: 支持多用户注册和登录，每个用户的数据都安全隔离，只能管理自己创建的机器人。
🧩 多机器人管理:
在一个界面中添加、配置和删除多个 Telegram Bot。
一键启动、停止、重载机器人后台进程。
🎨 多维度指令定义方式:
固定指令: 快速创建简单的“命令-回复”式交互，支持文本、图片、文档等多种消息类型，适合新手快速上手。
流程编排 (Blockly): 通过拖拽积木块来设计复杂的多步骤对话流、API交互和条件逻辑，实现零代码构建强大功能。
专业模式 (Python): 为高级用户提供一个安全的沙箱环境，可以直接编写 Python 代码来处理机器人逻辑，拥有最高的自由度和灵活性。
中文伪代码: 使用自然语言描述机器人行为，一键将其转换为可视化的 Blockly 流程图，极大降低了复杂流程的设计门槛。
🚀 AI 辅助创作:
可选集成 DeepSeek AI（或其他兼容 OpenAI 的模型），只需一句话描述需求，即可自动生成指令模板和中文伪代码。
在未配置 API Key 的情况下，提供智能离线模板作为备用，不影响核心功能。
📊 实时监控与日志:
仪表盘通过 WebSocket 实时推送所有机器人的运行状态、在线时长、消息和错误计数，告别延迟。
独立的监控面板，可查看选中机器人的详细状态和实时日志流，日志由后端即时推送，无需手动刷新。
🚀 快速开始
1. 环境准备
Python 3.8 或更高版本。
Git
2. 克隆与安装
code
Bash
# 克隆仓库
git clone https://github.com/sniperrich/BotAdmin.git
cd BotAdmin

# 推荐在虚拟环境中操作
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
3. 配置环境变量
在项目根目录下创建一个名为 .env 的文件，并填入以下内容。
code
Env
# [必填] Flask 应用的加密密钥，用于保护 session。请替换为一串随机字符。
# 可以使用 python -c 'import secrets; print(secrets.token_hex(16))' 生成
APP_SECRET="your_strong_random_secret_string"

# [可选] AI 功能配置
# 如果您想使用 AI 辅助生成功能，请提供您的 DeepSeek API Key
# 也可使用任何兼容 OpenAI 接口的 Key
DEEPSEEK_API_KEY="your_deepseek_api_key"

# [可选] 如果您使用第三方兼容 OpenAI 的服务，请指定其 Base URL
# DEEPSEEK_BASE_URL="https://api.deepseek.com"
4. 初始化与运行
项目首次运行时会自动创建 bot_admin.db 数据库文件。
code
Bash
python main.py
服务将启动在 http://127.0.0.1:8000。现在，您可以在浏览器中访问它。
📖 使用指南
注册与登录: 首次使用请先注册一个管理员账户，然后登录。
添加机器人:
从 Telegram 的官方 @BotFather 获取您的机器人 Token。
在“我的 Bots”板块，填入机器人名称和 Token，点击“添加”。
选择与配置:
点击新创建的机器人卡片，下方将展开“Bot 控制中心”。
在 固定指令、流程编排、专业模式 或 中文伪代码 标签页中定义机器人的行为。
启动机器人: 在卡片上或控制中心点击 “启动/重载” 按钮。
测试: 前往 Telegram，与您的机器人对话，测试您配置的各项功能。
⚠️ 重要提示: 每当您修改了任何指令、流程或脚本后，都需要点击 “启动/重载” 按钮来应用更改，使之在运行中的机器人上生效。
🔮 未来路线图

计划任务 (Job Queue): 在“专业模式”中增加定时触发器，实现每日推送、定时提醒等功能。

高级代码编辑器: 为“专业模式”引入 Monaco Editor 或 CodeMirror，提供语法高亮和代码补全。

一键部署: 提供 Dockerfile 和 docker-compose.yml，简化部署流程。
❤️ 贡献
欢迎任何形式的贡献！如果您有好的想法或发现了 Bug，请随时提交 Pull Request 或创建 Issue。
Fork 本仓库
创建您的特性分支 (git checkout -b feature/AmazingFeature)
提交您的更改 (git commit -m 'Add some AmazingFeature')
推送到分支 (git push origin feature/AmazingFeature)
创建一个 Pull Request
📄 许可证
本项目基于 MIT 许可证。详情请见 LICENSE 文件。
<br>
🤖 Bot Admin - A Visual Management Panel for Telegram Bots
![alt text](https://img.shields.io/badge/Language-Python-blue.svg)

![alt text](https://img.shields.io/badge/Framework-Flask-black.svg)

![alt text](https://img.shields.io/badge/License-MIT-green.svg)

![alt text](https://img.shields.io/github/stars/sniperrich/BotAdmin?style=social)
Bot Admin is a powerful, user-friendly web-based panel designed for Telegram bots. It allows users to effortlessly create, manage, and deploy multiple bots through an intuitive web interface, without needing to dive into complex backend code.
The core philosophy of this project is to provide a full-spectrum solution from zero-code to pro-code, ensuring that product managers, operations staff, and professional developers alike can find their most efficient workflow.
![alt text](https://raw.githubusercontent.com/sniperrich/BotAdmin/main/screenshot.png)
✨ Core Features
👤 Multi-User & Authentication: Supports user registration and login, with each user's data securely isolated to manage their own bots.
🧩 Multi-Bot Management:
Add, configure, and delete multiple Telegram bots from a single interface.
One-click start, stop, and reload bot processes.
🎨 Versatile Logic Definition:
Fixed Commands: Quickly create simple command-response interactions with support for text, photos, documents, and more. Perfect for beginners.
Flow Orchestration (Blockly): Design complex, multi-step conversational flows, API interactions, and conditional logic by dragging and dropping blocks. Build powerful features with zero code.
Pro Mode (Python): Provides a secure sandbox environment for advanced users to write Python code directly, offering maximum freedom and flexibility.
Pseudocode (Chinese): Describe bot behavior in natural language (Chinese), and with one click, convert it into a visual Blockly flow, significantly lowering the barrier to designing complex logic.
🚀 AI-Powered Generation:
Optional integration with DeepSeek AI (or any OpenAI-compatible model). Simply describe your needs in a sentence to automatically generate command templates and pseudocode.
Provides intelligent offline templates as a fallback if no API key is configured, ensuring core functionality is always available.
📊 Real-time Monitoring & Logging:
The dashboard displays live status, uptime, and message/error counts for all bots, pushed in real-time via WebSockets, eliminating delays.
A dedicated monitoring panel provides a detailed status view and a live log stream for the selected bot, with logs pushed instantly from the backend.
🚀 Getting Started
1. Prerequisites
Python 3.8 or higher.
Git
2. Clone & Install
code
Bash
# Clone the repository
git clone https://github.com/sniperrich/BotAdmin.git
cd BotAdmin

# It's recommended to use a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
3. Configure Environment Variables
Create a file named .env in the project root directory and add the following content.
code
Env
# [Required] A secret key for the Flask application to secure sessions. Replace with a random string.
# You can generate one with: python -c 'import secrets; print(secrets.token_hex(16))'
APP_SECRET="your_strong_random_secret_string"

# [Optional] Configuration for AI features
# If you want to use the AI-assisted generation, provide your DeepSeek API Key.
# Any OpenAI-compatible key will also work.
DEEPSEEK_API_KEY="your_deepseek_api_key"

# [Optional] If you are using a third-party OpenAI-compatible service, specify its Base URL.
# DEEPSEEK_BASE_URL="https://api.deepseek.com"
4. Initialize & Run
The bot_admin.db database file will be created automatically on the first run.
code
Bash
python main.py
The service will start on http://127.0.0.1:8000. You can now access it in your browser.
📖 Usage Guide
Register & Login: On your first visit, register an administrator account, then log in.
Add a Bot:
Obtain a bot Token from Telegram's official @BotFather.
In the "My Bots" section, fill in the bot's name and token, then click "Add".
Select & Configure:
Click on the newly created bot card to expand the "Bot Control Center" below.
Define your bot's behavior using the Fixed Commands, Flow Orchestration, Pro Mode, or Pseudocode tabs.
Start the Bot: Click the "Start/Reload" button on the card or in the control center.
Test: Go to Telegram and start a conversation with your bot to test the features you've configured.
⚠️ Important Note: Whenever you modify any command, flow, or script, you must click the "Start/Reload" button to apply the changes to the running bot.
🔮 Future Roadmap

Scheduled Tasks (Job Queue): Add a time-based trigger in "Pro Mode" to enable features like daily reports, reminders, etc.

Advanced Code Editor: Integrate Monaco Editor or CodeMirror for "Pro Mode" to provide syntax highlighting and autocompletion.

One-Click Deployment: Provide a Dockerfile and docker-compose.yml to simplify the deployment process.
❤️ Contributing
Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are greatly appreciated.
Fork the Project
Create your Feature Branch (git checkout -b feature/AmazingFeature)
Commit your Changes (git commit -m 'Add some AmazingFeature')
Push to the Branch (git push origin feature/AmazingFeature)
Open a Pull Request
📄 License
Distributed under the MIT License. See LICENSE for more information.
