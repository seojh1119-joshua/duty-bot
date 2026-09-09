<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>대시보드 달력 시스템</title>
    <style>
        :root {
            --bg-color: #f8f9fa;
            --card-bg: #ffffff;
            --text-color: #333333;
            --primary-color: #3498db;
            --border-color: #e2e8f0;
        }
        
        [data-theme="dark"] {
            --bg-color: #1a202c;
            --card-bg: #2d3748;
            --text-color: #f7fafc;
            --primary-color: #63b3ed;
            --border-color: #4a5568;
        }

        body {
            font-family: 'Malgun Gothic', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 15px;
            box-sizing: border-box;
        }

        .dashboard-container {
            max-width: 600px;
            margin: 0 auto;
            background: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }

        /* 2번 요구사항: 조회 년월 시인성 강화 및 헤더 */
        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .current-ym {
            font-size: 1.4rem;
            font-weight: bold;
            color: var(--primary-color);
        }

        /* 3번 요구사항: 설정 버튼 */
        .settings-btn {
            background: var(--primary-color);
            color: white;
            border: none;
            padding: 8px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }

        .cal-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .cal-nav button {
            background: none;
            border: 1px solid var(--border-color);
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            color: var(--text-color);
        }

        /* 5번 요구사항: 모바일 세로모드에서도 가로형 뷰가 유연하게 스크롤 및 행렬 변환되도록 최적화 */
        .calendar-wrapper {
            overflow-x: auto;
            width: 100%;
        }

        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, minmax(40px, 1fr));
            gap: 5px;
            text-align: center;
            min-width: 320px;
        }

        .calendar-grid.horizontal-view {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .day-cell {
            padding: 10px 5px;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-size: 0.9rem;
        }

        /* 통합 설정 모달 */
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.5);
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: var(--card-bg);
            padding: 20px;
            border-radius: 8px;
            width: 90%;
            max-width: 400px;
        }
        .modal-content h3 { margin-top: 0; }
        .close-btn { float: right; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>

<div class="dashboard-container" id="dashboard">
    <!-- 2. 달력 버튼 위에 명확하게 보이는 조회 년월 -->
    <div class="header-bar">
        <div class="current-ym" id="currentYmText">2026년 9월</div>
        <!-- 3. 통합 설정 버튼 -->
        <button class="settings-btn" onclick="openSettings()">설정 ⚙️</button>
    </div>

    <div class="cal-nav">
        <button onclick="changeMonth(-1)">◀ 이전 달</button>
        <span id="subNavigationInfo">좌우로 스와이프하세요</span>
        <button onclick="changeMonth(1)">다음 달 ▶</button>
    </div>

    <!-- 4. 모바일 스와이프 및 5. 가로형 반응형 영역 -->
    <div class="calendar-wrapper" id="swipeArea">
        <div class="calendar-grid" id="calendarGrid">
            <div class="day-cell">일</div><div class="day-cell">월</div><div class="day-cell">화</div>
            <div class="day-cell">수</div><div class="day-cell">목</div><div class="day-cell">금</div><div class="day-cell">토</div>
        </div>
    </div>
</div>

<!-- 3. 통합 설정 모달 (달력 표시 방식, 테마 선택, 근무자 수동 반복 등록, 카카오 센더) -->
<div class="modal" id="settingsModal">
    <div class="modal-content">
        <span class="close-btn" onclick="closeSettings()">&times;</span>
        <h3>통합 설정 메뉴</h3>
        <p>
            <label>달력 표시 방식:</label>
            <select id="displayModeSelect" onchange="saveSettings()">
                <option value="grid">기본 그리드형</option>
                <option value="horizontal">가로형 행렬형</option>
            </select>
        </p>
        <p>
            <label>테마 선택:</label>
            <select id="themeSelect" onchange="saveSettings()">
                <option value="light">라이트 테마</option>
                <option value="dark">다크 테마</option>
            </select>
        </p>
        <hr>
        <p><button style="width:100%; padding:8px;" onclick="alert('근무자 수동 반복 등록 기능 실행')">근무자 수동 반복 등록</button></p>
        <p><button style="width:100%; padding:8px;" onclick="alert('카카오 센더 기능 실행')">카카오 센더 전송</button></p>
    </div>
</div>

<script>
    // 1. 하드웨어 기반 설정 저장 (로컬 스토리지 활용으로 웹 세션 공유 방지)
    function loadSettings() {
        const savedTheme = localStorage.getItem('hardware_theme') || 'light';
        const savedMode = localStorage.getItem('hardware_display_mode') || 'grid';

        document.getElementById('themeSelect').value = savedTheme;
        document.getElementById('displayModeSelect').value = savedMode;

        document.documentElement.setAttribute('data-theme', savedTheme);
        applyDisplayMode(savedMode);
    }

    function saveSettings() {
        const theme = document.getElementById('themeSelect').value;
        const mode = document.getElementById('displayModeSelect').value;

        localStorage.setItem('hardware_theme', theme);
        localStorage.setItem('hardware_display_mode', mode);

        document.documentElement.setAttribute('data-theme', theme);
        applyDisplayMode(mode);
    }

    function applyDisplayMode(mode) {
        const grid = document.getElementById('calendarGrid');
        if (mode === 'horizontal') {
            grid.classList.add('horizontal-view');
        } else {
            grid.classList.remove('horizontal-view');
        }
    }

    function openSettings() { document.getElementById('settingsModal').style.display = 'flex'; }
    function closeSettings() { document.getElementById('settingsModal').style.display = 'none'; }

    // 4. 모바일 터치 스와이프 월 전환 구현
    let touchStartX = 0;
    let touchEndX = 0;

    const swipeArea = document.getElementById('swipeArea');
    swipeArea.addEventListener('touchstart', e => {
        touchStartX = e.changedTouches[0].screenX;
    });

    swipeArea.addEventListener('touchend', e => {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    });

    function handleSwipe() {
        if (touchEndX < touchStartX - 50) {
            changeMonth(1); // 왼쪽으로 밀면 다음 달
        }
        if (touchEndX > touchStartX + 50) {
            changeMonth(-1); // 오른쪽으로 밀면 이전 달
        }
    }

    let currentMonth = 9;
    let currentYear = 2026;

    function changeMonth(direction) {
        currentMonth += direction;
        if (currentMonth > 12) { currentMonth = 1; currentYear++; }
        if (currentMonth < 1) { currentMonth = 12; currentYear--; }
        document.getElementById('currentYmText').innerText = `${currentYear}년 ${currentMonth}월`;
    }

    window.onload = loadSettings;
</script>

</body>
</html>
