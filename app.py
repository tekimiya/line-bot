import os
import re
import hmac
import hashlib
import base64
import json
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask, request, abort
import requests
import anthropic
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flash(__name__)

LINE_CHANNEL_SECRET = os.environ['LINE_CHANNEL_SECRET']
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
LINE_PUSH_USER_ID = 'U43f403149806d8e5def5b42cca840dd6'

EVA_BASE = 'https://www.evaangel.com'
EVA_API = EVA_BASE + '/cabinwsv/api/Schedule/'
EVA_USER = 'f59113'
EVA_PASSWORD = os.environ.get('EVA_PASSWORD', '')

SCHEDULE = """
4æç­è¡¨ï¼
04/01 ä¼å | 04/02 é£è¡ BR192 TSAï¼æ¾å±±ï¼âHNDï¼æ±äº¬ç¾½ç°ï¼07:19èµ·é£/BR191 HNDâTSA 12:41èµ·é£ å ±å°05:50
04/03 ççå | 04/04 çå
04/05 é£è¡ BR281 TPEï¼æ¡åï¼âCEBï¼å®¿é§ï¼08:02/BR282 CEBâTPE 12:18 å ±å°06:00
04/06 é£è¡ BR805 TPEâMFMï¼æ¾³éï¼16:37/BR806 MFMâTPE 20:16 å ±å°14:40
04/07 ä¼å(ADO) | 04/08 ä¼å | 04/09 ä¼å(ADO)
04/10 ç¹æ®å(YH) | 04/11 ç¹æ®å(YI)
04/12 é£è¡ BR192 TSAâHND 07:21/BR191 HNDâTSA 12:37 å ±å°05:50
04/13 é£è¡ BR772 TSAâSHAï¼ä¸æµ·è¹æ©ï¼14:53/BR771 SHAâTSA 19:37 å ±å°13:25
04/14 ä¼å | 04/15 ä¼å
04/16 é£è¡(ééæ¢­) B78801 TSAâKNHï¼ééï¼âTSAâKNHâTSA å ±å°06:00
04/17 é£è¡ BR192 TSAâHND 07:28/BR191 HNDâTSA 12:43 å ±å°05:50
04/18 ä¼å(ADO) | 04/19 å®¶åº­ç§é¡§å
04/20 é£è¡ BR118 TPEâSDJï¼ä»å°ï¼10:12 å ±å°08:05
04/21 é£è¡ BR117 SDJâTPE 16:14 å ±å°07:39
04/22 é£è¡ BR772 TSAâSHA 15:05/BR771 SHAâTSA 19:31 å ±å°13:25
04/23 ä¼å(ADO) | 04/24 ç¹æ®
04/25 é£è¡ BR772 TSAâSHA 15:11/BR771 SHAâTSA 19:27 å ±å°13:25
04/26 ä¼å
04/27 é£è¡(é¦¬å¬æ¢­) B78607 TSAâMZGï¼é¦¬å¬ï¼âTSAâMZGâTSA å ±å°07:20
04/28 å¾å½(Q05) | 04/29 é£è¡ BR190 TSAâHND 16:20 å ±å°14:50
04/30 é£è¡(çº) BR189 HNDï¼æ±äº¬ç¾½ç°ï¼âTSA 10:50

5æç­è¡¨ï¼
05/01 ä¼å
05/02 é£è¡(ééæ¢­) B78801 TSAâKNHâTSAâKNHâTS@ å ±å°06:00
05/03 é£è¡(ééæ¢­) åä¸ å ±å°06:00
05/04 å¾å½(Q12) | 05/05 ä¼å(ADO) | 05/06 ä¼å
05/07 é£è¡ BR772 TSAâSHA 14:55/BR771 SHAâTSA 19:40 å ±å°13:25
05/08 é£è¡(å»é) B7511 TSAâXMNï¼å»éï¼17:00/B7512 XMNâTSA 19:40 å ±å°15:30
05/09 é£è¡ BR772 TSAâSHA 14:55/BR771 SHAâTSA 19:40 å ±å°13:25
05/10 ç¹æ®å(YJ)
05/11 é£è¡(é¦¬å¬æ¢­) B78601 TSAâMZGâTSAâMZGâTSA å ±å°06:15
05/12 ä¼å(ADO) | 05/13 ä¼å
05/14 é£è¡(é¦¬å¬æ¢­) B78601 TSAâMZGâTSAâMZGâTSA å ±å°06:15
05/15 é£è¡(å»é) B7511 TSAâXMN 17:00/B7512 XMNâTSA 19:40 å ±å°15:30
05/16 é£è¡ BR772 TSAâSHA 14:55/BR771 SHAâTSA 19:40 å ±å°13:25
05/17 é£è¡(å·´é») BR87 TPEâCDGï¼å·´é»æ´é«æ¨ï¼23:30 å ±å°21:30
05/18 é£è¡ä¸­(BR87åå¾å·´é») | 05/19 Layoverå¨å·´é»(CDG)
05/20 é£è¡ BR88 CDGâTPE 11:20 | 05/21 é£è¡ä¸­(BR88è¿å°)
05/22 ä¼å(ADO) | 05/23 ä¼å | 05/24 ä¼å | 05/25 ä¼å
05/26 ä¼å(ADO)
05/27 é£è¡ BR192 TSAâHND 07:20/BR191 HNDâTSA 12:40 å ±å°05:50
05/28 ä¼å
05/29 é£è¡ BR190 TSAâHND 16:20 å ±å°14:50
05/30 é£è¡(çº) BR189 HNDâTSA 10:50
05/31 é£è¡ BR192 TSAâHND 07:20 å ±å°05:50
"""

