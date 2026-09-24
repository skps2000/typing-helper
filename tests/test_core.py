# -*- coding: utf-8 -*-
"""타이핑 도우미 핵심 로직 테스트.
UI/후킹 없이 순수 함수(한글 조합, 후보 매칭)만 검증한다.
실행: python -m pytest tests/  또는  python tests/test_core.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import typing_helper as th

# 테스트용 표현 목록(파일과 독립)
SAMPLE = [
    "켜고 너한테 말하는 거야 다시 확인해봐",
    "너한테 켜고 입력하는 거임 확인해봐",
    "확인해봐",
    "확인 후 다시 연락드리겠습니다",
    "브리핑해줘",
    "브리핑, 향후 방향성 검토",
    "브리핑 개선해야 할 부분 있나 검토",
    "감사합니다 좋은 하루 보내세요",
    "GitHub 저장소에 올려줘",
]

def setup():
    th.PHRASE_LIST = list(SAMPLE)

_results = []
def check(name, cond, extra=""):
    _results.append((name, bool(cond), extra))
    print(("  PASS " if cond else "  FAIL ") + name + (("  -> "+extra) if extra else ""))

def test_compose():
    cases = {
        "dkssud": "안녕", "gksrmf": "한글", "dkssudgktpdy": "안녕하세요",
        "rkatkgkqslek": "감사합니다", "dnjs": "원", "djqtdma": "없음",
        "ghkrdls": "확인", "qmfl": "브리", "qmflvld": "브리핑",
    }
    for latin, want in cases.items():
        got = th.compose(latin)
        check(f"compose({latin})=={want}", got == want, got)

def test_boundary_midword():
    setup()
    items, pref = th.top_matches("sjgksxp")  # 너한테
    check("너한테: pref", pref == "너한테", pref)
    check("너한테: 중간단어 제안 포함",
          "너한테 말하는 거야 다시 확인해봐" in items, str(items))

def test_phrase_start_priority():
    setup()
    items, pref = th.top_matches("ghkrdls")  # 확인
    check("확인: 시작매칭 우선", items and items[0].startswith("확인"), str(items[:2]))

def test_dedup_and_cap():
    setup()
    items, pref = th.top_matches("ghkrdls")
    check("확인: 후보 중복 없음", len(items) == len(set(items)), str(items))
    check("확인: 최대 개수 준수", len(items) <= th.MAX_SUG, str(len(items)))

def test_short_input_suppressed():
    setup()
    items, pref = th.top_matches("d")
    check("짧은 입력 억제", items == [], str(items))

def test_latin_fallback():
    setup()
    # 한/영 안 바꾸고 영문 자판 그대로 'git' 쳤을 때도 GitHub 표현이 잡혀야
    items, pref = th.top_matches("git")
    check("영문 폴백(git->GitHub)", any(it.startswith("GitHub") for it in items), str(items))

def test_backspace_clear_recovers():
    """v11 회귀 테스트: 백스페이스는 버퍼를 비운다.
    on_press 의 _cur 전이를 그대로 흉내내 반복 입력/삭제 후에도 정상 매칭되는지 본다."""
    setup()
    cur = []
    def press(ch=None, backspace=False):
        if backspace: cur.clear()          # v11 동작
        elif ch is not None: cur.append(ch)
        return th.top_matches("".join(cur))
    # 브리(qmfl) 입력 -> 제안 뜸
    for c in "qmfl": items, _ = press(c)
    check("1회차: 브리 제안", any("브리핑" in it for it in items), str(items))
    # 다 지움(백스페이스 2번) -> 버퍼 비고 제안 없음
    press(backspace=True); items, _ = press(backspace=True)
    check("삭제 후 버퍼 비움", cur == [] and items == [], str(items))
    # 다시 브리 -> 또 제안 떠야(누적 쓰레기 없음)
    for c in "qmfl": items, _ = press(c)
    check("2회차: 브리 다시 제안", any("브리핑" in it for it in items), str(items))
    # 3,4회차 반복
    for rep in (3, 4):
        for _ in range(4): press(backspace=True)
        for c in "qmfl": items, _ = press(c)
        check(f"{rep}회차: 브리 다시 제안", any("브리핑" in it for it in items), str(items))

def test_suffix_backoff():
    """앞 단어가 저장 표현에 없어도 뒤 단어부터 매칭돼야 한다."""
    setup()
    # 1글자 접미("후")는 노이즈 억제로 제외, 전체는 항상 포함
    check("접미후보 생성",
          th._suffix_candidates("그래서 확인 후") == ["그래서 확인 후", "확인 후"],
          str(th._suffix_candidates("그래서 확인 후")))
    # '확인 후'(ghkrdls gn) 전체 매칭
    items, pref = th.top_matches("ghkrdls gn")
    check("확인 후 전체 매칭", any("확인 후" in it for it in items), str(items))
    # 백오프: 존재하지 않는 앞단어 프리픽스를 직접 넣어도 뒤 단어로 매칭
    # (compose 우회: PHRASE_LIST에 대해 _match_from_boundary + _suffix_candidates 직접)
    got = None
    for prefix in th._suffix_candidates("메롱 브리핑"):
        hits = th._match_from_boundary(prefix, th.MAX_SUG)
        if hits: got = (prefix, hits); break
    check("백오프로 브리핑 회수", got and got[0] == "브리핑", str(got))

def test_usage_ranking():
    """자주 채택한 표현이 위로 올라와야 한다(사용 학습)."""
    setup()
    th.USAGE = {}
    base, _ = th.top_matches("ghkrdls")  # 확인
    # 평소엔 위가 아니던 '확인해봐'에 사용빈도를 주면 1순위가 돼야
    th.USAGE = {"확인해봐": 5}
    boosted, _ = th.top_matches("ghkrdls")
    check("사용빈도로 확인해봐 1순위", boosted and boosted[0] == "확인해봐",
          str(boosted[:2]) + " (기본:" + str(base[:2]) + ")")
    th.USAGE = {}  # 정리

def test_line_before_caret():
    check("현재 줄만 추출", th._line_before_caret("가나\n다라 마") == "다라 마",
          th._line_before_caret("가나\n다라 마"))
    check("빈 입력", th._line_before_caret("") == "")
    check("cap 적용", th._line_before_caret("가"*100, cap=10) == "가"*10)

def test_uia_gapfill():
    """실제 텍스트(UIA) 보정: 키 버퍼가 비어도 커서앞 텍스트로 제안, 단 키 입력이 우선."""
    setup()
    th.ACOMP = True; th.USE_UIA_PREFIX = True
    # 1) 백스페이스로 _cur 비었지만 화면엔 '브리'가 남은 상황
    th._cur = []; th._uia_prefix = "브리"; th._update_sug()
    check("UIA 보정: 브리 제안", any("브리핑" in it for it in th.S["items"]), str(th.S["items"]))
    check("UIA 보정: pref=브리", th.S["pref"] == "브리", th.S["pref"])
    # 2) 키 입력이 있으면 키 입력 우선(UIA는 무시)
    th._cur = list("ghkrdls"); th._uia_prefix = "브리"; th._update_sug()
    check("키 입력 우선(확인)", th.S["items"] and th.S["items"][0].startswith("확인"), str(th.S["items"][:1]))
    # 3) 1글자 실제텍스트는 억제(min_prefix=2)
    th._cur = []; th._uia_prefix = "브"; th._update_sug()
    check("1글자 UIA 억제", th.S["items"] == [], str(th.S["items"]))
    th._cur = []; th._uia_prefix = ""   # 정리

def test_settings_roundtrip():
    """설정 저장/복원(임시 파일). 레지스트리는 건드리지 않는다."""
    import tempfile
    old = th.SETTINGS_PATH
    th.SETTINGS_PATH = os.path.join(tempfile.gettempdir(), "th_settings_unittest.json")
    try:
        th.save_settings({"collecting": False, "acomp": True, "autocopy": True})
        got = th.load_settings()
        check("설정 round-trip", got == {"collecting": False, "acomp": True, "autocopy": True}, str(got))
        # 손상 파일이면 빈 dict
        with open(th.SETTINGS_PATH, "w", encoding="utf-8") as f: f.write("{not json")
        check("손상 설정 안전 처리", th.load_settings() == {}, str(th.load_settings()))
    finally:
        try: os.remove(th.SETTINGS_PATH)
        except Exception: pass
        th.SETTINGS_PATH = old

def test_phrases_normalization():
    """로딩 시 끝 공백 제거 + 중복 줄 제거(첫 등장 유지) + 주석/빈 줄 무시."""
    import tempfile
    old_p, old_m = th.PHRASES, th._phrase_mtime
    tmp = os.path.join(tempfile.gettempdir(), "th_phrases_unittest.txt")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# 주석\n브리핑해줘  \n\n브리핑해줘\n확인해봐\n브리핑해줘\n")
    try:
        th.PHRASES = tmp; th.reload_phrases()
        check("중복/공백 정규화", th.PHRASE_LIST == ["브리핑해줘", "확인해봐"], str(th.PHRASE_LIST))
    finally:
        th.PHRASES = old_p; th._phrase_mtime = 0
        try: os.remove(tmp)
        except Exception: pass

def test_chosung_search():
    """초성 검색: ㅂㄹㅍ -> 브리핑 계열."""
    setup()
    check("_chosung", th._chosung("브리핑해줘") == "ㅂㄹㅍㅎㅈ", th._chosung("브리핑해줘"))
    check("초성질의 판별", th._is_chosung_query("ㅂㄹㅍ") and not th._is_chosung_query("브리"))
    res = th.reco_matches("ㅂㄹㅍ")
    check("ㅂㄹㅍ -> 브리핑", any(p.startswith("브리핑") for p in res), str(res[:3]))

def test_password_block():
    """비밀번호 필드로 감지되면(_in_password) 제안을 내지 않는다."""
    setup(); th.ACOMP = True
    th._in_password = True
    th._cur = list("ghkrdls"); th._uia_prefix = "브리"; th._update_sug()
    check("비번칸: 제안 억제", th.S["items"] == [], str(th.S["items"]))
    th._in_password = False; th._cur = []; th._uia_prefix = ""  # 정리

def test_trash_restore():
    """삭제 시 휴지통 보관 + 최근 삭제 복원."""
    import tempfile
    old_p, old_t, old_m = th.PHRASES, th.TRASH_PATH, th._phrase_mtime
    tmpP = os.path.join(tempfile.gettempdir(), "th_ph_unit.txt")
    tmpT = os.path.join(tempfile.gettempdir(), "th_tr_unit.txt")
    with open(tmpP, "w", encoding="utf-8") as f: f.write("브리핑해줘\n확인해봐\n")
    th.PHRASES = tmpP; th.TRASH_PATH = tmpT; th._phrase_mtime = 0
    try:
        if os.path.exists(tmpT): os.remove(tmpT)
        th.reload_phrases()
        msg = th.del_phrase("확인해봐")
        check("삭제→휴지통 보관", ("휴지통" in msg) and ("확인해봐" not in th.PHRASE_LIST), msg)
        with open(tmpT, encoding="utf-8") as f: trash = f.read()
        check("휴지통 파일에 존재", "확인해봐" in trash, trash.strip())
        rmsg = th.restore_last_deleted()
        check("복원됨", ("복원" in rmsg) and ("확인해봐" in th.PHRASE_LIST), rmsg)
    finally:
        th.PHRASES = old_p; th.TRASH_PATH = old_t; th._phrase_mtime = 0
        for p in (tmpP, tmpT):
            try: os.remove(p)
            except Exception: pass

def test_fuzzy_search():
    """RapidFuzz: 검색창 오타도 보정해 찾는다."""
    setup()
    res = th.reco_matches("확인해바")  # 오타(바 vs 봐)
    check("오타 검색 → 확인해봐", "확인해봐" in res, str(res[:3]))

def test_theme_compute():
    """테마 팔레트: light/dark 구분."""
    lt = th.compute_theme("light"); dk = th.compute_theme("dark")
    check("light 팔레트", lt["dark"] is False and lt["bg"] == "#f5f6f8", str(lt))
    check("dark 팔레트", dk["dark"] is True and dk["bg"] != lt["bg"], str(dk))

def test_app_block():
    """앱별 차단: _app_blocked면 제안 억제."""
    setup(); th.ACOMP = True; th._in_password = False; th._app_blocked = False
    th._cur = list("ghkrdls"); th._uia_prefix = "브리"; th._update_sug()
    check("차단 안됨: 제안 나옴", th.S["items"] != [], str(th.S["items"][:1]))
    th._app_blocked = True; th._update_sug()
    check("앱 차단: 제안 억제", th.S["items"] == [], str(th.S["items"]))
    th._app_blocked = False; th._cur = []; th._uia_prefix = ""

def test_hotkey_toggle():
    """빠른 토글 핫키: ACOMP on/off + 설정 저장."""
    import tempfile
    old = th.SETTINGS_PATH
    th.SETTINGS_PATH = os.path.join(tempfile.gettempdir(), "th_hk_unit.json")
    try:
        th.ACOMP = True
        th._toggle_acomp_hotkey()
        check("핫키 토글 → OFF", th.ACOMP is False, str(th.ACOMP))
        check("핫키 설정 저장", th.load_settings().get("acomp") is False, str(th.load_settings()))
        th._toggle_acomp_hotkey()
        check("핫키 토글 → ON", th.ACOMP is True, str(th.ACOMP))
    finally:
        try: os.remove(th.SETTINGS_PATH)
        except Exception: pass
        th.SETTINGS_PATH = old; th.ACOMP = True

def test_proc_name():
    """_proc_name: 현재 프로세스 실행파일명."""
    name = th._proc_name(os.getpid())
    check("_proc_name 자기 프로세스", name.endswith(".exe") and len(name) > 4, name)

def test_sensitive_digits():
    """민감정보 필터: 구분자 있는 카드/전화/계좌 감지, 날짜·짧은 숫자는 통과."""
    check("카드(공백) 감지", th._has_long_digits("카드 1234 5678 9012 3456"))
    check("전화 감지", th._has_long_digits("010-1234-5678"))
    check("계좌 감지", th._has_long_digits("110 234 567890"))
    check("짧은 숫자 통과", not th._has_long_digits("오후 3시 30분 회의"))
    check("날짜(8자리) 통과", not th._has_long_digits("2024-01-01"))

def test_self_focus_block():
    """우리 대시보드 포커스면 제안 억제(오버레이 자기창 위 표시 방지)."""
    setup(); th.ACOMP = True; th._in_password = False; th._app_blocked = False
    th._self_focused = True
    th._cur = list("ghkrdls"); th._uia_prefix = "브리"; th._update_sug()
    check("자기창: 제안 억제", th.S["items"] == [], str(th.S["items"]))
    th._self_focused = False; th._cur = []; th._uia_prefix = ""

def test_version():
    check("APP_VERSION 존재", isinstance(th.APP_VERSION, str) and th.APP_VERSION[0].isdigit(), th.APP_VERSION)

def test_long_insert_clipboard():
    """긴 문장은 클립보드 붙여넣기, 짧은 문장은 타이핑으로 삽입."""
    import tempfile
    calls = {"copied": [], "typed": [], "vpaste": 0}
    class FakeKBD:
        def type(self, t): calls["typed"].append(t)
        def press(self, k):
            if k == "v": calls["vpaste"] += 1
        def release(self, k): pass
    class FakePC:
        def __init__(self): self._c = "원래클립"
        def paste(self): return self._c
        def copy(self, t): self._c = t; calls["copied"].append(t)
    oldKBD, oldPC, oldUP = th.KBD, th.pyperclip, th.USAGE_PATH
    th.KBD = FakeKBD(); th.pyperclip = FakePC()
    th.USAGE_PATH = os.path.join(tempfile.gettempdir(), "th_usage_unit.json")
    try:
        th.S = {"items": ["확인 아주 긴 문장 삽입 테스트입니다"], "idx": 0,
                "pref": "확인", "rem": " 아주 긴 문장 삽입 테스트입니다", "ver": 0, "close": False}
        th._cur = list("x"); th.do_insert()
        check("긴 문장: 붙여넣기 사용", calls["vpaste"] >= 1 and any("긴 문장" in c for c in calls["copied"]), str(calls))
        check("긴 문장: 타이핑 미사용", calls["typed"] == [], str(calls["typed"]))
        check("클립보드 원복", th.pyperclip.paste() == "원래클립", th.pyperclip.paste())
        calls["typed"].clear()
        th.S = {"items": ["가나"], "idx": 0, "pref": "가", "rem": "나", "ver": 0, "close": False}
        th.do_insert()
        check("짧은 문장: 타이핑 사용", calls["typed"] == ["나"], str(calls["typed"]))
    finally:
        th.KBD = oldKBD; th.pyperclip = oldPC; th.USAGE_PATH = oldUP
        try: os.remove(os.path.join(tempfile.gettempdir(), "th_usage_unit.json"))
        except Exception: pass

def test_pin_ranking():
    """고정(★)한 표현이 최상단으로."""
    setup(); th.PINNED = set(); th.USAGE = {}
    base, _ = th.top_matches("ghkrdls")  # 확인
    th.PINNED = {"확인해봐"}
    pinned, _ = th.top_matches("ghkrdls")
    check("고정 표현 최상단", pinned and pinned[0] == "확인해봐",
          str(pinned[:2]) + " (기본:" + str(base[:1]) + ")")
    th.PINNED = set()

def test_placeholder_nav():
    """자리표시자 {..} 있으면 삽입 후 왼쪽 이동+Shift 선택 키를 보낸다."""
    import tempfile
    calls = {"left": 0, "shift": 0, "typed": []}
    class FakeKBD:
        def type(self, t): calls["typed"].append(t)
        def press(self, k):
            n = getattr(k, "name", "")
            if "left" in n: calls["left"] += 1
            if "shift" in n: calls["shift"] += 1
        def release(self, k): pass
    oldKBD, oldPC, oldUP = th.KBD, th.pyperclip, th.USAGE_PATH
    th.KBD = FakeKBD(); th.pyperclip = None   # 타이핑 경로 강제
    th.USAGE_PATH = os.path.join(tempfile.gettempdir(), "th_usage_ph.json")
    try:
        th.S = {"items": ["안녕하 세요 {이름}님"], "idx": 0, "pref": "안녕하",
                "rem": " 세요 {이름}님", "ver": 0, "close": False}
        th._cur = list("x"); th.do_insert()
        check("자리표시자: 왼쪽 이동", calls["left"] > 0, str(calls))
        check("자리표시자: Shift 선택", calls["shift"] > 0, str(calls))
    finally:
        th.KBD = oldKBD; th.pyperclip = oldPC; th.USAGE_PATH = oldUP
        try: os.remove(os.path.join(tempfile.gettempdir(), "th_usage_ph.json"))
        except Exception: pass

def test_maxsug_runtime():
    """MAX_SUG를 바꾸면 top_matches 개수에 즉시 반영(기본 인자 캡처 버그 방지)."""
    old = th.MAX_SUG; th.PINNED = set(); th.USAGE = {}
    th.PHRASE_LIST = ["확인 A", "확인 B", "확인 C", "확인 D", "확인 E"]
    try:
        th.MAX_SUG = 2; few, _ = th.top_matches("ghkrdls")
        check("MAX_SUG=2 제한", len(few) == 2, str(few))
        th.MAX_SUG = 6; many, _ = th.top_matches("ghkrdls")
        check("MAX_SUG=6 더 많이", len(many) == 5 and len(many) > len(few), str(many))
    finally:
        th.MAX_SUG = old

def test_import_export():
    """표현 가져오기(병합/중복제거) + 내보내기(파일 복사)."""
    import tempfile
    old_p, old_m = th.PHRASES, th._phrase_mtime
    tmpP = os.path.join(tempfile.gettempdir(), "th_io_target.txt")
    tmpSrc = os.path.join(tempfile.gettempdir(), "th_io_src.txt")
    tmpOut = os.path.join(tempfile.gettempdir(), "th_io_out.txt")
    with open(tmpP, "w", encoding="utf-8") as f: f.write("기존표현\n")
    with open(tmpSrc, "w", encoding="utf-8") as f: f.write("새표현1\n기존표현\n새표현2\n# 주석줄\n")
    th.PHRASES = tmpP; th._phrase_mtime = 0; th.reload_phrases()
    try:
        msg = th._import_from(tmpSrc)
        check("가져오기 병합", "새표현1" in th.PHRASE_LIST and "새표현2" in th.PHRASE_LIST, msg)
        check("중복 미추가", th.PHRASE_LIST.count("기존표현") == 1, str(th.PHRASE_LIST))
        check("주석 제외", "# 주석줄" not in th.PHRASE_LIST)
        th._export_to(tmpOut)
        with open(tmpOut, encoding="utf-8") as f: out = f.read()
        check("내보내기 내용", "새표현1" in out and "기존표현" in out, out.strip()[:40])
    finally:
        th.PHRASES = old_p; th._phrase_mtime = 0
        for p in (tmpP, tmpSrc, tmpOut):
            try: os.remove(p)
            except Exception: pass

def test_sorted_for_display():
    """추천 목록 정렬: 관련도(원순서)/가나다/최근, 고정(★) 항상 위."""
    th.PHRASE_LIST = ["가", "다", "나"]; th.PINNED = set()
    items = ["다", "가", "나"]
    check("관련도=원순서", th._sorted_for_display(items, "관련도") == items, str(items))
    check("가나다 정렬", th._sorted_for_display(items, "가나다") == ["가", "나", "다"],
          str(th._sorted_for_display(items, "가나다")))
    check("최근 정렬(뒤 index 먼저)", th._sorted_for_display(items, "최근") == ["나", "다", "가"],
          str(th._sorted_for_display(items, "최근")))
    th.PINNED = {"다"}
    check("고정 우선(가나다)", th._sorted_for_display(items, "가나다")[0] == "다",
          str(th._sorted_for_display(items, "가나다")))
    th.PINNED = set()

def test_clean_old_logs():
    """오래된 typing_/raw_ 로그만 파일명 날짜 기준으로 삭제, 그 외 보존."""
    import tempfile, shutil, datetime as _dt
    d = tempfile.mkdtemp(prefix="th_logs_")
    for name in ["typing_2020-01-01.txt", "raw_2020-01-01.txt",
                 "typing_2026-09-25.txt", "raw_2026-09-20.txt",
                 "phrases.txt", "typing_bad.txt"]:
        open(os.path.join(d, name), "w").close()
    today = _dt.date(2026, 9, 25)
    try:
        n = th._clean_old_logs(days=30, root=d, today=today)
        left = set(os.listdir(d))
        check("오래된 로그 2개 삭제", n == 2, str(n))
        check("2020 로그 삭제됨", "typing_2020-01-01.txt" not in left and "raw_2020-01-01.txt" not in left, str(left))
        check("최근 로그 유지", "typing_2026-09-25.txt" in left and "raw_2026-09-20.txt" in left, str(left))
        check("비대상 파일 유지", "phrases.txt" in left and "typing_bad.txt" in left, str(left))
        check("days=0 비활성", th._clean_old_logs(days=0, root=d, today=today) == 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)

def main():
    for fn in [test_compose, test_boundary_midword, test_phrase_start_priority,
               test_dedup_and_cap, test_short_input_suppressed, test_latin_fallback,
               test_backspace_clear_recovers, test_suffix_backoff,
               test_line_before_caret, test_uia_gapfill, test_usage_ranking, test_settings_roundtrip,
               test_phrases_normalization, test_chosung_search,
               test_password_block, test_trash_restore,
               test_fuzzy_search, test_theme_compute,
               test_app_block, test_hotkey_toggle, test_proc_name,
               test_sensitive_digits, test_self_focus_block, test_version,
               test_long_insert_clipboard, test_pin_ranking, test_placeholder_nav,
               test_maxsug_runtime, test_import_export, test_sorted_for_display,
               test_clean_old_logs]:
        print(f"[{fn.__name__}]"); fn()
    n = len(_results); p = sum(1 for _, ok, _ in _results if ok)
    print(f"\n결과: {p}/{n} PASS")
    return 0 if p == n else 1

if __name__ == "__main__":
    sys.exit(main())
