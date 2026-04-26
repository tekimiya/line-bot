import os
import hmac
import hashlib
import base64
import json
from flask import Flask, request, abort
import requests
import anthropic

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ['LINE_CHANNEL_SECRET']
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']

SCHEDULE = """
4月班表：
04/01 休假 | 04/02 飛行 BR192 TSA（松山）→HND（東京羽田）07:19起飛/BR191 HND→TSA 12:41起飛 報到05:50
04/03 生理假 | 04/04 病假
04/05 飛行 BR281 TPE（桃園）→CEB（宿霧）08:02/BR282 CEB→TPE 12:18 報到06:00
04/06 飛行 BR805 TPE→MFM（澳門）16:37/BR806 MFM→TPE 20:16 報到14:40
04/07 休假(ADO) | 04/08 休假 | 04/09 休假(ADO)
04/10 特殊假(YH) | 04/11 特殊假(YI)
04/12 飛行 BR192 TSA→HND 07:21/BR191 HND→TSA 12:37 報到05:50
04/13 飛行 BR772 TSA→SHA（上海虹橋）14:53/BR771 SHA→TSA 19:37 報到13:25
04/14 休假 | 04/15 休假
04/16 飛行(金門梭) B78801 TSA→KNH（金門）→TSA→KNH→TSA 報到06:00
04/17 飛行 BR192 TSA→HND 07:28/BR191 HND→TSA 12:43 報到05:50
04/18 休假(ADO) | 04/19 家庭照顧假
04/20 飛行 BR118 TPE→SDJ（仙台）10:12 報到08:05
04/21 飛行 BR117 SDJ→TPE 16:14 報到07:39
04/22 飛行 BR772 TSA→SHA 15:05/BR771 SHA→TSA 19:31 報到13:25
04/23 休假(ADO) | 04/24 特殊
04/25 飛行 BR772 TSA→SHA 15:11/BR771 SHA→TSA 19:27 報到13:25
04/26 休假
04/27 飛行(馬公梭) B78607 TSA→MZG（馬公）→TSA→MZG→TSA 報到07:20
04/28 待命(Q05) | 04/29 飛行 BR190 TSA→HND 16:20 報到14:50
04/30 飛行(續) BR189 HND（東京羽田）→TSA 10:50

5月班表：
05/01 休假
05/02 飛行(金門梭) B78801 TSA→KNH→TSA→KNH→TSA 報到06:00
05/03 飛行(金門梭) 同上 報到06:00
05/04 待命(Q12) | 05/05 休假(ADO) | 05/06 休假
05/07 飛行 BR772 TSA→SHA 14:55/BR771 SHA→TSA 19:40 報到13:25
05/08 飛行(廈門) B7511 TSA→XMN（廈門）17:00/B7512 XMN→TSA 19:40 報到15:30
05/09 飛行 BR772 TSA→SHA 14:55/BR771 SHA→TSA 19:40 報到13:25
05/10 特殊假(YJ)
05/11 飛行(馬公梭) B78601 TSA→MZG→TSA→MZG→TSA 報到06:15
05/12 休假(ADO) | 05/13 休假
05/14 飛行(馬公梭) B78601 TSA→MZG→TSA→MZG→TSA 報到06:15
05/15 飛行(廈門) B7511 TSA→XMN 17:00/B7512 XMN→TSA 19:40 報到15:30
05/16 飛行 BR772 TSA→SHA 14:55/BR771 SHA→TSA 19:40 報到13:25
05/17 飛行(巴黎) BR87 TPE→CDG（巴黎戴高樂）23:30 報到21:30
05/18 飛行中(BR87前往巴黎) | 05/19 Layover在巴黎(CDG)
05/20 飛行 BR88 CDG→TPE 11:20 | 05/21 飛行中(BR88返台)
05/22 休假(ADO) | 05/23 休假 | 05/24 休假 | 05/25 休假
05/26 休假(ADO)
05/27 飛行 BR192 TSA→HND 07:20/BR191 HND→TSA 12:40 報到05:50
05/28 休假
05/29 飛行 BR190 TSA→HND 16:20 報到14:50
05/30 飛行(續) BR189 HND→TSA 10:50
05/31 飛行 BR192 TSA→HND 07:20 報到05:50
"""

SYSTEM_PROMPT = f"""你是杜珮瑄的長榮航空班表助理。她是長榮航空空服員（員工編號 F59113）。

請用繁體中文回答，語氣自然像朋友聊天，簡潔不囉嗦。

她的 4-5 月班表：
{SCHEDULE}

班表代碼說明：
- DO / ADO：休假
- Y開頭+字母（YJ/YH/YI）、FL、SL、MEN、AL：各種假別
- 待命班（字母+數字，如 Q05、Q12、J13）：待命，共3小時，公司可能臨時抓飛
- LO：Layover（外站過夜）
- 飛行中：長程航班途中

回答原則：
- 只回答班表相關問題
- 如果問今天/明天，請根據台北時間判斷日期
- 不知道的資訊（如組員名單）就說需要登入查詢
- 遇到不相關的問題，說你只負責班表事宜"""


def verify_signature(body_bytes, signature):
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode('utf-8'),
        body_bytes,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash_value).decode('utf-8')
    return hmac.compare_digest(expected, signature)


def reply_to_line(reply_token, text):
    resp = requests.post(
        'https://api.line.me/v2/bot/message/reply',
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        },
        json={
            'replyToken': reply_token,
            'messages': [{'type': 'text', 'text': text}]
        },
        timeout=10
    )
    if resp.status_code != 200:
        print(f"LINE API error: {resp.status_code} {resp.text}", flush=True)


def ask_claude(user_message):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_message}]
    )
    return response.content[0].text


@app.route('/', methods=['GET'])
def health():
    return 'OK'


@app.route('/webhook', methods=['POST'])
def webhook():
    body_bytes = request.get_data()
    signature = request.headers.get('X-Line-Signature', '')

    data = json.loads(body_bytes)

    if data.get('events'):
        if not verify_signature(body_bytes, signature):
            abort(400)

        for event in data['events']:
            if event.get('type') == 'message' and event['message'].get('type') == 'text':
                reply_token = event['replyToken']
                user_message = event['message']['text']
                try:
                    response_text = ask_claude(user_message)
                    reply_to_line(reply_token, response_text)
                except Exception as e:
                    print(f"ERROR: {e}", flush=True)
                    reply_to_line(reply_token, '抱歉，我現在有點忙，請稍後再問我 😅')

    return 'OK'


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
