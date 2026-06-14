import unittest
from unittest.mock import patch

from xianyu_qr_login import QRLoginManager, QRLoginSession, build_qr_login_display_lines


class FakeResponse:
    def __init__(self, *, json_data=None, text="", cookies=None):
        self._json_data = json_data or {}
        self.text = text
        self.cookies = cookies or {}

    def json(self):
        return self._json_data


class FakeClient:
    def __init__(self, *, query_json=None, query_cookies=None):
        self.query_json = query_json or {
            "content": {"data": {"qrCodeStatus": "NEW"}}
        }
        self.query_cookies = query_cookies or {}

    def get(self, url, **kwargs):
        if "mtop.gaia.nodejs.gaia.idle.data.gw" in url:
            return FakeResponse(cookies={"m_h5_tk": "token_123", "m_h5_tk_enc": "enc"})

        if "mini_login.htm" in url:
            return FakeResponse(
                text='window.viewData = {"loginFormData": {"appName": "xianyu", "fromSite": "77"}};'
            )

        if "qrcode/generate.do" in url:
            return FakeResponse(
                json_data={
                    "content": {
                        "success": True,
                        "data": {
                            "t": "login_t",
                            "ck": "login_ck",
                            "codeContent": "https://login.example/qr",
                        },
                    }
                }
            )

        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, **kwargs):
        if "mtop.gaia.nodejs.gaia.idle.data.gw" in url:
            return FakeResponse()

        if "qrcode/query.do" in url:
            return FakeResponse(json_data=self.query_json, cookies=self.query_cookies)

        raise AssertionError(f"unexpected POST {url}")


class QRLoginManagerTests(unittest.TestCase):
    def test_generate_qr_code_stores_waiting_session(self):
        manager = QRLoginManager(client_factory=lambda: FakeClient())

        with patch.object(manager, "_render_qr_data_url", return_value="data:image/png;base64,abc"):
            result = manager.generate_qr_code()

        self.assertTrue(result["success"])
        self.assertTrue(result["session_id"])
        self.assertEqual(result["qr_code_url"], "data:image/png;base64,abc")

        session = manager.sessions[result["session_id"]]
        self.assertEqual(session.status, "waiting")
        self.assertEqual(session.qr_content, "https://login.example/qr")
        self.assertEqual(session.params["t"], "login_t")
        self.assertEqual(session.params["ck"], "login_ck")

    def test_poll_once_confirmed_merges_cookies_and_exposes_cookie_string(self):
        manager = QRLoginManager(
            client_factory=lambda: FakeClient(
                query_json={"content": {"data": {"qrCodeStatus": "CONFIRMED"}}},
                query_cookies={"unb": "seller123", "_m_h5_tk": "new_token_456"},
            )
        )
        session = QRLoginSession("session-1")
        session.params = {"appName": "xianyu"}
        session.cookies = {"existing": "cookie"}
        manager.sessions[session.session_id] = session

        status = manager.poll_once(session.session_id)

        self.assertEqual(status["status"], "success")
        self.assertEqual(status["unb"], "seller123")
        self.assertIn("existing=cookie", status["cookies"])
        self.assertIn("unb=seller123", status["cookies"])
        self.assertIn("_m_h5_tk=new_token_456", status["cookies"])

    def test_display_lines_include_qr_content_link_and_png_path(self):
        lines = build_qr_login_display_lines(
            qr_content="https://login.example/qr",
            png_path="/tmp/xianyu-login-qr.png",
        )

        display = "\n".join(lines)
        self.assertIn("https://login.example/qr", display)
        self.assertIn("/tmp/xianyu-login-qr.png", display)


if __name__ == "__main__":
    unittest.main()
