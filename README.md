# 碧蓝航线Wiki多智能体查询系统
基于 AutoGen AgentChat 构建的全自动多智能体信息检索流水线。
输入自然语言查询，智能体团队自动完成需求解析、Wiki数据拉取、信息提炼、结果校验迭代，最终返回结构化的碧蓝航线图鉴信息。

## 系统架构
本项目采用 `SelectorGroupChat` 动态选择器多智能体架构，支持条件分支与多轮迭代重提炼。
> 流程：用户提问 → summarize_agent（需求解析） → search_agent（调用Wiki工具） → extract_agent（信息提炼） → user_proxy（结果审核）
> 分支逻辑：审核不通过，自动跳转回 extract_agent 重新提炼；审核通过输出 Terminated，任务结束。

### 智能体角色分工
1. **summarize_agent 需求总结智能体**
    接收用户自然语言问题，解析查询意图，生成Wiki工具调用参数。
2. **search_agent 搜索工具智能体**
    接收查询参数，调用外部工具 `get_blhx_wiki_data` 请求碧蓝海事局Wiki，获取原始结构化字典数据。
3. **extract_agent 信息提炼智能体**
    基于Wiki原始数据，提取用户关心字段，整理成简洁可读结果；审核不通过时可多次重新提炼。
4. **user_proxy 自动审核智能体**
    校验提炼结果是否满足用户需求。合格输出 `Terminated` 终止任务；不合格指令提炼智能体重新整理信息。

## 核心技术特性
1. 协作模式：SelectorGroupChat，自定义selector函数，支持动态跳转Agent，适配迭代重提炼场景。
2. 双层终止保护：
   - 语义终止条件：TextMentionTermination，检测`Terminated`正常结束；
   - 硬轮次上限：max_turns=3，防止智能体死循环，限制最大对话轮次。
3. Function Calling 外部工具集成：search_agent绑定Wiki爬虫工具，抓取并清洗Wiki页面标记文本。
4. 全自动流水线，无需人工介入（无Human-in-the-Loop）。
5. 事件流采集对话消息，自动提取最后一轮提炼结果作为输出。

## 环境依赖
Python >=3.13.15

## 运行方式
### 1. 获取项目源码
方式一：Git克隆
```bash
git clone https://github.com/luohuacishu/azurelane_search_agent.git
cd azurelane_search_agent

# 创建虚拟环境
python -m venv .venv
# 激活虚拟环境
.venv\Scripts\activate
# 安装全部依赖包
pip install -r requirements.txt

MODEL_NAME=你的模型名称
LLM_BASE_URL=https://xxx/v1
LLM_API_KEY=sk-xxxxxx

cd src
python azurelane_search_agent.py
