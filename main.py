import os
import datetime
import requests
from urllib.parse import quote
from dotenv import load_dotenv
import concurrent.futures

load_dotenv()

KEY = os.getenv("SEOUL_API_KEY")
MAP_API_KEY = os.getenv("MAP_API_KEY")

# API에서 인식하는 정확한 공식 명칭들로 보정함
PLACES = [
    "강남역", "가로수길", "여의도", "홍대 관광특구", "명동 관광특구", "이태원 관광특구", "잠실 관광특구",
    "동대문 관광특구", "종로·청계 관광특구", "경복궁", "광화문·덕수궁", "창덕궁·종묘", "가산디지털단지역",
    "건대입구역", "고속터미널역", "교대역", "구로디지털단지역", "서울역", "선릉역", "신도림역", "신림역",
    "신촌·이대역", "역삼역", "연신내역", "왕십리역", "용산역", "이태원역", "장한평역", "종로3가역", "합정역",
    "DMC(디지털미디어시티)", "창동 신경제 중심지", "노량진", "낙산공원·이화마을", "북촌한옥마을", "서촌",
    "성수카페거리", "수유리 먹자골목", "쌍문동 맛집거리", "압구정로데오거리", "영등포 타임스퀘어", "인사동·익선동",
    "국립중앙박물관·용산가족공원", "남산공원", "뚝섬한강공원", "망원한강공원", "반포한강공원", "북서울꿈의숲",
    "서울대공원", "서울숲공원", "월드컵공원", "이촌한강공원", "잠실종합운동장", "잠실한강공원", "어린이대공원",
    "샤로수길", "송리단길", "행리단길", "광장시장", "노량진 수산시장", "가락시장", "망원시장", "통인시장"
    # (핵심 60여개 우선 배치, 나머지는 성공률 위해 필터링)
]

def get_text_between(content, start_tag, end_tag):
    if start_tag not in content: return None
    start_idx = content.find(start_tag) + len(start_tag)
    end_idx = content.find(end_tag)
    return content[start_idx:end_idx].strip()

def fetch_data(place):
    url = f"http://openapi.seoul.go.kr:8088/{KEY}/xml/citydata/1/5/{quote(place)}"
    try:
        res = requests.get(url, timeout=8)
        content = res.text
        
        if "AREA_CONGEST_LVL" in content:
            lvl = get_text_between(content, "<AREA_CONGEST_LVL>", "</AREA_CONGEST_LVL>")
            
            # 여기서 LAT, LNG가 정확히 매칭되는지 다시 확인
            lat_val = get_text_between(content, "<LAT>", "</LAT>")
            lng_val = get_text_between(content, "<LNG>", "</LNG>")
            
            if not lat_val or not lng_val: return None

            score_map = {"붐빔": 4, "약간 붐빔": 3, "보통": 2, "여유": 1}
            print(f"✅ {place} 수집 성공 ({lvl})")
            
            return {
                "name": place,
                "lat": float(lat_val), # 37.xxx
                "lng": float(lng_val), # 127.xxx
                "score": score_map.get(lvl, 0)
            }
    except:
        pass
    return None

def draw_map(data_list, filename, is_hot=True):
    if not data_list: return
    
    if is_hot:
        # 핫플: 강렬한 네비게이션 나이트 스타일 + 빨간 핀
        style_id = "mapbox/navigation-night-v1"
        color = "ff4444"
        marker_type = "pin-l" # 좀 더 큰 핀으로 강조
    else:
        # 칠플: 자연 친화적인 아웃도어 스타일 + 시원한 하늘색 핀
        style_id = "mapbox/outdoors-v12"
        color = "00dbff"
        marker_type = "pin-m"

    markers = [f"{marker_type}+{color}({d['lng']},{d['lat']})" for d in data_list]
    markers_str = ",".join(markers)
    
    seoul_center = "126.978,37.566,10.7"
    
    # 조립된 URL
    map_url = f"https://api.mapbox.com/styles/v1/{style_id}/static/{markers_str}/{seoul_center}/800x800?access_token={MAP_API_KEY}"
    
    try:
        res = requests.get(map_url)
        if res.status_code == 200:
            with open(filename, "wb") as f:
                f.write(res.content)
            print(f"✨ 스타일 업그레이드 완료: {filename}")
        else:
            print(f"❌ 에러 발생: {res.status_code}")
    except Exception as e:
        print(f"🔥 지도 생성 실패: {e}")

def main():
    print(f"📡 {len(PLACES)}개 장소 데이터 수집 시작...")
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_data, p) for p in PLACES]
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            if r: results.append(r)
            
    print(f"\n📊 총 {len(results)}개 장소 수집 완료")
    
    if results:
        results.sort(key=lambda x: x['score'], reverse=True)
        hot_10 = results[:10]
        chill_10 = results[-10:]
        
        draw_map(hot_10, "seoul_hot.png", True)
        draw_map(chill_10, "seoul_chill.png", False)

def update_readme():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.readlines()
    
    # README 상단이나 특정 위치에 시간 기록
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(f"## 🕒 마지막 업데이트: {time_str} (KST)\n")
        f.writelines(content[1:]) # 기존 내용 이어 붙이기

if __name__ == "__main__":
    main()
    update_readme() # 매 실행 시 README 시간 갱신