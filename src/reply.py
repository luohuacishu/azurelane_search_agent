# -*- coding: utf-8 -*-
import asyncio
import os
import re

import botpy
from botpy import logging
from botpy.ext.cog_yaml import read
from botpy.message import GroupMessage

from azurelane_search_agent import run_agent_for_qq

test_config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))
_log = logging.get_logger()

# 触发 AutoGen 完整查询流程的关键词（你可以按需增删）
QUERY_KEYWORDS = ["查", "信浓", "舰娘", "装备", "鱼雷", "保底", "碧蓝", "图鉴", "技能", "稀有度"]


class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot 「{self.robot.name}」 on_ready!")

    async def on_group_at_message_create(self, message: GroupMessage):
        try:
            # 1. 去掉 @机器人 的标记，拿到纯文本
            user_text = re.sub(r"<@!\d+>", "", message.content).strip()
            if not user_text:
                await self._reply(message, "你想问什么呢？比如：帮我查一下信浓的保底次数")
                return

            _log.info(f"收到群消息: {user_text}")

            # 2. 关键词预判：非查询类消息直接回复引导语，不走 AutoGen
            if not any(k in user_text for k in QUERY_KEYWORDS):
                await self._reply(
                    message,
                    "你可以问我碧蓝航线的舰娘、装备、鱼雷图鉴信息~\n"
                    "比如：帮我查一下信浓的保底次数"
                )
                return

            # 3. 调用 AutoGen 多智能体团队（内部已带超时保护）
            reply_text = await run_agent_for_qq(user_text)

            # 4. 长度保护（QQ 单条消息有长度上限）
            if len(reply_text) > 1500:
                reply_text = reply_text[:1500] + "\n...(内容过长已截断)"

            await self._reply(message, reply_text)

        except Exception as e:
            _log.error(f"处理消息时出错: {e}")
            await self._reply(message, "抱歉，我处理时出错了，请稍后再试。")

    async def _reply(self, message: GroupMessage, content: str):
        """统一的回复封装，避免重复代码"""
        try:
            await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type=0,
                msg_id=message.id,
                content=content
            )
        except Exception as e:
            _log.error(f"发送群消息失败: {e}")


if __name__ == "__main__":
    intents = botpy.Intents(public_messages=True)
    client = MyClient(intents=intents)
    client.run(appid=test_config["appid"], secret=test_config["secret"])