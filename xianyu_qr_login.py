import base64
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from random import random
from typing import Any, Callable, Dict, Optional

import requests
from loguru import logger

try:
    import qrcode
    import qrcode.constants
except ImportError:  # pragma: no cover - exercised only when dependencies are missing.
    qrcode = None


class QRLoginError(Exception):
    """Raised when QR login cannot continue."""


class QRLoginVerificationRequired(QRLoginError):
    """Raised when Xianyu asks for additional phone or risk-control verification."""


@dataclass
class QRLoginSession:
    session_id: str
    status: str = "waiting"
    qr_code_url: Optional[str] = None
    qr_content: Optional[str] = None
    cookies: Dict[str, str] = field(default_factory=dict)
    unb: Optional[str] = None
    created_time: float = field(default_factory=time.time)
    expire_time: int = 300
    params: Dict[str, Any] = field(default_factory=dict)
    verification_url: Optional[str] = None

    def is_expired(self) -> bool:
        return time.time() - self.created_time > self.expire_time


class QRLoginManager:
    """Generate and poll Xianyu QR login sessions."""

    def __init__(
        self,
        *,
        client_factory: Optional[Callable[[], Any]] = None,
        timeout: int = 60,
    ):
        self.sessions: Dict[str, QRLoginSession] = {}
        self.client_factory = client_factory or requests.Session
        self.timeout = timeout
        self.host = "https://passport.goofish.com"
        self.api_mini_login = f"{self.host}/mini_login.htm"
        self.api_generate_qr = f"{self.host}/newlogin/qrcode/generate.do"
        self.api_scan_status = f"{self.host}/newlogin/qrcode/query.do"
        self.api_h5_tk = (
            "https://h5api.m.goofish.com/h5/"
            "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get/1.0/"
        )
        self.headers = self._generate_headers()

    def _generate_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://passport.goofish.com/",
            "Origin": "https://passport.goofish.com",
        }

    def _new_client(self):
        client = self.client_factory()
        if hasattr(client, "headers"):
            client.headers.update(self.headers)
        return client

    def _cookies_to_dict(self, cookies: Any) -> Dict[str, str]:
        return {k: v for k, v in dict(cookies or {}).items() if v is not None}

    def _cookie_marshal(self, cookies: Dict[str, str]) -> str:
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def _get_mh5tk(self, session: QRLoginSession) -> None:
        data = {"bizScene": "home"}
        data_str = json.dumps(data, separators=(",", ":"))
        timestamp = str(int(time.time() * 1000))
        app_key = "34839810"
        client = self._new_client()

        resp = client.get(self.api_h5_tk, headers=self.headers, timeout=self.timeout)
        session.cookies.update(self._cookies_to_dict(resp.cookies))

        m_h5_tk = session.cookies.get("m_h5_tk", "")
        token = m_h5_tk.split("_")[0] if "_" in m_h5_tk else ""
        sign_input = f"{token}&{timestamp}&{app_key}&{data_str}"
        sign = hashlib.md5(sign_input.encode()).hexdigest()

        params = {
            "jsv": "2.7.2",
            "appKey": app_key,
            "t": timestamp,
            "sign": sign,
            "v": "1.0",
            "type": "originaljson",
            "dataType": "json",
            "timeout": 20000,
            "api": "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
            "data": data_str,
        }
        client.post(
            self.api_h5_tk,
            params=params,
            headers=self.headers,
            cookies=session.cookies,
            timeout=self.timeout,
        )

    def _get_login_params(self, session: QRLoginSession) -> None:
        params = {
            "lang": "zh_cn",
            "appName": "xianyu",
            "appEntrance": "web",
            "styleType": "vertical",
            "bizParams": "",
            "notLoadSsoView": False,
            "notKeepLogin": False,
            "isMobile": False,
            "qrCodeFirst": False,
            "stie": 77,
            "rnd": random(),
        }
        client = self._new_client()
        resp = client.get(
            self.api_mini_login,
            params=params,
            cookies=session.cookies,
            headers=self.headers,
            timeout=self.timeout,
        )

        match = re.search(r"window\.viewData\s*=\s*(\{.*?\});", resp.text, re.S)
        if not match:
            raise QRLoginError("获取二维码登录参数失败：页面中未找到 viewData")

        view_data = json.loads(match.group(1))
        form_data = view_data.get("loginFormData")
        if not form_data:
            raise QRLoginError("获取二维码登录参数失败：页面中未找到 loginFormData")

        form_data["umidTag"] = "SERVER"
        session.params.update(form_data)

    def _render_qr_data_url(self, qr_content: str) -> str:
        if qrcode is None:
            raise QRLoginError("缺少 qrcode 依赖，请先运行 pip install -r requirements.txt")

        qr = qrcode.QRCode(
            version=5,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{qr_base64}"

    def generate_qr_code(self) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        session = QRLoginSession(session_id)

        self._get_mh5tk(session)
        self._get_login_params(session)

        client = self._new_client()
        resp = client.get(
            self.api_generate_qr,
            params=session.params,
            cookies=session.cookies,
            headers=self.headers,
            timeout=self.timeout,
        )
        result = resp.json()

        if result.get("content", {}).get("success") is not True:
            raise QRLoginError(f"获取登录二维码失败：{result}")

        data = result["content"]["data"]
        session.params.update({"t": data["t"], "ck": data["ck"]})
        session.qr_content = data["codeContent"]
        session.qr_code_url = self._render_qr_data_url(session.qr_content)
        session.status = "waiting"
        self.sessions[session_id] = session

        logger.info(f"二维码生成成功: {session_id}")
        return {
            "success": True,
            "session_id": session_id,
            "qr_code_url": session.qr_code_url,
            "qr_content": session.qr_content,
        }

    def poll_once(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "not_found", "session_id": session_id}
        if session.is_expired() and session.status != "success":
            session.status = "expired"
            return self.get_session_status(session_id)

        client = self._new_client()
        resp = client.post(
            self.api_scan_status,
            data=session.params,
            cookies=session.cookies,
            headers=self.headers,
            timeout=self.timeout,
        )
        data = resp.json().get("content", {}).get("data", {})
        qr_status = data.get("qrCodeStatus")

        if qr_status == "CONFIRMED":
            if data.get("iframeRedirect") is True:
                session.status = "verification_required"
                session.verification_url = data.get("iframeRedirectUrl")
                return self.get_session_status(session_id)

            session.status = "success"
            session.cookies.update(self._cookies_to_dict(resp.cookies))
            if "unb" in session.cookies:
                session.unb = session.cookies["unb"]
            return self.get_session_status(session_id)

        if qr_status == "SCANED":
            session.status = "scanned"
        elif qr_status == "EXPIRED":
            session.status = "expired"
        elif qr_status == "NEW":
            session.status = "waiting"
        elif qr_status:
            session.status = "cancelled"

        return self.get_session_status(session_id)

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "not_found", "session_id": session_id}
        if session.is_expired() and session.status != "success":
            session.status = "expired"

        result: Dict[str, Any] = {"status": session.status, "session_id": session_id}
        if session.status == "verification_required":
            result["verification_url"] = session.verification_url
            result["message"] = "账号被风控，需要手机验证"
        if session.status == "success":
            result["cookies"] = self._cookie_marshal(session.cookies)
            result["unb"] = session.unb
        return result

    def wait_for_login(self, session_id: str, *, timeout_seconds: int = 300) -> Dict[str, Any]:
        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout_seconds:
            status = self.poll_once(session_id)
            state = status.get("status")
            if state != last_status:
                logger.info(f"扫码登录状态: {state}")
                last_status = state

            if state in {"success", "expired", "cancelled", "verification_required", "not_found"}:
                return status
            time.sleep(0.8)

        session = self.sessions.get(session_id)
        if session and session.status != "success":
            session.status = "expired"
        return self.get_session_status(session_id)


