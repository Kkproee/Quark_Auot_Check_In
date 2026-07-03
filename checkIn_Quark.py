"""
夸克网盘自动签到
使用方法：
    1. 直接运行：python quark_checkin.py
    2. 脚本会先读取环境变量 COOKIE_QUARK，如果没设置则使用下方 DEFAULT_COOKIE
    3. 多账户用换行或 && 分隔

抓包 & 配置方式：
    手机端抓包 → 访问抽奖页 → 找到 url 为
    https://drive-m.quark.cn/1/clouddrive/act/growth/reward 的请求
    复制整段 url（必须含 kps sign vcode 参数）作为 COOKIE_QUARK 的值
    格式：user=任意昵称; url=https://drive-m.quark.cn/1/......;

Author: BNDou (adapted)
"""

import os
import re
import sys
import requests


# ════════════════════════════════════════════════════════════════
# 配置区：可在此直接填入你的 COOKIE_QUARK，或通过环境变量设置
# ════════════════════════════════════════════════════════════════
# 多个账号用 \n 或 && 分隔
# 格式示例：
#   user=昵称1; url=https://drive-m.quark.cn/1/...?kps=...&sign=...&vcode=...;
#   或旧版：
#   user=昵称1; kps=xxx; sign=xxx; vcode=xxx;
#
# 既不填这里也不设环境变量时脚本会退出。
DEFAULT_COOKIE_QUARK = os.environ.get("COOKIE_QUARK", "")

# PushPlus 推送 Token（可选），设了环境变量 PUSHPLUS_TOKEN 会自动推送
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")

try:
    # 尝试加载通知模块，没有也不影响签到
    from utils.notify import send
except ImportError:
    def send(title, content):
        print(f"[通知模块未安装] {title}: {content}")


def pushplus_send(title, content):
    """通过 PushPlus 推送（仅当设置了 PUSHPLUS_TOKEN 时生效）"""
    if not PUSHPLUS_TOKEN:
        return
    try:
        resp = requests.get(
            "http://www.pushplus.plus/send",
            params={"token": PUSHPLUS_TOKEN, "title": title, "content": content},
            timeout=10
        )
        result = resp.json()
        if result.get("code") == 200:
            print("  📬 PushPlus 推送成功")
        else:
            print(f"  ⚠️ PushPlus 推送失败: {result.get('msg', '未知')}")
    except Exception as e:
        print(f"  ⚠️ PushPlus 推送异常: {e}")


def get_env():
    """获取环境变量或默认配置中的 COOKIE_QUARK"""
    cookie_raw = os.environ.get("COOKIE_QUARK") or DEFAULT_COOKIE_QUARK

    if not cookie_raw:
        print("❌ 未设置 COOKIE_QUARK 环境变量，且 DEFAULT_COOKIE_QUARK 为空")
        print("请先配置后再运行")
        sys.exit(1)

    cookie_list = re.split(r"\n|&&", cookie_raw.strip())
    # 过滤空行
    cookie_list = [c.strip() for c in cookie_list if c.strip()]
    return cookie_list


def extract_params(url):
    """从 URL 中提取 kps / sign / vcode 参数"""
    query_start = url.find("?")
    if query_start == -1:
        return {}
    query_string = url[query_start + 1:]
    params = {}
    for pair in query_string.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[key] = value
    return {
        "kps": params.get("kps", ""),
        "sign": params.get("sign", ""),
        "vcode": params.get("vcode", ""),
    }


