import os
import json
import calendar
import datetime
import requests
import pandas as pd
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, io

try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

app = Flask(__name__)

# 데이터 및 설정 경로
DATA_DIR = Path("DATA")
DATA_DIR.mkdir(exist_ok=True)
CONFIG_PATH = DATA_DIR / "local_config.json"
EXCEL_PATH = DATA_DIR / "edited_duty_schedule.xlsx"
STATE_PATH = DATA_DIR / "edited_duty_schedule.json"

def load_config():
    default_cfg = {
        "auto_view_type": "grid",
        "app_theme": "light",
        "kakao_access_token": "",
        "batch_start_date": str(datetime.date.today()),
        "batch_infinite": False,
        "batch_days_c": 30,
        "batch_i1": 3,
        "batch_w1_names": ["", "", ""],
        "batch_i2": 3,
        "batch_w2_names": ["", "", ""]
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                default_cfg.update(json.load(f))
        except Exception:
            pass
    return default_cfg

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_memos():
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("memos", {})
        except Exception:
            pass
    return {}

def save_memos(memos):
    data = {"memos": memos, "last_saved": str(datetime.datetime.now())}
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_duty_df():
    if EXCEL_PATH.exists():
        df = pd.read_excel(EXCEL_PATH)
        df["날짜"] = pd.to_datetime(df["날짜"])
        return df
    
    # 기본 생성
    dates = pd.date_range(start=datetime.date.today().replace(day=1), periods=90, freq="D")
    df = pd.DataFrame({
        "날짜": dates,
        "근무자1": "미지정", "대직1": None,
        "근무자2": "미지정", "대직2": None,
        "실제근무1": "미지정", "실제근무2": "미지정",
        "M열구분": "", "년월": dates.strftime("%Y-%m")
    })
    save_duty_df(df)
    return df

def save_duty_df(df):
    df.to_excel(EXCEL_PATH, index=False)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/init", methods=["GET"])
def api_init():
    cfg = load_config()
    memos = load_memos()
    df = get_duty_df()
    months = sorted(df["년월"].dropna().unique().tolist())
    
    return jsonify({
        "config": cfg,
        "memos": memos,
        "months": months,
        "today": str(datetime.date.today())
    })

@app.route("/api/duty/<ym>", methods=["GET"])
def get_monthly_duty(ym):
    df = get_duty_df()
    memos = load_memos()
    sub_df = df[df["년월"] == ym].copy()
    
    records = []
    for _, row in sub_df.iterrows():
        d_str = row["날짜"].strftime("%Y-%m-%d")
        c_date = row["날짜"].date()
        w_idx = c_date.weekday()
        
        is_holiday = c_date in kr_holidays
        is_sat = (w_idx == 5)
        is_sun = (w_idx == 6)
        
        p1 = str(row.get("근무자1", "미지정"))
        p2 = str(row.get("근무자2", "미지정"))
        sub1 = str(row.get("대직1", "")) if pd.notnull(row.get("대직1")) else ""
        sub2 = str(row.get("대직2", "")) if pd.notnull(row.get("대직2")) else ""
        
        real1 = sub1 if sub1 and sub1 not in ["nan", "None"] else p1
        real2 = sub2 if sub2 and sub2 not in ["nan", "None"] else p2
        
        records.append({
            "date": d_str,
            "day": c_date.day,
            "p1": p1, "p2": p2,
            "sub1": sub1, "sub2": sub2,
            "real1": real1, "real2": real2,
            "m_val": str(row.get("M열구분", "")) if pd.notnull(row.get("M열구분")) else "",
            "memo": memos.get(d_str, ""),
            "is_sat": is_sat,
            "is_sun": is_sun,
            "is_holiday": is_holiday
        })
        
    return jsonify({"data": records})

@app.route("/api/duty/edit", methods=["POST"])
def edit_duty_day():
    data = request.json
    d_str = data.get("date")
    p1 = data.get("p1", "미지정")
    p2 = data.get("p2", "미지정")
    sub1 = data.get("sub1", "")
    sub2 = data.get("sub2", "")
    memo = data.get("memo", "").strip()
    
    df = get_duty_df()
    idx = df[df["날짜"].dt.strftime("%Y-%m-%d") == d_str].index
    
    if not idx.empty:
        i = idx[0]
        df.loc[i, "근무자1"] = p1 if p1 else "미지정"
        df.loc[i, "근무자2"] = p2 if p2 else "미지정"
        df.loc[i, "대직1"] = sub1 if sub1 else None
        df.loc[i, "대직2"] = sub2 if sub2 else None
        df.loc[i, "실제근무1"] = sub1 if sub1 else (p1 if p1 else "미지정")
        df.loc[i, "실제근무2"] = sub2 if sub2 else (p2 if p2 else "미지정")
        save_duty_df(df)
        
    memos = load_memos()
    if memo:
        memos[d_str] = memo
    else:
        memos.pop(d_str, None)
    save_memos(memos)
    
    return jsonify({"status": "success"})

@app.route("/api/config/save", methods=["POST"])
def save_app_config():
    cfg = request.json
    save_config(cfg)
    return jsonify({"status": "success"})

@app.route("/api/duty/batch", methods=["POST"])
def save_batch_pattern():
    data = request.json
    start_d = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    days_c = int(data.get("days", 30))
    infinite = data.get("infinite", False)
    w1 = [x for x in data.get("w1", []) if x]
    w2 = [x for x in data.get("w2", []) if x]
    
    df = get_duty_df()
    cur_d = start_d
    delta = (datetime.date(start_d.year, 12, 31) - start_d).days + 1 if infinite else days_c
    
    for i in range(delta):
        idx = df[df["날짜"].dt.date == cur_d].index
        if not idx.empty:
            i_row = idx[0]
            if w1:
                p1_val = w1[i % len(w1)]
                df.loc[i_row, "근무자1"] = p1_val
                df.loc[i_row, "대직1"] = None
                df.loc[i_row, "실제근무1"] = p1_val
            if w2:
                p2_val = w2[i % len(w2)]
                df.loc[i_row, "근무자2"] = p2_val
                df.loc[i_row, "대직2"] = None
                df.loc[i_row, "실제근무2"] = p2_val
        cur_d += datetime.timedelta(days=1)
        
    save_duty_df(df)
    return jsonify({"status": "success"})

@app.route("/api/stats/<ym>", methods=["GET"])
def get_stats(ym):
    df = get_duty_df()
    f_df = df if ym == "all" else df[df["년월"] == ym]
    
    expanded = []
    duty_dates = set()
    for _, r in f_df.iterrows():
        cat = "평일"
        hours = 15 if "주말" in cat else 7
        w1, w2 = str(r.get("실제근무1", "")).strip(), str(r.get("실제근무2", "")).strip()
        
        has_duty = False
        for w in [w1, w2]:
            if w and w not in ["미지정", "nan", "None"]:
                expanded.append({"worker": w, "hours": hours})
                has_duty = True
        if has_duty:
            duty_dates.add(r["날짜"].date())
            
    if not expanded:
        return jsonify({"workers": [], "total_workers": 0, "total_days": 0, "total_hours": 0})
        
    e_df = pd.DataFrame(expanded)
    summary = e_df.groupby("worker").agg(count=("hours", "count"), hours=("hours", "sum")).reset_index()
    summary = summary.sort_values(by="hours", ascending=False)
    
    return jsonify({
        "workers": summary.to_dict(orient="records"),
        "total_workers": len(summary),
        "total_days": len(duty_dates),
        "total_hours": int(e_df["hours"].sum())
    })

@app.route("/api/kakao/send", methods=["POST"])
def send_kakao_msg():
    data = request.json
    token = data.get("token", "").strip()
    msg = data.get("message", "")
    
    if not token:
        return jsonify({"status": "error", "message": "카카오 토큰이 없습니다."}), 400
    if len(msg) > 200:
        return jsonify({"status": "error", "message": "메시지 200자 초과"}), 400
        
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    payload = {"template_object": json.dumps({"object_type": "text", "text": msg, "link": {"web_url": "https://developers.kakao.com"}})}
    
    resp = requests.post(url, headers=headers, data=payload, timeout=5)
    if resp.status_code == 200:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": resp.text}), resp.status_code

@app.route("/api/excel/download", methods=["GET"])
def download_excel():
    df = get_duty_df()
    memos = load_memos()
    df["메모"] = df["날짜"].dt.strftime("%Y-%m-%d").map(lambda d: memos.get(d, ""))
    
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="숙직근무자")
    out.seek(0)
    return send_file(out, download_name="숙직근무표.xlsx", as_attachment=True)

@app.route("/api/excel/upload", methods=["POST"])
def upload_excel():
    file = request.files.get("file")
    if file:
        df = pd.read_excel(file)
        df["날짜"] = pd.to_datetime(df["날짜"])
        save_duty_df(df)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
