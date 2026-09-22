from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent,UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.messages import TextMessage
from executor import toolExecutor
from search import get_blhx_wiki_data
from dotenv import load_dotenv
import os
import asyncio
load_dotenv()
# ========== 初始化工具执行器，注册工具 ==========
executor = toolExecutor()
executor.add_tool("get_blhx_wiki_data", "获取舰娘/鱼雷/装备图鉴数据", get_blhx_wiki_data)
def create_openai_model_client():
    """
    创建一个Openai模型客户端
    """
    return OpenAIChatCompletionClient(
        model=os.getenv("MODEL_NAME"),
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
        model_info={
            "vision": False,
            "function_calling":True,
            "json_output":True,
            "structured_output":True,
            "family":"unknown"
        },
    )
def create_summarize_agent( model_client):
    """
    创建一个总结智能体
    它必须是一个AssistantAgent，负责理解用户的需求，总结用户想要了解什么，生成最适合调用工具函数get_blhx_wiki_data的参数
    """
    system_prompt="""
    你是一位专业的碧蓝航线信息总结助手，你能够分析用户的查询需求，总结用户想要了解什么，生成最适合调用工具函数get_blhx_wiki_data的参数，包括舰娘/鱼雷/装备图鉴数据等等
    当接收到用户发送来的请求时:
    1.简洁总结用户想要了解什么
    2.生成最适合调用工具函数get_blhx_wiki_data的参数
    请简洁明了的输出总结和参数
    例如:
    总结: 用户想要了解信浓的信息
    参数: {"name": "信浓"}
    
    并在分析完成后输出"请工具调用专家开始调用函数"
"""
    return AssistantAgent(
        name="summarize_agent",
        model_client=model_client,
        system_message=system_prompt,
    )
    
def create_search_agent( model_client):
    """
    创建一个搜索智能体
    它必须是一个AssistantAgent，负责根据碧蓝航线信息总结智能体的总结和参数，调用工具函数get_blhx_wiki_data，获取用户想要了解的信息
    """
    system_prompt="""
    你是一位专业的碧蓝航线搜索智能助手，你能够根据碧蓝航线信息总结智能体的总结和参数，调用工具函数get_blhx_wiki_data，获取用户想要了解的信息
    工具调用方式：
    参数是 {"name": "xxx"}, 使用 executor.get_tool("get_blhx_wiki_data")(name) 获取字典结果
    当接收到碧蓝航线信息总结智能体的总结和参数时:
    1.根据碧蓝航线信息总结智能体的总结和参数，调用工具函数get_blhx_wiki_data，获取用户想要了解的完整字典数据
    2.把碧蓝航线信息总结智能体的总结和调用工具函数获得的完整字典原封不动的传输给信息提炼智能体
    完成后输出"请信息提炼智能体开始提炼信息"
    """
    return AssistantAgent(
        name="search_agent",
        model_client=model_client,
        system_message=system_prompt,
        tools=[get_blhx_wiki_data]
    )
def create_extract_agent( model_client):
    """
    创建一个信息提炼智能体
    它必须是一个AssistantAgent，负责根据搜索智能体获取到的信息，提炼出用户想要了解的信息
    """
    system_prompt="""
    你是一位专业的碧蓝航线信息提炼助手，你能够根据搜索智能体获取到的完整图鉴字典，提炼出用户想要了解的信息
    当接收到搜索智能体获取到的信息时:
    1.根据用户想要了解到的信息和搜索智能体获取到的完整字典，提炼出用户关心的内容
    2.请简洁明了的输出提炼出的完整信息，
        例如：  信浓稀有度：[海上传奇]
                信浓技能：[技能1,
                技能2,
                技能3]
    
       完成后输出"请用户代理开始执行测试"
    """
    return AssistantAgent(
        name="extract_agent",
        model_client=model_client,
        system_message=system_prompt,
    )
def create_user_proxy( model_client):
    return AssistantAgent(
        name="user_proxy",
        model_client=model_client,
        system_message="""
        用户代理，负责执行以下职责：
        1.将用户提出的搜寻请求和信息提炼智能体输出的信息作判断，判断智能体输出的信息是否符合用户的需求
        当符合用户需求后请回复"Terminated"
        当不符合用户需求后请回复"请extract_agent开始提炼信息"
        """
    )
def custom_selector(messages):
    last_msg=messages[-1]
    if last_msg.source=="user":
        return "summarize_agent"
    content=last_msg.content
    if last_msg.source=="summarize_agent":
        return "search_agent"
    elif last_msg.source=="search_agent":
        return "extract_agent"
    elif last_msg.source=="extract_agent":
        return "user_proxy"
    elif "请extract_agent开始提炼信息" in content:
        return "extract_agent"
    return None
async def run_search_blhx_wiki_data_team(user_query:str):
    print("开始运行搜索智能体团队")
    model_client = create_openai_model_client()
    print("创建模型客户端完成")
    
    summarize_agent = create_summarize_agent(model_client)
    search_agent = create_search_agent(model_client)
    extract_agent = create_extract_agent(model_client)
    user_proxy = create_user_proxy(model_client)
    # 所有agent列表
    agents = [summarize_agent, search_agent, extract_agent, user_proxy]
    # 创建终止条件：文本命中 Terminated 就停止
    termination_condition = TextMentionTermination(text="Terminated")
    # ========== SelectorGroupChat 核心代码 ==========
    team = SelectorGroupChat(
        participants=agents,  
        model_client=model_client,
        termination_condition=termination_condition,
        selector_func=custom_selector,
        max_turns=3
    )
    all_messages = []
    async for event in team.run_stream(task=user_query):
        if isinstance(event, TextMessage):
            all_messages.append(event)
            # 只打印 extract_agent 的输出
            if event.source == "extract_agent":
                print("\n---------- extract_agent 输出 ----------")
                print(event.content)
                print("----------------------------------------\n")
                
    final_answer = None
    for msg in reversed(all_messages):
        if msg.source == "extract_agent":
            final_answer = msg.content
            break
    if final_answer is not None:
        final_answer = final_answer.replace("请用户代理开始执行测试", "").strip()
        return final_answer
    else:
        return "未获取提炼结果"

    
if __name__ == "__main__":
    user_query = "帮我查一下信浓的保底次数"
    result = asyncio.run(run_search_blhx_wiki_data_team(user_query))
    print("协作开发结果:",result)
