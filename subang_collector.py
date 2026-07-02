import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
# ★ 추가
import firebase_admin
from firebase_admin import credentials, db

# ★ 스크립트 맨 위, 최초 1회만 초기화
FIREBASE_KEY_PATH = "firebase-key.json"
FIREBASE_DB_URL = "https://gangnam-subang-default-rtdb.asia-southeast1.firebasedatabase.app"

if not firebase_admin._apps:  # 중복 초기화 방지
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})



HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

FIREBASE_URL = "https://gangnam-subang-default-rtdb.asia-southeast1.firebasedatabase.app/gangnam_subang_data.json"

# -------------------------------------------------------
# 좌표 딕셔너리
# -------------------------------------------------------
RAINFALL_COORDS = {
    "강남구청":   [37.5172, 127.0473],
    "개포2동":   [37.4812, 127.0571],
    "세곡동":    [37.4645, 127.0931],
    "논현1동":   [37.5112, 127.0287],
    "대치펌프장": [37.4955, 127.0623],
    "역삼1동":   [37.5007, 127.0368],
    "대치4동":   [37.4902, 127.0671],
    "일원본동":  [37.4773, 127.0831],
    "수서펌프장": [37.4848, 127.1003],
    "삼성1동":   [37.5085, 127.0603],
    "압구정동":  [37.5271, 127.0285],
    "청담동":    [37.5231, 127.0531],
    "도곡2동":   [37.4912, 127.0503],
    "율현펌프장": [37.4601, 127.0871],
    "대치1펌프장":[37.4971, 127.0651],
}

WATERLEVEL_COORDS = {
    "신사573-1":   [37.5253, 127.0201],
    "신사548-1":   [37.5248, 127.0198],
    "대치599":     [37.4947, 127.0619],
    "대치316":     [37.4923, 127.0578],
    "삼성172-104": [37.5091, 127.0548],
    "역삼833-4":   [37.5003, 127.0401],
    "신사638-1":   [37.5261, 127.0213],
    "신사660-1":   [37.5267, 127.0231],
    "신사648-8":   [37.5258, 127.0219],
    "청담105-6":   [37.5238, 127.0541],
    "청담48-3":    [37.5229, 127.0519],
    "청담34-7":    [37.5221, 127.0511],
    "청담44-14":   [37.5233, 127.0527],
    "일원641-1":   [37.4781, 127.0839],
    "일원642-14":  [37.4785, 127.0843],
    "역삼820-5":   [37.5011, 127.0389],
    "일원738-1":   [37.4791, 127.0851],
    "일원735":     [37.4788, 127.0848],
    "수서714":     [37.4851, 127.1007],
    "논현143-14":  [37.5098, 127.0279],
    "수서501-6":   [37.4841, 127.0991],
}

PUMPSTATION_COORDS = {
    "대치펌프장":    [37.4955, 127.0623],
    "대치1펌프장":   [37.4971, 127.0651],
    "수서펌프장":    [37.4848, 127.1003],
    "율현펌프장":    [37.4601, 127.0871],
    "수서간이펌프장": [37.4839, 127.0989],
    "대왕간이펌프장": [37.4571, 127.0901],
    "아랫반간이펌프장":[37.4589, 127.0881],
    "세곡간이펌프장": [37.4631, 127.0911],
}

SLUICEGATE_COORDS = {
    "강남나들목":  [37.5231, 127.0089],
    "신사나들목":  [37.5251, 127.0121],
    "신청담나들목": [37.5261, 127.0311],
}

RIVERLEVEL_COORDS = {
    "잠수교":  [37.5131, 126.9971],
    "청담대교": [37.5271, 127.0531],
    "턴천2교": [37.4941, 127.0831],
    "대치교":  [37.4951, 127.0631],
    "대곡교":  [37.4631, 127.0911],
    "세곡천":  [37.4641, 127.0921],
    "여수대교": [37.4611, 127.1071],
}

# 주소 캐시 (한번 받아온 주소는 재사용)
ADDRESS_CACHE = {}

def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.encoding = 'utf-8'
    return BeautifulSoup(response.text, 'html.parser')

def to_float(val):
    try:
        return float(str(val).replace('m','').strip())
    except:
        return 0.0

def to_int(val):
    try:
        return int(str(val).strip())
    except:
        return 0

