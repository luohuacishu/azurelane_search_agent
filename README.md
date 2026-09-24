# 碧蓝航线 Wiki 多智能体查询系统

基于 AutoGen AgentChat 构建的轻量级多智能体信息检索流水线。  
输入自然语言查询，智能体团队自动完成意图解析、Wiki 数据拉取、信息提炼，返回结构化的碧蓝航线图鉴信息。  
同时提供 QQ 群机器人接入能力，支持在 QQ 群内 @ 机器人直接查询。

## 系统架构

本项目采用 `SelectorGroupChat` 动态选择器多智能体架构，经过优化后简化为两个智能体：

> 流程：用户提问 → query_agent（意图解析 + 调用工具） → format_agent（信息提炼 + 输出终止）

- **query_agent**：分析用户想查什么，调用 `get_blhx_wiki_data` 工具获取原始数据。
- **format_agent**：把原始数据整理成用户可读的简洁格式，输出 `Terminated` 结束任务。

### 优化亮点

相比早期 4 智能体版本（summarize / search / extract / user_proxy），当前版本做了以下优化：

1. **合并智能体**：summarize + search 合并为 `query_agent`，extract + user_proxy 合并为 `format_agent`，LLM 调用次数从 4 次降到 2 次。
2. **复用模型客户端**：`model_client` 单例模式，避免每次请求重复创建。
3. **规则校验代替 LLM 审核**：`is_answer_valid()` 函数替代 user_proxy 的 LLM 判断，省一次调用。
4. **并发限流**：使用 `asyncio.Semaphore(3)` 限制同时处理的请求数，避免打爆 API。
5. **修复 selector 跳转 bug**：原 `"ent"` 跳转目标修正为 `"format_agent"`。

## 核心技术特性

1. **协作模式**：`SelectorGroupChat` + 自定义 selector 函数，支持动态跳转 Agent。
2. **双层终止保护**：
   - 语义终止：`TextMentionTermination` 检测 `Terminated` 正常结束；
   - 硬轮次上限：`max_turns=2` 防止死循环。
3. **Function Calling 外部工具集成**：`query_agent` 绑定 Wiki 爬虫工具，抓取并清洗 Wiki 页面标记文本。
4. **全自动流水线**：无需人工介入（无 Human-in-the-Loop）。
5. **事件流采集**：自动提取最后一轮 `format_agent` 输出作为最终结果。

## 目录结构
-pro3/

-├── src/

-│ ├── azurelane_search_agent.py # 多智能体核心逻辑 + run_agent_for_qq 包装函数

-│ ├── reply.py # QQ 机器人入口（botpy）

-│ ├── executor.py # 工具执行器

-│ ├── search.py # Wiki 搜索工具

-│ ├── config.yaml # QQ 机器人 AppID / Secret

-├── .env # 大模型配置

-├── requirements.txt

-└── README.md


## 环境依赖

- Python >= 3.11（推荐 3.13）
- AutoGen AgentChat
- botpy（用于 QQ 机器人接入）
- 依赖清单见 `requirements.txt`

## 运行方式

### 1. 获取项目源码

```bash
git clone https://github.com/luohuacishu/azurelane_search_agent.git
cd azurelane_search_agent

## 2. 创建并激活虚拟环境
Windows (PowerShell/CMD):
python -m venv .venv
.venv\Scripts\activate

macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate

## 3. 安装依赖包
pip install -r requirements.txt

## 4. 配置环境变量
在项目根目录下创建一个名为 .env 的文件，填入大模型配置：
MODEL_NAME=你的模型名称
LLM_BASE_URL=https://xxx/v1
LLM_API_KEY=sk-xxxxxx

## 5. 运行方式
### 方式一：直接运行多智能体查询（命令行测试）
cd src
python azurelane_search_agent.py

### 方式二：启动 QQ 群机器人
cd src
python demo_reply.py

```

## 运行示例
用户提问： 信浓的保底次数是多少？

终端输出：

开始运行搜索智能体团队
模型客户端就绪

---------- format_agent 输出 ----------
信浓保底次数：[蝶海梦花活动池累计建造200次后可兑换获取；复刻蝶海梦花累计建造200次后可兑换获取；共可累计4次；也可通过常驻UR兑换获取]
--------------------------------------

协作开发结果: 信浓保底次数：
蝶海梦花活动池累计建造 200次 后可兑换获取；
复刻蝶海梦花累计建造 200次 后可兑换获取；
共可累计 4次；
也可通过常驻 UR 兑换获取。