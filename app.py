import os
import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, request, abort
import requests
import anthropic
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ['LINE_CHANNEL_SECRET']
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
LINE_PUSH_USER_ID = 'U43f403149806d8e5def5b42cca840dd6'

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
05/02 飛行(金門梭) B78801 TSA→KNH→TSA→KNH→TS@ 報到06:00
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
- 飛行$��ﺦ長程航班途中

各航班飛行時數（格式 時:分）：
BR192 TSA→HND: 03:10
BR191 HND→TSA: 03:25
BR190 TSA→HND: 03:00
BR189 HND→TSA: 03:40
BR118 TPE→SDJ: 03:30
BR117 SDJ→TPE: 03:50
BR281 TPE→CEB: 02:50
BR282 CEB→TPE: 02:55
BR805 TPE→MFM: 01:55
BR806 MFM→TPE: 01:55
BR772 TSA→SHA: 01:35
BR771 SHA→TSA: 02:05
B7511 TSA→XMN: 01:40
B7512 XMN→TSA: 01:45
BR87 TPE→CDG: 14:55
BR88 CDG→TPE: 13:25
B78801 TSA→KNH: 01:05
B78802 KNH→TSA: 01:00
B78811 TSA→KNH: 01:05
B78812 KNH→TSA: 01:00
B78607/B78609/B78601 TSA→MZG: 00:50
B78608/B78610/B78602/B78616 MZG→TSA: 00:50

