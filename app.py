import calendar
from datetime import datetime
import tkinter as tk


class SwipeCalendarApp(tk.Tk):

  def __init__(self):
    super().__init__()
    self.title("터치 스와이프 달력")
    self.geometry("420x480")
    
    # 배경 색상 설정
    self.bg_color = "#f8f9fa"
    self.configure(bg=self.bg_color)

    # 현재 날짜 상태 초기화
    self.current_date = datetime.now()

    # 스와이프 감지용 변수
    self.touch_start_x = 0
    self.THRESHOLD = 60  # 1달 이동 기준이 되는 최소 드래그 픽셀 거리

    # 상단 연도/월 헤더 (버튼 완전 제거)
    self.header_label = tk.Label(
        self, font=("Arial", 18, "bold"), bg=self.bg_color, fg="#212529"
    )
    self.header_label.pack(pady=25)

    # 달력 날짜들이 표시될 프레임
    self.calendar_frame = tk.Frame(self, bg=self.bg_color)
    self.calendar_frame.pack(expand=True, fill="both", padx=20, pady=10)

    # 창 전체 및 프레임에 마우스/터치 드래그 이벤트 바인딩
    self.bind("<Button-1>", self.on_touch_start)
    self.bind("<ButtonRelease-1>", self.on_touch_end)
    self.calendar_frame.bind("<Button-1>", self.on_touch_start)
    self.calendar_frame.bind("<ButtonRelease-1>", self.on_touch_end)

    # 초기 달력 화면 렌더링
    self.update_calendar()

  def on_touch_start(self, event):
    # 드래그 시작 시점의 절대 X 좌표 기록 (x_root 사용으로 안정성 확보)
    self.touch_start_x = event.x_root

  def on_touch_end(self, event):
    touch_end_x = event.x_root
    distance = self.touch_start_x - touch_end_x

    # 스와이프 거리가 최소 기준(THRESHOLD)을 넘었을 때만 동작
    if abs(distance) >= self.THRESHOLD:
      # 밀린 거리를 기준 거리로 나누어 스와이프한 횟수(개월 수) 계산
      # 예: 150px 밀었으면 약 2.5 -> 정수 변환하여 2달 이동
      month_offset = int(distance / self.THRESHOLD)

      # 월 변경 적용 (양수면 미래, 음수면 과거)
      self.current_date = self.add_months(self.current_date, month_offset)
      self.update_calendar()

  def add_months(self, sourcedate, months):
    # 표준 라이브러리를 활용한 안전한 월 연산 및 말일 보정
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return sourcedate.replace(year=year, month=month, day=day)

  def update_calendar(self):
    year = self.current_date.year
    month = self.current_date.month

    # 헤더 텍스트 갱신
    self.header_label.config(text=f"{year}년 {month}월")

    # 기존 달력 위젯 초기화
    for widget in self.calendar_frame.winfo_children():
      widget.destroy()

    # 요일 헤더 생성 (토/일 색상 구분)
    days = ["월", "화", "수", "목", "금", "토", "일"]
    for i, day in enumerate(days):
      fg_color = "#e03131" if i == 6 else ("#1971c2" if i == 5 else "#495057")
      lbl = tk.Label(
          self.calendar_frame,
          text=day,
          font=("Arial", 11, "bold"),
          bg=self.bg_color,
          fg=fg_color,
          width=4,
      )
      lbl.grid(row=0, column=i, padx=5, pady=5)

    # 날짜 그리드 생성
    cal = calendar.monthcalendar(year, month)
    for r, week in enumerate(cal):
      for c, day in enumerate(week):
        if day != 0:
          # 주말 색상 지정 (토요일: 파란색, 일요일: 빨간색)
          text_color = "#212529"
          if c == 6:
            text_color = "#e03131"
          elif c == 5:
            text_color = "#1971c2"

          lbl = tk.Label(
              self.calendar_frame,
              text=str(day),
              font=("Arial", 11),
              bg="#ffffff",
              fg=text_color,
              width=4,
              height=2,
              relief="solid",
              borderwidth=1,
          )
          lbl.grid(row=r + 1, column=c, padx=3, pady=3)


if __name__ == "__main__":
  app = SwipeCalendarApp()
  app.mainloop()
