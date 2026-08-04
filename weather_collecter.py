import requests, json, datetime, os, time

# ===== 수정 =====
SERVICE_KEY = "5bd3ec725b6f3296044a5b57defb49b921430b38d68d1607e6703643bb66a65f"
OUTPUT = r"G:\내 드라이브\수방프로젝트\weather_gangnam.json"
NX, NY = 62, 126

FIREBASE_URL = "https://gangnam-subang-default-rtdb.asia-southeast1.firebasedatabase.app/weather_gangnam.json"
# ================

def get_realtime_base_datetime():
    now = datetime.datetime.now()
    if now.minute < 40:
        now -= datetime.timedelta(hours=1)
    return now.strftime("%Y%m%d"), now.strftime("%H00")

def get_forecast_base_datetime():
    now = datetime.datetime.now()
    base_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    base_hour = None
    for h in reversed(base_hours):
        if now.hour > h or (now.hour == h and now.minute >= 10):
            base_hour = h
            break
    if base_hour is None:
        now -= datetime.timedelta(days=1)
        base_hour = 23
    return now.strftime("%Y%m%d"), f"{base_hour:02d}00"

def safe_float(v, default=0.0):
    try:    return float(v)
    except: return default

# ★ 추가 — 타임아웃/연결 오류 시 재시도하는 공용 GET 헬퍼
#   - 최대 3회 시도, 실패 시 3초 대기 후 재시도
#   - connect timeout 5초 / read timeout 15초 (기존 10초 단일값보다 여유 있게)
def fetch_with_retry(url, label, max_retries=3, retry_delay=3):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, timeout=(5, 15))
            print(f"[{label}] 상태코드:", r.status_code, f"(시도 {attempt}/{max_retries})")
            return r
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"[{label}] 요청 실패 (시도 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    raise last_error

def fetch_realtime():
    base_date, base_time = get_realtime_base_datetime()
    url = ("https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
           f"?serviceKey={SERVICE_KEY}&numOfRows=60&pageNo=1&dataType=JSON"
           f"&base_date={base_date}&base_time={base_time}&nx={NX}&ny={NY}")
    r = fetch_with_retry(url, "실황")
    items = r.json()["response"]["body"]["items"]["item"]
    return {it["category"]: it["obsrValue"] for it in items}, base_date, base_time

def fetch_forecast():
    """단기예보 한 번 호출로 POP(강수확률)와 SKY(하늘상태) 둘 다 추출"""
    base_date, base_time = get_forecast_base_datetime()
    url = ("https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
           f"?serviceKey={SERVICE_KEY}&numOfRows=1000&pageNo=1&dataType=JSON"
           f"&base_date={base_date}&base_time={base_time}&nx={NX}&ny={NY}")
    r = fetch_with_retry(url, "예보")
    items = r.json()["response"]["body"]["items"]["item"]

    today_str = datetime.datetime.now().strftime("%Y%m%d")
    current_hour = datetime.datetime.now().hour

    morning_pop, afternoon_pop = 0.0, 0.0
    sky_value, sky_diff = None, 9999

    for it in items:
        if it["fcstDate"] != today_str: continue
        try:
            fcst_hour = int(it["fcstTime"][:2])
        except:
            continue

        if it["category"] == "POP":
            try: value = float(it["fcstValue"])
            except: continue
            if fcst_hour < 12: morning_pop = max(morning_pop, value)
            else:              afternoon_pop = max(afternoon_pop, value)

        elif it["category"] == "SKY":
            try: value = int(it["fcstValue"])
            except: continue
            diff = abs(fcst_hour - current_hour)
            if diff < sky_diff:
                sky_diff = diff
                sky_value = value

    sky_map = {1: "맑음", 3: "구름많음", 4: "흐림"}
    sky_text = sky_map.get(sky_value, "맑음")

    return morning_pop, afternoon_pop, sky_text

def fetch_weather():
    result, base_date, base_time = fetch_realtime()

    temp = safe_float(result.get("T1H"), 0.0)
    rain = safe_float(result.get("RN1"), 0.0)
    pty  = result.get("PTY", "0")
    reh  = safe_float(result.get("REH"), 0.0)
    wsd  = safe_float(result.get("WSD"), 0.0)
    vec  = safe_float(result.get("VEC"), 0.0)

    pty_map = {"0":"없음","1":"비","2":"비/눈","3":"눈","5":"빗방울","6":"빗방울/눈날림","7":"눈날림"}
    precipitation = pty_map.get(str(pty), "없음")

    try:
        morning_pop, afternoon_pop, sky_text = fetch_forecast()
    except Exception as e:
        print(f"단기예보 조회 실패: {e}")
        morning_pop, afternoon_pop, sky_text = 0.0, 0.0, "맑음"

    out = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": temp,
        "rainfall": rain,
        "precipitation": precipitation,
        "sky": sky_text,   # 이제 진짜 SKY 값 (맑음/구름많음/흐림)
        "humidity": reh,
        "pop_morning": morning_pop,
        "pop_afternoon": afternoon_pop,
        "wind_speed": wsd,
        "wind_direction": vec,
        "base": f"{base_date} {base_time}"
    }
    return out

try:
    w = fetch_weather()
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(w, f, ensure_ascii=False, indent=2)
    print("날씨 수집 완료:", w)

 # ★ 추가 — Firebase에도 업로드
    try:
        requests.put(FIREBASE_URL, json=w)
        print("Firebase 업로드 완료")
    except Exception as fe:
        print("Firebase 업로드 실패:", fe)


except Exception as e:
    print("오류:", e)