class Quark:
    """夸克签到 & 抽奖相关操作"""

    def __init__(self, user_data):
        self.param = user_data

    @staticmethod
    def convert_bytes(b):
        """字节 → 可读大小"""
        b = int(b)
        units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = 0
        while b >= 1024 and i < len(units) - 1:
            b /= 1024
            i += 1
        return f"{b:.2f} {units[i]}"

    def get_growth_info(self):
        """获取成长信息（含签到状态）"""
        url = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info"
        params = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.param.get("kps"),
            "sign": self.param.get("sign"),
            "vcode": self.param.get("vcode"),
        }
        try:
            resp = requests.get(url, params=params, timeout=15).json()
            return resp.get("data")
        except Exception as e:
            print(f"  ⚠️ 获取成长信息失败: {e}")
            return False

    def get_growth_sign(self):
        """执行签到请求"""
        url = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign"
        params = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.param.get("kps"),
            "sign": self.param.get("sign"),
            "vcode": self.param.get("vcode"),
        }
        data = {"sign_cyclic": True}
        try:
            resp = requests.post(url, json=data, params=params, timeout=15).json()
            if resp.get("data"):
                return True, resp["data"]["sign_daily_reward"]
            else:
                return False, resp.get("message", "未知错误")
        except Exception as e:
            return False, str(e)

    def query_balance(self):
        """查询抽奖余额"""
        url = "https://coral2.quark.cn/currency/v1/queryBalance"
        params = {
            "moduleCode": "1f3563d38896438db994f118d4ff53cb",
            "kps": self.param.get("kps"),
        }
        try:
            resp = requests.get(url, params=params, timeout=15).json()
            if resp.get("data"):
                return resp["data"]["balance"]
            else:
                return resp.get("msg", "查询失败")
        except Exception as e:
            return str(e)

    def do_sign(self):
        """执行签到，返回结果文本"""
        log = ""
        growth_info = self.get_growth_info()

        if not growth_info:
            return "❌ 签到异常: 获取成长信息失败\n"

        # 用户类型
        vip_tag = "88VIP" if growth_info.get("88VIP") else "普通用户"
        log += f"  {vip_tag} {self.param.get('user', '未命名')}\n"

        # 网盘容量
        total_cap = self.convert_bytes(growth_info["total_capacity"])
        sign_reward = growth_info.get("cap_composition", {}).get("sign_reward", 0)
        sign_reward_str = self.convert_bytes(sign_reward) if sign_reward else "0 MB"
        log += f"  💾 网盘总容量：{total_cap}，签到累计容量：{sign_reward_str}\n"

        # 签到状态
        cap_sign = growth_info.get("cap_sign", {})
        if cap_sign.get("sign_daily"):
            reward = self.convert_bytes(cap_sign.get("sign_daily_reward", 0))
            progress = cap_sign.get("sign_progress", 0)
            target = cap_sign.get("sign_target", 7)
            log += f"  ✅ 今日已签到 +{reward}，连签进度({progress}/{target})\n"
        else:
            success, sign_return = self.get_growth_sign()
            if success:
                reward = self.convert_bytes(sign_return)
                progress = cap_sign.get("sign_progress", 0) + 1
                target = cap_sign.get("sign_target", 7)
                log += f"  ✅ 执行签到成功 +{reward}，连签进度({progress}/{target})\n"
            else:
                log += f"  ❌ 签到异常: {sign_return}\n"

        return log


def main():
    """主函数"""
    print("=" * 40)
    print("     夸克网盘自动签到")
    print("=" * 40)

    accounts = get_env()
    print(f"✅ 检测到共 {len(accounts)} 个夸克账号\n")

    all_messages = []

    for i, account_str in enumerate(accounts, 1):
        print(f"──── 第 {i} 个账号 ────")

        # 解析账号参数
        user_data = {}
        for part in account_str.replace(" ", "").split(";"):
            if not part:
                continue
            if "=" in part:
                key, value = part.split("=", 1)
                user_data[key] = value

        # 从 url 中提取 kps / sign / vcode
        if "url" in user_data:
            url_params = extract_params(user_data["url"])
            # 仅当 url 中包含了这些参数时才覆盖
            if url_params.get("kps"):
                user_data.setdefault("kps", url_params["kps"])
            if url_params.get("sign"):
                user_data.setdefault("sign", url_params["sign"])
            if url_params.get("vcode"):
                user_data.setdefault("vcode", url_params["vcode"])

        # 检查关键参数
        if not user_data.get("kps") or not user_data.get("sign"):
            msg = f"  ❌ 账号 {i} 缺少 kps/sign 参数，跳过\n"
            print(msg)
            all_messages.append(msg)
            continue

        # 执行签到
        quark = Quark(user_data)
        result = quark.do_sign()
        print(result)
        all_messages.append(result)

    final_msg = "\n".join(all_messages).strip()
    if final_msg:
        try:
            send("夸克自动签到", final_msg)
        except Exception as e:
            print(f"⚠️ 通知发送失败: {e}")
        pushplus_send("夸克自动签到", final_msg)

    return final_msg


if __name__ == "__main__":
    print("\n---------- 夸克网盘开始签到 ----------\n")
    main()
    print("\n---------- 夸克网盘签到完毕 ----------")
