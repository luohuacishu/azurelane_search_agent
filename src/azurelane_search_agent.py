# -*- coding: utf-8 -*-
import asyncio
import os

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.messages import TextMessage
from executor import toolExecutor
from search import get_blhx_wiki_data
from dotenv import load_dotenv

load_dotenv()

# ========== 初始化工具执行器，注册工具 ==========
executor = toolExecutor()
executor.add_tool("get_blhx_wiki_data", "获取舰娘/鱼雷/装备图鉴数据", get_blhx_wiki_data)


# ========== 全局复用 model_client ==========
_model_client = None


def get_model_client():
    """单例模式，避免每次请求都重新创建客户端"""
    global _model_client
    if _model_client is None:
        _model_client = OpenAIChatCompletionClient(
            model=os.getenv("MODEL_NAME"),
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "structured_output": True,
                "family": "unknown",
            },
        )
    return _model_client


# ========== 并发限流：最多同时处理 3 个请求 ==========
_semaphore = asyncio.Semaphore(3)


# ========== Agent 定义 ==========
def create_query_agent(model_client):
    """
    合并 summarize + search 的职责：
    理解用户意图 → 调用工具获取数据
    """
    system_prompt = """
    你是一位专业的碧蓝航线信息查询助手。
    用户会问舰娘/装备/鱼雷/图鉴相关的问题。

    你的职责：
    1. 分析用户想查什么（舰娘名、装备名等）
    2. 调用工具 get_blhx_wiki_data，参数格式为 {"name": "xxx"}
    3. 把工具返回的原始数据原封不动地传给 format_agent

    完成后输出"请format_agent整理信息"
    """
    return AssistantAgent(
        name="query_agent",
        model_client=model_client,
        system_message=system_prompt,
        tools=[get_blhx_wiki_data],
    )


def create_format_agent(model_client):
    """
    负责把原始数据整理成用户可读的格式
    """
    system_prompt = """
    你是一位专业的碧蓝航线信息提炼助手，你能够根据搜索智能体获取到的完整图鉴字典，提炼出用户想要了解的信息
    当接收到搜索智能体获取到的信息时:
    1.根据用户想要了解到的信息和搜索智能体获取到的完整字典，提炼出用户关心的内容
    2.请简洁明了的输出提炼出的完整信息，

    输出格式简洁，例如：
    信浓稀有度：[海上传奇]
    信浓技能：[技能1: 描述1
    , 技能2: 描述2
    , 技能3: 描述3]

    整理完成后，输出"请用户代理开始执行测试"。
    """
    return AssistantAgent(
        name="format_agent",
        model_client=model_client,
        system_message=system_prompt,
    )


def create_user_proxy(model_client):
    """
    用户代理：审核提炼结果是否符合用户需求
    """
    return AssistantAgent(
        name="user_proxy",
        model_client=model_client,
        system_message="""
        用户代理，负责执行以下职责：
        1. 将用户提出的搜寻请求和 format_agent 输出的信息作判断，判断是否符合用户的需求
        当符合用户需求后请回复"Terminated"
        当不符合用户需求后请回复"请format_agent开始提炼信息"
        """
    )


# ========== Selector ==========
def custom_selector(messages):
    last_msg = messages[-1]
    if last_msg.source == "user":
        return "query_agent"

    content = last_msg.content

    if last_msg.source == "query_agent":
        return "format_agent"
    elif last_msg.source == "format_agent":
        return "user_proxy"
    elif "请format_agent开始提炼信息" in content:
        return "format_agent"
    return None


# ========== 团队运行：复用 team 实例 ==========
_team_cache = {}


def get_team():
    """复用 team 实例，避免每次请求都重新创建 agent"""
    global _team_cache
    if "team" not in _team_cache:
        model_client = get_model_client()

        query_agent = create_query_agent(model_client)
        format_agent = create_format_agent(model_client)
        user_proxy = create_user_proxy(model_client)

        agents = [query_agent, format_agent, user_proxy]

        termination_condition = TextMentionTermination(text="Terminated")

        _team_cache["team"] = SelectorGroupChat(
            participants=agents,
            model_client=model_client,
            termination_condition=termination_condition,
            selector_func=custom_selector,
            max_turns=4,  # query → format → user_proxy → (可能重提炼)
        )
    return _team_cache["team"]


async def run_search_blhx_wiki_data_team(user_query: str) -> str:
    print("开始运行搜索智能体团队")
    team = get_team()
    print("智能体团队就绪")

    all_messages = []
    async for event in team.run_stream(task=user_query):
        if isinstance(event, TextMessage):
            all_messages.append(event)
            if event.source == "format_agent":
                print("\n---------- format_agent 输出 ----------")
                print(event.content)
                print("----------------------------------------\n")

    final_answer = None
    for msg in reversed(all_messages):
        if msg.source == "format_agent":
            final_answer = msg.content
            break

    if final_answer is not None:
        final_answer = final_answer.replace("请用户代理开始执行测试", "").strip()
        return final_answer
    else:
        return "未获取提炼结果"


# ========== 给 QQ 机器人用的包装函数 ==========
async def run_agent_for_qq(user_query: str, timeout: int = 240) -> str:
    """
    带超时、异常兜底、并发限流的包装函数
    """
    async with _semaphore:
        try:
            result = await asyncio.wait_for(
                run_search_blhx_wiki_data_team(user_query),
                timeout=timeout,
            )
            return result if result else "抱歉，我没有查到相关信息。"
        except asyncio.TimeoutError:
            return "思考太久了，请稍后再试~"
        except Exception as e:
            print(f"[AutoGen 错误] {e}")
            return "抱歉，处理时出错了，请稍后再试。"


if __name__ == "__main__":
    user_query = "帮我查一下信浓的保底次数"
    result = asyncio.run(run_agent_for_qq(user_query))
    print("协作开发结果:", result)