# -------------------------------------------------------
# 데이터 수집 함수들
# -------------------------------------------------------
def collect_rainfall():
    soup = get_soup("https://subang.gangnam.go.kr/rainfall/viewRainfall.do")
    result = []
    known_locations = [
        "강남구청","개포2동","세곡동","논현1동","대치펌프장",
        "역삼1동","대치4동","일원본동","수서펌프장","삼성1동",
        "압구정동","청담동","도곡2동","율현펌프장","대치1펌프장"
    ]
    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        if line in known_locations:
            entry = {"location": line}
            keys = ["금일우량","시간우량","시간최대","누계우량"]
            vals = []
            for j in range(i+1, min(i+20, len(lines))):
                try:
                    float(lines[j])
                    vals.append(lines[j])
                except:
                    pass
                if len(vals) >= 4:
                    break
            for k, key in enumerate(keys):
                entry[key] = vals[k] if k < len(vals) else "0"
            result.append(entry)
    return result

def collect_waterlevel():
    soup = get_soup("https://subang.gangnam.go.kr/waterlevel/viewWaterLevel.do")
    result = []
    known_locations = [
        '신사573-1','신사548-1','대치599','대치316','삼성172-104',
        '역삼833-4','신사638-1','신사660-1','신사648-8','청담105-6',
        '청담48-3','청담34-7','청담44-14','일원641-1','일원642-14',
        '역삼820-5','일원738-1','일원735','수서714','논현143-14','수서501-6'
    ]
    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        if line in known_locations:
            vals = []
            for j in range(i+1, min(i+6, len(lines))):
                try:
                    v = float(lines[j].replace('m','').strip())
                    vals.append(v)
                except:
                    pass
                if len(vals) >= 2:
                    break
            if len(vals) >= 2:
                cur_f, dia_f = vals[0], vals[1]
                ratio = round(cur_f / dia_f * 100, 1) if dia_f > 0 else 0
                result.append({"location": line, "current_level": str(cur_f), "pipe_diameter": str(dia_f), "fill_ratio_pct": ratio})
            elif len(vals) == 1:
                result.append({"location": line, "current_level": str(vals[0]), "pipe_diameter": "unknown", "fill_ratio_pct": 0})
    return result

def collect_pumpstation():
    soup = get_soup("https://subang.gangnam.go.kr/pumpjang/viewPumpjang.do")
    result = []
    tables = soup.find_all('table')
    if tables:
        for row in tables[-1].find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 3:
                result.append({"location": cols[0].get_text(strip=True), "total_pumps": cols[1].get_text(strip=True), "active_pumps": cols[2].get_text(strip=True)})
    return result

def collect_sluicegate():
    soup = get_soup("https://subang.gangnam.go.kr/soomoon/viewSoomoon.do")
    result = []
    reference_level = ""
    for table in soup.find_all('table'):
        tds = table.find_all('td')
        if len(tds) == 1:
            val = tds[0].get_text(strip=True).upper().replace('M','').strip()
            try:
                float(val)
                reference_level = val
            except:
                pass
    known_gates = ['강남나들목','신사나들목','신청담나들목']
    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        if line in known_gates:
            entry = {"location": line, "reference_level_m": reference_level}
            for j in range(i+1, min(i+8, len(lines))):
                if lines[j] in ['개문','폐문','상태']:
                    if j+1 < len(lines):
                        entry[lines[j]] = lines[j+1]
            result.append(entry)
    return result

def collect_riverlevel():
    soup = get_soup("https://subang.gangnam.go.kr/river/riverLevel.do")
    result = []
    known_rivers = ['잠수교','청담대교','턴천2교','대치교','대곡교','세곡천','여수대교']
    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        if line in known_rivers:
            for j in range(i+1, min(i+4, len(lines))):
                try:
                    val = float(lines[j].replace('m','').strip())
                    result.append({"location": line, "level_m": str(val)})
                    break
                except:
                    pass
    return result

def collect_river_block():
    soup = get_soup("https://subang.gangnam.go.kr/river/viewRiver.do")
    result = []
    known_rivers = ['양재천','탄천','세곡천']
    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    seen = []
    for line in lines:
        for name in known_rivers:
            if name in line and name not in seen:
                result.append({"river": name, "status": "데이터로딩중(JavaScript)"})
                seen.append(name)
    return result

# -------------------------------------------------------
# GeoJSON 변환
# -------------------------------------------------------
def make_geojson(items, coord_map, properties_fn):
    features = []
    for item in items:
        loc = item.get("location", "")
        coords = coord_map.get(loc)
        if not coords:
            continue
        props = properties_fn(item)
        props["location"] = loc
        # 주소 캐시에서 가져오기
        cache_key = str(coords[1]) + "," + str(coords[0])
        props["address"] = ADDRESS_CACHE.get(cache_key, "")
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [coords[1], coords[0]]},
            "properties": props
        })
    return {"type": "FeatureCollection", "features": features}

