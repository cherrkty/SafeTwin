import requests, json, datetime, os, time, sys


KST = datetime.timezone(datetime.timedelta(hours=9))

def now_kst():
    return datetime.datetime.now(KST)


SERVICE_KEY = os.environ.get("SERVICE_KEY", "")
OUTPUT = r"G:\내 드라이브\수방프로젝트\weather_gangnam.json"
NX, NY = 62, 126


FIREBASE_DB_URL   = "https://gangnam-subang-default-rtdb.asia-southeast1.firebasedatabase.app"
FIREBASE_PATH     = "weather_gangnam"
FIREBASE_KEY_FILE = "firebase-key.json"


def get_realtime_base_datetime():
    now = now_kst()
    if now.minute < 40:
        now -= datetime.timedelta(hours=1)
    return now.strftime("%Y%m%d"), now.strftime("%H00")

def get_forecast_base_datetime():
    now = now_kst()
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


def fetch_with_retry(url, label, max_retries=5, retry_delay=10):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, timeout=(15, 20))
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

    today_str = now_kst().strftime("%Y%m%d")
    current_hour = now_kst().hour

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
        "timestamp": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
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


def upload_to_firebase(data):
    if not os.path.exists(FIREBASE_KEY_FILE):
        print(f"Firebase 서비스 계정 키 파일 없음({FIREBASE_KEY_FILE}) — 업로드 건너뜀 (로컬 테스트 환경으로 판단)")
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, db

        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY_FILE)
            firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

        ref = db.reference(FIREBASE_PATH)
        ref.set(data)
        print("Firebase 업로드 완료 (서비스 계정 인증)")
    except Exception as fe:
        print("Firebase 업로드 실패:", fe)
       
        raise

try:
    w = fetch_weather()
    print("날씨 수집 완료:", w)

   
    try:
        out_dir = os.path.dirname(OUTPUT)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(w, f, ensure_ascii=False, indent=2)
            print("로컬 파일 저장 완료:", OUTPUT)
        else:
            print("로컬 저장 경로 사용 불가(예: GitHub Actions 환경) — 건너뜀")
    except Exception as le:
        print("로컬 파일 저장 실패(무시하고 계속 진행):", le)

    
    upload_to_firebase(w)

except Exception as e:
    print("오류:", e)
   
    sys.exit(1)