SYSTEM_PROMPT = f"""ä½ æ¯æç®ççé·æ¦®èªç©ºç­è¡¨å©çãå¥¹æ¯é·æ¦®èªç©ºç©ºæå¡ï¼å¡å·¥ç·¨è F59113ï¼ã

è«ç¨ç¹é«ä¸­æåç­ï¼èªæ°£èªç¶åæåèå¤©ï¼ç°¡æ½ä¸åå¦ã

å¥¹ç 4-5 æç­è¡¨ï¼
{SCHEDULE}

ç­è¡¨ä»£ç¢¼èªªæï¼
- DO / ADOï¼ä¼å
- Yéé ­+å­æ¯ï¼YJ/YH/YIï¼ãFLãSLãMENãALï¼åç¨®åå¥
- å¾å½ç­ï¼å­æ¯+æ¸å­ï¼å¦ Q05ãQ12ãJ13ï¼ï¼å¾å½ï¼å±3å°æï¼å¬å¸å¯è½è¨ææé£
- LOï¼Layoverï¼å¤ç«éå¤ï¼
- é£è¡ä¸­ï¼é·ç¨èªç­éä¸­

åèªç­é£è¡ææ¸ï¼æ ¼å¼ æ:åï¼ï¼
BR192 TSAâHND: 03:10
BR191 HNDâTSA: 03:25
BR190 TSAâHND: 03:00
BR189 HNDâTSA: 03:40
BR118 TPEâSDJ: 03:30
BR117 SDJâTPE: 03:50
BR281 TPEâCEB: 02:50
BR282 CEBâTPE: 02:55
BR805 TPEâMFM: 01:55
BR806 MFMâTPE: 01:55
BR772 TSAâSHA: 01:35
BR771 SHAâTSA: 02:05
B7511 TSAâXMN: 01:40
B7512 XMNâTSA: 01:45
BR87 TPEâCDG: 14:55
BR88 CDGâTPE: 13:25
B78801 TSAâKNH: 01:05
B78802 KNHâTSA: 01:00
B78811 TSAâKNH: 01:05
B78812 KNHâTSA: 01:00
B78607/B78609/B78601 TSAâMZG: 00:50
B78608/B78610/B78602/B78616 MZGâTSA: 00:50

åç­ååï¼
- åªåç­ç­è¡¨ç¸éåé¡
- å¦æåä»å¤©/æå¤©ï¼è«æ ¹æå°åæéå¤æ·æ¥æ
- ä¸ç¥éçè³è¨ï¼å¦çµå¡åå®ï¼å°±èªªéè¦ç»å¥æ¥è©¢
- éå°ä¸ç¸éçåé¡ï¼èªªä½ åªè² è²¬ç­è¡¨äºå®"""

AIRPORTS = {
    'TSA': 'æ¾å±±', 'TPE': 'æ¡å', 'HND': 'æ±äº¬ç¾½ç°', 'NRT': 'æ±äº¬æç°',
    'SHA': 'ä¸æµ·è¹æ©', 'PVG': 'ä¸æµ·æµ¦æ±', 'XMN': 'å»é', 'MZG': 'é¦¬å¬',
    'KNH': 'éé', 'CDG': 'å·´é»æ´é«æ¨', 'MFM': 'æ¾³é', 'CEB': 'å®¿é§',
    'SDJ': 'ä»å°', 'HKG': 'é¦æ¸¯', 'BKK': 'æ¼è°·', 'SIN': 'æ°å å¡',
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
        ('B78601', 'TSA', 'MZG', '07:15', '08:05'),
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

WEEKDAY_MAP = {0: 'é±ä¸', 1: 'é±äº', 2: 'é±ä¸', 3: 'é±å', 4: 'é±äº', 5: 'é±å­', 6: 'é±æ¥'}


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
        return f'ð´ æå¤© {month_day}ï¼{weekday}ï¼ä¼å\nå¥½å¥½æ¾é¬åé»ï¼'

    if dtype == 'standby':
        return f'â° æå¤© {month_day}ï¼{weekday}ï¼å¾å½ï¼{day["code"]}ï¼\nä¿æææ©æ¢éï¼'

    if dtype in ('fly', 'fly_cont'):
        lines = [f'âï¸ æå¤© {month_day}ï¼{weekday}ï¼ç­è¡¨æé']
        if dtype == 'fly' and day.get('checkin'):
            lines.append(f'\nå ±å°ï¼{day["checkin"]}')
        for flt, dep, arr, dep_t, arr_t in day['flights']:
            dep_cn = AIRPORTS.get(dep, dep)
            arr_cn = AIRPORTS.get(arr, arr)
            lines.append(f'\n{dep_cn} â {arr_cn}  {flt}\nèµ·é£ï¼{dep_t}ãè½å°ï¼{arr_t}')
        lines.append('\nð¥ çµå¡åå®éç»å¥æ¥è©¢')
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


# Start scheduler â fires every day at 19:50 Taiwan time
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Taipei'))
scheduler.add_job(send_daily_reminder, 'cron', hour=19, minute=50)
scheduler.start()


# ââ EVA crew list functions ââââââââââââââââââââââââââââââââââââââââââââââââââââ

def solve_captcha(img_bytes):
    b64 = base64.b64encode(img_bytes).decode()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=20,
        messages=[{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/gif', 'data': b64}},
            {'type': 'text', 'text': (
                'éæ¯ä¸å¼µç¶²ç«é©è­ç¢¼ï¼CAPTCHAï¼åçã'
                'åçä¸­æ 5 åæ¸å­ï¼0-9ï¼ï¼è«å¾å·¦å°å³ä»ç´°è¾¨è­æ¯ä¸åæ¸å­ã'
                'åªè¼¸åºé 5 åæ¸å­ï¼ä¸è¦ç©ºæ ¼ãä¸è¦æ¨é»ãä¸è¦ä»»ä½èªªææå­ã'
            )}
        ]}]
    )
    return resp.content[0].text.strip().replace(' ', '')


def eva_login():
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    try:
        r = session.get(EVA_BASE + '/WAL/AntiRobot.aspx', timeout=15)
        vs = re.search(r'id="__VIEWSTATE"\s+value="([^"]*)"', r.text)
        vsg = re.search(r'id="__VIEWSTATEGENERATOR"\s+value="([^"]*)"', r.text)
        if not (vs and vsg):
            print('EVA login: VIEWSTATE not found', flush=True)
            return None, None
        import time
        cap_url = EVA_BASE + f'/Common/ValidateCode.ashx?t={time.time()}'
        cap_img = session.get(cap_url, timeout=10)
        cap_answer = solve_captcha(cap_img.content)
        print(f'CAPTCHA answer: {cap_answer}', flush=True)
        login_r = session.post(EVA_BASE + '/WAL/AntiRobot.aspx', data={
            '__VIEWSTATE': vs.group(1),
            '__VIEWSTATEGENERATOR': vsg.group(1),
            'ID': EVA_USER,
            'PWD': EVA_PASSWORD,
            'txtValidCode': cap_answer,
        }, timeout=15, allow_redirects=True)
        if 'AntiRobot' in login_r.url:
            print(f'EVA login failed: redirected to {login_r.url}', flush=True)
            return None, None
        js_r = session.get(EVA_BASE + '/Common/js_Initial.ashx', timeout=10)
        token_m = re.search(r"UserToken\s*=\s*'([^']+)'", js_r.text)
        token = token_m.group(1) if token_m else ''
        print(f'EVA login OK, token: {token[:8]}...', flush=True)
        return session, token
    except Exception as e:
        print(f'EVA login error: {e}', flush=True)
        return None, None


def fetch_crew_json(session, token, airline, flight_num, flight_date, end_airport):
    headers = {
        'x-cookie-prefix-header': 'Cabin_',
        'x-user-company-header': 'EVA',
        'x-user-token-header': token,
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': EVA_BASE + '/Entry/Duty/FlightDutyMayfly/FlightKey.aspx',
    }
    try:
        url = (f"{EVA_API}Get_MayflyList"
               f"?parm_FlightStartDate={flight_date}"
               f"&AirlineCode={airline}&FlightNumber={flight_num}"
               f"&EndAirport={end_airport}&parm_Qual=*&ADMIN_TYPE=O")
        r = session.get(url, headers=headers, timeout=15)
        print(f'Crew API status: {r.status_code}', flush=True)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f'Crew API error: {e}', flush=True)
    return None


