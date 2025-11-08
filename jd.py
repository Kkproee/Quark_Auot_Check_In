import os
import requests

cookie = os.environ.get("JD_COOKIE")
token = os.environ.get("PUSHPLUS_TOKEN")

title = 'JDSignIn'

url = ("https://api.m.jd.com/client.action?functionId=signBeanAct&body=%7B%22fp%22%3A%22-1%22%2C%22shshshfp%22%3A%22-1"
       "%22%2C%22shshshfpa%22%3A%22-1%22%2C%22referUrl%22%3A%22-1%22%2C%22userAgent%22%3A%22-1%22%2C%22jda%22%3A%22-1"
       "%22%2C%22rnVersion%22%3A%223.9%22%7D&appid=ld&client=apple&clientVersion=10.0.4&networkType=wifi&osVersion=14"
       ".8.1&uuid=xxxxxx&openudid=xxxxxx&jsonp=jsonp_1645885800574_58482")

headers = {
    "User-Agent": "okhttp/3.12.1;jdmall;android;version/10.3.4",
    "Cookie": cookie
}

response = requests.post(url, headers=headers)
content = response.text

print("token =", token)
print("title =", title)
print("content =", content)

# ✅ 推送
if token:
    pushplus_api = "http://www.pushplus.plus/send"
    params = {
        "token": token,
        "title": title,
        "content": content
    }
    requests.get(pushplus_api, params=params)
    print("✅ 推送完成")
else:
    print("❌ PUSHPLUS_TOKEN 未设置，未推送")
