#!/usr/bin/env python3
"""
闲鱼Cookie诊断工具
用于检查.env文件中的COOKIES_STR是否完整有效
"""
import os
from dotenv import load_dotenv

def check_cookies():
    """检查Cookie配置"""
    print("=" * 60)
    print("🔍 闲鱼Cookie诊断工具")
    print("=" * 60)

    # 加载.env文件
    if not os.path.exists('.env'):
        print("❌ 错误：.env文件不存在！")
        print("💡 请从.env.example创建.env文件")
        return False

    load_dotenv()
    cookies_str = os.getenv('COOKIES_STR', '')

    if not cookies_str:
        print("❌ 错误：COOKIES_STR为空！")
        print("💡 请在.env文件中配置COOKIES_STR")
        return False

    print(f"\n📋 Cookie长度: {len(cookies_str)} 字符")
    print(f"📋 Cookie片段: {cookies_str[:100]}...")

    # 解析cookies
    cookies = {}
    for cookie in cookies_str.split('; '):
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies[key.strip()] = value.strip()

    print(f"\n📊 解析到 {len(cookies)} 个Cookie项\n")

    # 检查关键cookies
    required_cookies = {
        'cna': '设备标识',
        '_m_h5_tk': 'H5 Token',
        '_m_h5_tk_enc': 'H5 Token加密',
        'cookie2': 'Cookie2',
        'unb': '用户标识',
        'XSRF-TOKEN': 'CSRF Token'
    }

    missing_cookies = []
    for cookie_name, description in required_cookies.items():
        if cookie_name in cookies:
            value = cookies[cookie_name]
            # 只显示前20个字符
            display_value = value[:20] + '...' if len(value) > 20 else value
            print(f"✅ {cookie_name:15} ({description:15}): {display_value}")
        else:
            print(f"❌ {cookie_name:15} ({description:15}): 缺失")
            missing_cookies.append(cookie_name)

    print("\n" + "=" * 60)

    if missing_cookies:
        print(f"⚠️  缺少 {len(missing_cookies)} 个关键Cookie: {', '.join(missing_cookies)}")
        print("\n💡 解决方案：")
        print("1. 打开浏览器访问 https://www.goofish.com/")
        print("2. 登录你的闲鱼账号")
        print("3. 按F12打开开发者工具")
        print("4. 切换到Network标签")
        print("5. 刷新页面")
        print("6. 点击任意请求，在Headers中找到Cookie")
        print("7. 复制完整的Cookie值，更新到.env文件的COOKIES_STR中")
        return False
    else:
        print("✅ 所有关键Cookie都存在！")
        print("\n💡 如果仍然出现错误，可能的原因：")
        print("1. Cookie已过期 - 需要重新获取")
        print("2. 触发了风控 - 等待几分钟后重试")
        print("3. IP被限制 - 尝试更换网络环境")
        return True

if __name__ == '__main__':
    check_cookies()
