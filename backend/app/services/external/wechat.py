"""微信公众号接口（Phase 9）：access_token、带参数二维码、webhook 签名校验、事件 XML 解析。

调用方均在异步路由里，耗网络的函数用 run_in_threadpool 包裹。
"""
import hashlib
import xml.etree.ElementTree as ET
import logging
from urllib.parse import quote

import requests

logger = logging.getLogger("app.wechat")


def fetch_access_token(appid: str, appsecret: str) -> str:
    r = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": appid, "secret": appsecret},
        timeout=10,
    )
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"获取access_token失败: {data}")
    return data["access_token"]


def create_qrcode_ticket(access_token: str, scene_id: int, expire_seconds: int = 300) -> str:
    r = requests.post(
        f"https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token={access_token}",
        json={
            "expire_seconds": expire_seconds,
            "action_name": "QR_SCENE",
            "action_info": {"scene": {"scene_id": scene_id}},
        },
        timeout=10,
    )
    data = r.json()
    if "ticket" not in data:
        raise RuntimeError(f"创建二维码失败: {data}")
    return data["ticket"]


def ticket_to_url(ticket: str) -> str:
    return f"https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket={quote(ticket)}"


def verify_signature(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    sha1 = hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode()).hexdigest()
    return sha1 == signature


def parse_xml_event(body: bytes) -> dict:
    try:
        root = ET.fromstring(body)
        return {child.tag: (child.text or "") for child in root}
    except ET.ParseError:
        return {}


def create_menu(access_token: str, menu: dict) -> dict:
    r = requests.post(
        f"https://api.weixin.qq.com/cgi-bin/menu/create?access_token={access_token}",
        json=menu,
        timeout=10,
    )
    return r.json()


def send_template_message(access_token: str, openid: str, template_id: str, data: dict, url: str = "") -> dict:
    """发送公众号模板消息；模板字段需与公众平台配置一致。"""
    r = requests.post(
        f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}",
        json={"touser": openid, "template_id": template_id, "url": url, "data": data},
        timeout=10,
    )
    return r.json()


def build_text_reply(to_user: str, from_account: str, content: str) -> str:
    import time as _t
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_account}]]></FromUserName>"
        f"<CreateTime>{int(_t.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )
