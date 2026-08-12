import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = 'https://open.neis.go.kr/hub'
SCHOOL_NAME = os.getenv('SCHOOL_NAME', '양천고등학교')
API_KEY = os.getenv('NEIS_API_KEY', '').strip()
OUT = Path(__file__).resolve().parents[1] / 'data' / 'meals.json'


def fetch_json(endpoint, params):
    params = dict(params)
    params.update({'Type': 'json', 'pIndex': '1', 'pSize': params.get('pSize', '100')})
    if API_KEY:
        params['KEY'] = API_KEY
    url = f"{BASE}/{endpoint}?{urlencode(params)}"
    req = Request(url, headers={'User-Agent': 'glucose-health-project/1.0'})
    with urlopen(req, timeout=20) as r:
        raw = r.read().decode('utf-8')
    return json.loads(raw)


def rows_from(payload, name):
    if isinstance(payload, dict) and payload.get('RESULT'):
        raise RuntimeError(payload['RESULT'].get('MESSAGE', 'NEIS API error'))
    block = payload.get(name) if isinstance(payload, dict) else None
    if not isinstance(block, list):
        raise RuntimeError(f'{name} 응답 형식을 해석하지 못했습니다.')
    for part in block:
        if isinstance(part, dict) and isinstance(part.get('row'), list):
            return part['row']
    for part in block:
        head = part.get('head') if isinstance(part, dict) else None
        if isinstance(head, list):
            for item in head:
                result = item.get('RESULT') if isinstance(item, dict) else None
                if result:
                    raise RuntimeError(result.get('MESSAGE', '조회 결과 없음'))
    return []


def strip_br(s):
    return re.sub(r'<br\s*/?>', '\n', str(s or ''), flags=re.I).replace('&nbsp;', ' ').strip()


def number_from(pattern, text):
    m = re.search(pattern, str(text or ''), flags=re.I)
    return float(m.group(1)) if m else None


def parse_nutrition(text):
    return {
        'carb': number_from(r'탄수화물\s*\(g\)\s*[:：]\s*([0-9.]+)', text),
        'protein': number_from(r'단백질\s*\(g\)\s*[:：]\s*([0-9.]+)', text),
        'fat': number_from(r'지방\s*\(g\)\s*[:：]\s*([0-9.]+)', text),
    }


def parse_kcal(text):
    return number_from(r'([0-9.]+)\s*Kcal', text)


def ymd(d):
    return d.strftime('%Y%m%d')


def iso_ymd(s):
    return f'{s[:4]}-{s[4:6]}-{s[6:8]}' if len(s) == 8 else s


def load_existing():
    try:
        return json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        return {'school': SCHOOL_NAME, 'updated_at': '', 'meals': {}}


def save(data):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def get_school():
    payload = fetch_json('schoolInfo', {'SCHUL_NM': SCHOOL_NAME, 'pSize': '100'})
    rows = rows_from(payload, 'schoolInfo')
    exact = next((r for r in rows if r.get('SCHUL_NM') == SCHOOL_NAME), None)
    if exact is None:
        exact = next((r for r in rows if SCHOOL_NAME in str(r.get('SCHUL_NM', ''))), None)
    if exact is None:
        raise RuntimeError(f'{SCHOOL_NAME} 학교코드를 찾지 못했습니다.')
    return exact


def normalize_meal(r):
    n = parse_nutrition(r.get('NTR_INFO', ''))
    return {
        'date': iso_ymd(str(r.get('MLSV_YMD', ''))),
        'mealType': r.get('MMEAL_SC_NM', ''),
        'menu': strip_br(r.get('DDISH_NM', '')),
        'kcal': parse_kcal(r.get('CAL_INFO', '')),
        'carb': n['carb'],
        'protein': n['protein'],
        'fat': n['fat'],
        'nutritionRaw': strip_br(r.get('NTR_INFO', '')),
        'source': 'NEIS 급식식단정보'
    }


def fetch_range_with_key(school, start, end):
    payload = fetch_json('mealServiceDietInfo', {
        'ATPT_OFCDC_SC_CODE': school['ATPT_OFCDC_SC_CODE'],
        'SD_SCHUL_CODE': school['SD_SCHUL_CODE'],
        'MMEAL_SC_CODE': '2',
        'MLSV_FROM_YMD': ymd(start),
        'MLSV_TO_YMD': ymd(end),
        'pSize': '1000'
    })
    return rows_from(payload, 'mealServiceDietInfo')


def fetch_days_without_key(school, start, end):
    rows = []
    d = start
    while d <= end:
        try:
            payload = fetch_json('mealServiceDietInfo', {
                'ATPT_OFCDC_SC_CODE': school['ATPT_OFCDC_SC_CODE'],
                'SD_SCHUL_CODE': school['SD_SCHUL_CODE'],
                'MMEAL_SC_CODE': '2',
                'MLSV_YMD': ymd(d),
                'pSize': '5'
            })
            rows.extend(rows_from(payload, 'mealServiceDietInfo'))
        except Exception as e:
            # 급식이 없는 날의 INFO-200은 정상적인 상황으로 간주
            if '해당하는 데이터가 없습니다' not in str(e) and 'INFO-200' not in str(e):
                print(f'WARN {d}: {e}', file=sys.stderr)
        d += timedelta(days=1)
        time.sleep(0.05)
    return rows


def main():
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    start = (now - timedelta(days=14)).date()
    end = (now + timedelta(days=60)).date()
    existing = load_existing()
    school = get_school()

    if API_KEY:
        rows = fetch_range_with_key(school, start, end)
        mode = 'authenticated-open-api'
    else:
        # 인증키가 없어도 포털의 sample/default 접근이 허용되는 경우를 위한 폴백.
        # 안정적인 운영에는 GitHub Secret NEIS_API_KEY 설정을 권장한다.
        rows = fetch_days_without_key(school, start, end)
        mode = 'sample-open-api'

    meals = existing.get('meals', {}) if isinstance(existing.get('meals'), dict) else {}
    # 이번 조회 범위의 기존 값은 지운 뒤 최신 자료로 교체
    d = start
    while d <= end:
        meals.pop(d.isoformat(), None)
        d += timedelta(days=1)

    for r in rows:
        if r.get('MMEAL_SC_NM') not in ('중식', None, ''):
            continue
        item = normalize_meal(r)
        if item['date']:
            meals[item['date']] = item

    data = {
        'school': school.get('SCHUL_NM', SCHOOL_NAME),
        'schoolCode': school.get('SD_SCHUL_CODE', ''),
        'officeCode': school.get('ATPT_OFCDC_SC_CODE', ''),
        'updated_at': now.isoformat(timespec='seconds'),
        'mode': mode,
        'range': {'from': start.isoformat(), 'to': end.isoformat()},
        'meals': dict(sorted(meals.items()))
    }
    save(data)
    print(f"Saved {len(rows)} rows / {len(data['meals'])} meal dates to {OUT}")


if __name__ == '__main__':
    main()