def save_geojson(timestamp, rainfall, waterlevel, pumpstation, sluicegate, riverlevel):
    rainfall_geo = make_geojson(rainfall, RAINFALL_COORDS, lambda x: {
        "금일우량": to_float(x.get("금일우량", 0)),
        "시간우량": to_float(x.get("시간우량", 0)),
        "시간최대": to_float(x.get("시간최대", 0)),
        "누계우량": to_float(x.get("누계우량", 0)),
        "timestamp": timestamp
    })
    waterlevel_geo = make_geojson(waterlevel, WATERLEVEL_COORDS, lambda x: {
        "현재수위_m": to_float(x.get("current_level", 0)),
        "관경_m":    to_float(x.get("pipe_diameter", 0)),
        "충만율_pct": to_float(x.get("fill_ratio_pct", 0)),
        "timestamp": timestamp
    })
    pump_geo = make_geojson(pumpstation, PUMPSTATION_COORDS, lambda x: {
        "전체펌프": to_int(x.get("total_pumps", 0)),
        "가동펌프": to_int(x.get("active_pumps", 0)),
        "timestamp": timestamp
    })
    gate_geo = make_geojson(sluicegate, SLUICEGATE_COORDS, lambda x: {
        "기준수위_m": to_float(x.get("reference_level_m", 0)),
        "개문수위":   to_float(x.get("개문", 0)),
        "폐문수위":   to_float(x.get("폐문", 0)),
        "상태":      str(x.get("상태", "")),
        "timestamp": timestamp
    })
    river_geo = make_geojson(riverlevel, RIVERLEVEL_COORDS, lambda x: {
        "수위_m":    to_float(x.get("level_m", 0)),
        "timestamp": timestamp
    })

    for fname, geo in [
        ("geojson_rainfall.geojson", rainfall_geo),
        ("geojson_waterlevel.geojson", waterlevel_geo),
        ("geojson_pump.geojson", pump_geo),
        ("geojson_sluicegate.geojson", gate_geo),
        ("geojson_river.geojson", river_geo),
    ]:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(geo, f, ensure_ascii=False, indent=2)

# -------------------------------------------------------
# 주소 캐시 로드 (add_address.py 결과 재사용)
# -------------------------------------------------------
def load_address_cache():
    try:
        with open("geojson_rainfall.geojson", "r", encoding="utf-8") as f:
            geo = json.load(f)
        for feature in geo["features"]:
            coords = feature["geometry"]["coordinates"]
            key = str(coords[0]) + "," + str(coords[1])
            ADDRESS_CACHE[key] = feature["properties"].get("address", "")
        for fname in ["geojson_waterlevel.geojson","geojson_pump.geojson","geojson_sluicegate.geojson","geojson_river.geojson"]:
            with open(fname, "r", encoding="utf-8") as f:
                geo = json.load(f)
            for feature in geo["features"]:
                coords = feature["geometry"]["coordinates"]
                key = str(coords[0]) + "," + str(coords[1])
                ADDRESS_CACHE[key] = feature["properties"].get("address", "")
        print("주소 캐시 로드 완료: " + str(len(ADDRESS_CACHE)) + "개")
    except:
        print("주소 캐시 없음 (add_address.py 먼저 실행 필요)")

# -------------------------------------------------------
# 전체 수집 + GeoJSON 변환 통합
# -------------------------------------------------------
def collect_all():
    print("")
    print("[" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "] 전체 데이터 수집 중...")
    try:
        rainfall    = collect_rainfall()
        waterlevel  = collect_waterlevel()
        pumpstation = collect_pumpstation()
        sluicegate  = collect_sluicegate()
        riverlevel  = collect_riverlevel()
        river_block = collect_river_block()
        timestamp   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        data = {
            "timestamp":   timestamp,
            "rainfall":    rainfall,
            "waterlevel":  waterlevel,
            "pumpstation": pumpstation,
            "sluicegate":  sluicegate,
            "riverlevel":  riverlevel,
            "river_block": river_block
        }

        with open("gangnam_subang_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # ★ 추가 — Firebase에도 같은 데이터 업로드
        try:
            db.reference("gangnam_subang_data").set(data)
            print("Firebase 업로드 완료")
        except Exception as fe:
            print("Firebase 업로드 실패: " + str(fe))    

        # GeoJSON 자동 변환
        save_geojson(timestamp, rainfall, waterlevel, pumpstation, sluicegate, riverlevel)

        print("강우량:        " + str(len(rainfall))    + "개 지점")
        print("하수관로 수위:  " + str(len(waterlevel))  + "개 지점")
        print("펌프장:        " + str(len(pumpstation)) + "개소")
        print("육갑문:        " + str(len(sluicegate))  + "개소")
        print("하천수위:      " + str(len(riverlevel))  + "개 지점")
        print("GeoJSON 자동 변환 완료")

    except Exception as e:
        print("오류 발생: " + str(e))

# 주소 캐시 먼저 로드
load_address_cache()

# 즉시 1회 실행
collect_all()




