import pandas as pd
from datetime import date, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz, yaml
from pathlib import Path
from kakao_sender import send_me

CFG = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
SCHEDULE = Path(CFG["data"]["schedule_file"])
MAPPING  = Path(CFG["data"]["mapping_file"])
TZ = pytz.timezone(CFG["scheduler"]["timezone"])

def run_once():
    print(f"[{pd.Timestamp.now()}] ?? 알림 체크 시작")
    if not SCHEDULE.exists() or not MAPPING.exists():
        print("? 파일 없음"); return

    df = pd.read_excel(SCHEDULE, sheet_name="숙직근무자", dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"])

    map_df = pd.read_csv(MAPPING, dtype=str).fillna("")
    # 컬럼: 이름, 카카오키, 알림여부(Y/N)
    key_map = dict(zip(map_df["이름"], map_df["카카오키"]))
    ok_map  = dict(zip(map_df["이름"], map_df["알림여부"]))

    tomorrow = (date.today() + timedelta(1)).strftime("%Y-%m-%d")
    tom = df[df["날짜"].dt.strftime("%Y-%m-%d") == tomorrow]
    if tom.empty: 
        print("?? 내일 근무 없음"); return

    for _, row in tom.iterrows():
        duty = row.get("근무구분","평일")
        memo = row.get("메모","")
        for slot, col in [(1,"실제근무1"), (2,"실제근무2")]:
            name = str(row.get(col,"")).strip()
            if not name: continue
            if ok_map.get(name) != "Y": continue
            k = key_map.get(name)
            if not k: 
                print(f"?? 키 없음: {name}"); continue
            
            msg = (f"?? [당직 알림] 내일 근무입니다\n"
                   f"?? {tomorrow} ({row['요일']})\n"
                   f"?? {duty} ({slot}조)\n"
                   f"?? {name}\n"
                   f"?? {memo or '없음'}")
            
            if send_me(k, msg):
                print(f"? {name} 전송 성공")
            else:
                print(f"? {name} 전송 실패 (토큰 확인 필요)")

if __name__ == "__main__":
    sched = BlockingScheduler(timezone=TZ)
    h, m = map(int, CFG["scheduler"]["check_time"].split(":"))
    sched.add_job(run_once, "cron", hour=h, minute=m, id="duty_alarm")
    print(f"?? 로봇 대기 중... 매일 {h}:{m} 실행")
    try: sched.start()
    except KeyboardInterrupt: print("?? 중단됨")