回答原則：
- 只回答班表相關問題
- 如果問今天/明天，請根據台北時間判斷日期
- 不知道的資訊（如組員名單）就說需要登入查該
- 遇到不相關的問題，說你只負責班表事宜"""

AIRPORTS = {
    'TSA': '松山', 'TPE': '桃園', 'HND': '東京羽田', 'NRT': '東京成田',
    'SHA': '上海虹橋', 'PVG': '上海浦東', 'XMN': '廈門', 'MZG': '馬公',
    'KNH': '金門', 'CDG': '巴黎戴高樂', 'MFM': '澳門', 'CEB': '宿霧',
    'SDJ': '仙台', 'HKG': '香港', 'BKK': '曼谷', 'SIN': '新加坡',
}

DAILY_SCHEDULE = {
    '04/27': {'type': 'fly', 'checkin': '07:20', 'flights': [
        ('B78607', 'TSA', 'MZG', '08:20', '09:10'),
        ('B78608', 'MZG', 'TSA', '10:00', '10:50'),
        ('B78609', 'TSA', 'MZG', '11:40', '12:30'),
        ('B78616', 'MZG', 'TSA', '13:40', '14:30'),
    ]},
    '04/28': {'type': 'standby', 'code': 'Q05'},
    '04/29': {'type': 'fly', 'checkin': '14:50', 'flights': [
        ('BR190', 'TSA', 'HND', '16:20', '20:20'),
    ]},
    '04/30': {'type': 'fly_cont', 'flights': [
        ('BR189', 'HND', 'TSA', '10:50', '13:30'),
    ]},
    '05/01': {'type': 'off'},
    '05/02': {'type': 'fly', 'checkin': '06:00', 'flights': [
        ('B78801', 'TSA', 'KNH', '07:00', '08:05'),
        ('B78802', 'KNH', 'TSA', '08:55', '09:55'),
        ('B78811', 'TSA', 'KNH', '10:45', '11:50'),
        ('B78812', 'KNH', 'TSA', '12:40', '13:40'),
    ]},
    '05/03': {'type': 'fly', 'checkin': '06:00', 'flights': [
        ('B78801', 'TSA', 'KNH', '07:00', '08:05'),
        ('B78802', 'KNH', 'TSA', '08:55', '09:55'),
        ('B78811', 'TSA', 'KNH', '10:45', '11:50'),
        ('B78812', 'KNH', 'TSA', '12:40', '13:40'),
    ]},
    '05/04': {'type': 'standby', 'code': 'Q12'},
    '05/05': {'type': 'off'},
    '05/06': {'type': 'off'},
    '05/07': {'type': 'fly', 'checkin': '13:25', 'flights': [
        ('BR772', 'TSA', 'SHA', '14:55', '16:30'),
        ('BR771', 'SHA', 'TSA', '19:40', '21:45'),
    ]},
    '05/08': {'type': 'fly', 'checkin': '15:30', 'flights': [
        ('B7511', 'TSA', 'XMN', '17:00', '18:40'),
        ('B7512', 'XMN', 'TSA', '19:40', '21:25'),
    ]},
    '05/09': {'type': 'fly', 'checkin': '13:25', 'flights': [
        ('BR772', 'TSA', 'SHA', '14:55', '16:30'),
        ('BR771', 'SHA', 'TSA', '19:40', '21:45'),
    ]},
    '05/10': {'type': 'off'},
    '05/11': {'type': 'fly', 'checkin': '06:15', 'flights': [
        ('B78601', $TSA', 'MZG', '07:15', '08:05'),
        ('B78602', 'MZG', 'TSA', '08:55', '09:45'),
        ('B78609', 'TSA', 'MZG', '10:35', '11:25'),
        ('B78610', 'MZG', 'TSA', '12:15', '13:05'),
    ]},
    '05/12': {'type': 'off'},
    '05/13': {'type': 'off'},
    '05/14': {'type': 'fly', 'checkin': '06:15', 'flights': [
        ('B78601', 'TSA', 'MZG', '07:15', '08:05'),
        ('B78602', 'MZG', 'TSA', '08:55', '09:45'),
        ('B78609', 'TSA', 'MZG', '10:35', '11:25'),
        ('B78610', 'MZG', 'TSA', '12:15', '13:05'),
    ]},
    '05/15': {'type': 'fly', 'checkin': '15:30', 'flights': [
        ('B7511', 'TSA', 'XMN', '17:00', '18:40'),
        ('B7512', 'XMN', 'TSA', '19:40', '21:25'),
    ]},
    '05/16': {'type': 'fly', 'checkin': '13:25', 'flights': [
        ('BR772', 'TSA', 'SHA', '14:55', '16:30'),
        ('BR771', 'SHA', 'TSA', '19:40', '21:45'),
    ]},
    '05/17': {'type': 'fly', 'checkin': '21:30', 'flights': [
        ('BR87', 'TPE', 'CDG', '23:30', '(+1)08:25'),
    ]},
    '05/18': {'type': 'in_flight'},
    '05/19': {'type': 'layover'},
    '05/20': {'type': 'fly_cont', 'flights': [
        ('BR88', 'CDG', 'TPE', '11:20', '(+1)06:45'),
    ]},
    '05/21': {'type': 'in_flight'},
    '05/22': {'type': 'off'},
    '05/23': {'type': 'off'},
    '05/24': {'type': 'off'},
    '05/25': {'type': 'off'},
    '05/26': {'type': 'off'},
    '05/27': {'type': 'fly', 'checkin': '05:50', 'flights': [
        ('BR192', 'TSA', 'HND', '07:20', '11:30'),
        ('BR191', 'HND', 'TSA', '12:40', '15:05'),
    ]},
    '05/28': {'type': 'off'},
    '05/29': {'type': 'fly', 'checkin': '14:50', 'flights': [
        ('BR190', 'TSA', 'HND', '16:20', '20:20'),
    ]},
    '05/30': {'type': 'fly_cont', 'flights': [
        ('BR189', 'HND', 'TSA', '10:50', '13:30'),
    ]},
    '05/31': {'type': 'fly', 'checkin': '05:50', 'flights': [
        ('BR192', 'TSA', 'HND', '07:20', '11:30'),
    ]},
}

WEEKDAY_MAP = {0: '週一', 1: '週二', 2: '週三', 3: '週四', 4: '週五', 5: '週六', 6: '週日'}


def build_reminder_message():
    tpe = pytz.timezone('Asia/Taipei')
    tomorrow = datetime.now(tpe) + timedelta(days=1)
    month_day = tomorrow.strftime('%m/%d')
    weekday = WEEKDAY_MAP[tomorrow.weekday()]

    day = DAILY_SCHEDULE.get(month_day)
    if not day:
        return None

    dtype = day['type']

    if dtype in ('in_flight', 'layover'):
        return None

    if dtype == 'off':
        return f'😴 明天 {month_day}（{weekday}）休假\n好好放鬆充電！'

    if dtype == 'standby':
        return f'⏰ 明天 {month_day}（{weekday}）待命（{day["code"]}）\n保持手機暢通！'

    if dtype in ('fly', 'fly_cont'):
        lines = [f'✈️ 明天 {month_day}（{weekday}）班表提醒']
        if dtype == 'fly' and day.get('checkin'):
            lines.append(f'\n報到：{day["checkin"]}')
        for flt, dep, arr, dep_t, arr_t in day['flights']:
            dep_cn = AIRPORTS.get(dep, dep)
            arr_cn = AIRPORTS.get(arr, arr)
            lines.append(f'\n{dep_cn} → {arr_cn}  {flt}\n起飛：{dep_t}　落地：{arr_t}')
        lines.append('\n👥 組員名單需登入查詢')
        return ''.join(lines)

    return None


def send_line_push(text):
    try:
        resp = requests.post(
            'https://api.line.me/v2/bot/message/push',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
            },
            json={
                'to': LINE_PUSH_USER_ID,
                'messages': [{'type': 'text', 'text': text}]
            },
            timeout=10
        )
        print(f"Push sent: {resp.status_code}", flush=True)
    except Exception as e:
        print(f"Push error: {e}", flush=True)


def send_daily_reminder():
    print("Running daily reminder...", flush=True)
    msg = build_reminder_message()
    if msg:
        send_line_push(msg)
        print("Daily reminder sent.", flush=True)
    else:
        print("No reminder for tomorrow.", flush=True)


# Start scheduler — fires every day at 19:50 Taiwan time
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Taipei'))
scheduler.add_job(send_daily_reminder, 'cron', hour=19, minute=50)
scheduler.start()


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
    taipei = pytz.timezone('Asia/Taipei')
    today = datetime.now(taipei).strftime('%Y年%m月%d日（%A）')
    system_with_date = SYSTEM_PROMPT + f"\n\n今天台北時間是：{today}"
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=500,
        system=system_with_date,
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
