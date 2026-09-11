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

def main():
    for fn in [test_compose, test_boundary_midword, test_phrase_start_priority,
               test_dedup_and_cap, test_short_input_suppressed, test_latin_fallback,
               test_backspace_clear_recovers, test_suffix_backoff,
               test_line_before_caret, test_uia_gapfill]:
        print(f"[{fn.__name__}]"); fn()
    n = len(_results); p = sum(1 for _, ok, _ in _results if ok)
    print(f"\n결과: {p}/{n} PASS")
    return 0 if p == n else 1

if __name__ == "__main__":
    sys.exit(main())
