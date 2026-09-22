import requests
from requests.exceptions import HTTPError, ConnectionError, Timeout
import mwparserfromhell
from urllib.parse import quote
import re
import json
import time

def get_blhx_wiki_data(name: str):
    """
    碧蓝海事局wiki统一查询工具
    :自动解析舰娘图鉴/鱼雷图鉴/#invoke装备图鉴
    :param name: wiki页面标题
    :return: dict，解析后的图鉴数据；失败返回None
    """
    def clean_wiki_text(text: str) -> str:
        """清洗wiki标记"""
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"\[\[([^|]*\|)?([^\]]*)\]\]", r"\2", text)
        text = re.sub(r"{{黑幕\|([^}]*)}}", r"\1", text)
        text = re.sub(r"{{.*?}}", "", text)
        return text.strip()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = (
        f"https://wiki.biligame.com/blhx/api.php"
        f"?action=query&prop=revisions&rvslots=*&rvprop=content"
        f"&titles={quote(name)}&format=json"
    )
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code >= 400:
            raise HTTPError(f"Status {resp.status_code}")
        data = resp.json()
        pages = data["query"]["pages"]
        page = list(pages.values())[0]
        if "missing" in page:
            print(f"页面不存在：{name}")
            return None
        wikitext = page["revisions"][0]["slots"]["main"]["*"]
    except HTTPError as e:
        print(f"【HTTP错误】: {e}")
        return None
    except (ConnectionError, Timeout) as e:
        print(f"【网络/超时】: {e}")
        return None
    except Exception as e:
        print(f"【未知异常】: {e}")
        return None

    # ========== 解析模板，支持普通图鉴 和 #invoke lua图鉴 ==========
    wiki_code = mwparserfromhell.parse(wikitext)
    templates = wiki_code.filter_templates()
    for tpl in templates:
        tpl_name = str(tpl.name).strip()
        data_out = {"_template_name": tpl_name}
        # #invoke:装备图鉴 这类Lua模板，跳过第一个main参数
        if tpl_name.startswith("#invoke:") and tpl_name.endswith("图鉴"):
            for idx, param in enumerate(tpl.params):
                if idx == 0:
                    continue
                key = str(param.name).strip()
                val = clean_wiki_text(str(param.value).strip())
                if key:
                    data_out[key] = val
            return data_out
        if tpl_name.endswith("图鉴"):
            for param in tpl.params:
                key = str(param.name).strip()
                val = clean_wiki_text(str(param.value).strip())
                if key:
                    data_out[key] = val
            return data_out

    print(f"页面[{name}]没有找到xxx图鉴模板")
    return None


if __name__ == "__main__":
    # 正确调用方式：接收返回字典对象
    res = get_blhx_wiki_data("信浓")
    if res:
        
        print(json.dumps(res, ensure_ascii=False, indent=2))
    print(type(res))
