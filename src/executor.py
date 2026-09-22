"""
 工具函数执行器，用于存储和执行工具函数
"""

from typing import Callable, Dict, Any
from search import get_blhx_wiki_data

class toolExecutor:
    def __init__(self):
        """
            tools: {"工具名":{"description":"工具描述","function":工具函数,"required":是否必填,"args":参数列表}"}}
            例如:
            tools = {
                "get_blhx_wiki_data": {"description":"获取碧蓝航线舰娘/鱼雷/装备图鉴数据","function":get_blhx_wiki_data,"required":True,"args":["name"]},
            }
        """
        self.tools : Dict[str, Dict[str, Any]] = {}

    def add_tool(self, tool_name: str,description:str,function:Callable):
        """
        添加工具函数
        """
        if tool_name in self.tools:
            print(f"工具函数[{tool_name}]已存在，将被覆盖")
        self.tools[tool_name] = {"description":description,"function":function}

    def get_tool(self,tool_name: str) -> Callable:
        """
        获取一个工具函数
        """
        if tool_name in self.tools:
            return self.tools[tool_name]["function"]
        else:
            print(f"工具函数[{tool_name}]不存在")
            return None

    def get_Available_tools(self) -> str:
        """
        获取所有已注册的工具函数的信息
        """
        return "\n".join([f"{tool_name}: {tool_desc}" for tool_name, tool_desc in self.tools.items()])

from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    executor = toolExecutor()
    executor.add_tool("get_blhx_wiki_data","获取舰娘/鱼雷/装备图鉴数据",get_blhx_wiki_data)
    print(executor.get_Available_tools())
    print("*"*50)
    print(executor.get_tool("get_blhx_wiki_data")("信浓"))