def _save_qr_png(qr_data_url: str, output_dir: str = "data") -> str:
    os.makedirs(output_dir, exist_ok=True)
    _, encoded = qr_data_url.split(",", 1)
    path = os.path.abspath(os.path.join(output_dir, "xianyu-login-qr.png"))
    with open(path, "wb") as f:
        f.write(base64.b64decode(encoded))
    return path


def _print_qr_ascii(qr_content: str) -> None:
    if qrcode is None:
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(qr_content)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def build_qr_login_display_lines(*, qr_content: str, png_path: str) -> list[str]:
    return [
        f"二维码登录链接: {qr_content}",
        f"二维码图片文件: {png_path}",
    ]


def run_qr_login_cli(*, timeout_seconds: int = 300) -> str:
    """Run QR login in the terminal and return the complete cookie string."""
    manager = QRLoginManager()
    result = manager.generate_qr_code()
    session_id = result["session_id"]

    print("\n请使用闲鱼 App 扫描下方二维码并在手机上确认登录：\n")
    _print_qr_ascii(result["qr_content"])
    png_path = _save_qr_png(result["qr_code_url"])
    print()
    for line in build_qr_login_display_lines(
        qr_content=result["qr_content"],
        png_path=png_path,
    ):
        print(line)
    print("\n如果终端二维码不可扫，可以打开图片文件或二维码登录链接。")
    print("等待扫码确认中，二维码约 5 分钟内有效...\n")

    status = manager.wait_for_login(session_id, timeout_seconds=timeout_seconds)
    state = status.get("status")

    if state == "success" and status.get("cookies"):
        print("扫码登录成功，已获取 Cookie。")
        return status["cookies"]
    if state == "verification_required":
        url = status.get("verification_url") or ""
        raise QRLoginVerificationRequired(f"账号触发风控，需要手机验证：{url}")
    raise QRLoginError(f"扫码登录未完成，当前状态：{state}")