def format_crew_message(crew_list, flight_label, date_str):
    if not crew_list:
        return None
    date_display = date_str[5:] if len(date_str) >= 10 else date_str
    lines = [f'âï¸ {flight_label} | {date_display} çµå¡åå®\n']
    for c in crew_list:
        emp_id = c.get('ID', '')
        name = c.get('CNAME', '')
        ename = c.get('ENAME', '')
        nick_m = re.search(r'\(([^)]+)\)', ename)
        nick = nick_m.group(1) if nick_m else ''
        pos = c.get('POS', '')
        alloc = c.get('allocation', '')
        me = '  â å¦³' if emp_id == 'F59113' else ''
        name_str = f'{name}ï¼{nick}ï¼' if nick else name
        lines.append(f'{pos}  {name_str}  {alloc}{me}')
    return '\n'.join(lines)


def get_crew_query_params(user_msg):
    """Parse 'æ¥åå® [BR772] [05/07]' and return (flight_code, date_str, end_airport)."""
    tpe = pytz.timezone('Asia/Taipei')
    tomorrow = datetime.now(tpe) + timedelta(days=1)

    flight_m = re.search(r'\b(BR\d+|B7\d+)\b', user_msg.upper())
    date_m = re.search(r'(\d{1,2})[/](\d{2})', user_msg)

    if date_m:
        month_day = f'{date_m.group(1).zfill(2)}/{date_m.group(2)}'
        date_str = f'2026/{month_day}'
    else:
        month_day = tomorrow.strftime('%m/%d')
        date_str = '2026/' + month_day

    day_info = DAILY_SCHEDULE.get(month_day)
    if not day_info or day_info.get('type') not in ('fly', 'fly_cont'):
        return None, None, None
    flights = day_info.get('flights', [])
    if not flights:
        return None, None, None

    if flight_m:
        code = flight_m.group(1)
        for flt in flights:
            if flt[0].upper() == code:
                return code, date_str, flt[2]
        return code, date_str, flights[0][2]
    else:
        flt = flights[0]
        return flt[0], date_str, flt[2]


def query_and_push_crew(flight_code, date_str, end_airport):
    if flight_code.startswith('BR'):
        airline, num = 'BR', flight_code[2:]
    else:
        airline, num = 'B7', flight_code[2:]

    session, token = None, None
    for attempt in range(3):
        session, token = eva_login()
        if session:
            break
        print(f'Login attempt {attempt + 1} failed', flush=True)

    if not session:
        send_line_push('â ç»å¥é·æ¦®ç¶²ç«å¤±æï¼é©è­ç¢¼è¾¨è­é¯èª¤ï¼ï¼è«ç¨å¾åè©¦')
        return

    crew = fetch_crew_json(session, token, airline, num, date_str, end_airport)
    if crew is None:
        send_line_push('â æ¥è©¢ API å¤±æï¼è«ç¨å¾åè©¦')
    elif len(crew) == 0:
        send_line_push(f'â {flight_code} å¨ {date_str[5:]} å°ç¡çµå¡è³æ')
    else:
        msg = format_crew_message(crew, f'{airline}{num}', date_str)
        if msg:
            send_line_push(msg)


# ââ end EVA crew list functions ââââââââââââââââââââââââââââââââââââââââââââââââ


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
    today = datetime.now(taipei).strftime('%Yå¹´%mæ%dæ¥ï¼%Aï¼')
    system_with_date = SYSTEM_PROMPT + f"\n\nä»å¤©å°åæéæ¯ï¼{today}"
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

                if 'æ¥åå®' in user_message:
                    flight_code, date_str, end_airport = get_crew_query_params(user_message)
                    if flight_code:
                        reply_to_line(reply_token, f'ð æ¥è©¢ {flight_code} {date_str[5:]} çµå¡åå®ï¼è«ç¨ç­...')
                        t = threading.Thread(target=query_and_push_crew, args=(flight_code, date_str, end_airport))
                        t.daemon = True
                        t.start()
                    else:
                        reply_to_line(reply_token, 'æ¾ä¸å°å°æç­æ¬¡ï¼è«æå®ä¾å¦ï¼\næ¥åå® BR772\næ¥åå® B78607 04/27')
                else:
                    try:
                        response_text = ask_claude(user_message)
                        reply_to_line(reply_token, response_text)
                    except Exception as e:
                        print(f"ERROR: {e}", flush=True)
                        reply_to_line(reply_token, 'æ±æ­ï¼æç¾å¨æé»å¿ï¼è«ç¨å¾ååæ ð')

    return 'OK'


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
