# -*- coding: utf-8 -*-
import os, time, threading, traceback, ctypes
from ctypes import wintypes
# 교차 빌드(Wine) 환경의 tcl/tk 경로. 그 경로가 실제로 존재할 때만 설정한다.
# 무조건 setdefault 하면 C:\py311 이 없는 PC에서 소스 실행 시 tk.Tk() 가 죽는다.
for _var, _p in (("TCL_LIBRARY", r"C:\py311\tcl\tcl8.6"), ("TK_LIBRARY", r"C:\py311\tcl\tk8.6")):
    if _var not in os.environ and os.path.isdir(_p): os.environ[_var] = _p
from datetime import datetime, date

def _resolve_log_dir():
    # platformdirs 로 %LOCALAPPDATA%\TypingHelper 사용(OneDrive 리디렉션 안전).
    # 기존 ~/Documents/TypingLog 의 핵심 파일은 복사 이전하고 원본은 그대로 둔다(안전).
    old=os.path.join(os.path.expanduser("~"), "Documents", "TypingLog")
    try:
        import platformdirs, shutil
        new=platformdirs.user_data_dir("TypingHelper", appauthor=False)
        os.makedirs(new, exist_ok=True)
        for name in ("phrases.txt","usage.json","settings.json","phrases_trash.txt","교정프롬프트_가이드.txt"):
            src=os.path.join(old,name); dst=os.path.join(new,name)
            if os.path.exists(src) and not os.path.exists(dst):
                try: shutil.copy2(src,dst)
                except Exception: pass
        return new
    except Exception:
        return old
LOG_DIR=_resolve_log_dir()
os.makedirs(LOG_DIR, exist_ok=True)
def debug(m):
    try:
        with open(os.path.join(LOG_DIR,"_debug.log"),"a",encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {m}\n")
    except Exception: pass
debug("=== v29(클릭 삽입+폰트 폴백) boot ===")
try:
    from pynput import keyboard
    from pynput.keyboard import Controller
    try: import pyperclip
    except Exception: pyperclip=None
    import tkinter as tk
    debug(" imports OK")
except Exception:
    debug("IMPORT 크래시:\n"+traceback.format_exc()); raise
try:
    import pystray
    from PIL import Image as _PILImage, ImageDraw as _PILDraw
    HAVE_TRAY=True; debug(" tray imports OK")
except Exception:
    HAVE_TRAY=False; debug(" tray 미탑재(무시)")
try:
    import sv_ttk; HAVE_SVTTK=True
except Exception:
    HAVE_SVTTK=False

APP_NAME="타이핑 도우미"
APP_VERSION="0.18.0"
GUIDE=os.path.join(LOG_DIR,"교정프롬프트_가이드.txt")
PHRASES=os.path.join(LOG_DIR,"phrases.txt")
FLUSH_IDLE, FLUSH_MAX = 1.5, 200
MIN_PREFIX=2
def mainpath(): return os.path.join(LOG_DIR, f"typing_{date.today().isoformat()}.txt")
def rawpath():  return os.path.join(LOG_DIR, f"raw_{date.today().isoformat()}.txt")

GUIDE_TEXT = """타이핑 도우미 - 교정 프롬프트 가이드
[사용법]
1. 이 폴더의 typing_YYYY-MM-DD.txt 파일을 준비 (영문 깨짐 있으면 raw_*.txt 도)
2. 아래 프롬프트를 복사해 타 AI에 붙여넣고 파일과 함께 전송
3. AI 결과를 복사해 "교정결과(phrases.txt) 열기"로 열어 붙여넣고 저장
4. 저장 즉시 자동완성에 반영 (타이핑 중 회색 제안 → Tab으로 채움)

===== 프롬프트 (여기부터 복사) =====
첨부한 파일은 내가 Windows에서 실제로 타이핑한 기록이야.
한글은 자동 조합돼 오타/조합오류가 있을 수 있고, 한/영 구분이 안 돼 영문이 깨진 부분도 있어(raw로 복원).
작업:
1) 오타/조합오류/깨진 영문을 문맥에 맞게 교정해 자연스러운 문장으로 복원.
2) 의미없는 입력/중복/개인정보(비밀번호·카드·계좌·주민번호·로그인)는 전부 제외.
3) 자주 쓰는 표현/문장을 뽑아 중복 제거, 빈도순 정렬.
출력: 설명·번호·따옴표 없이 표현만 한 줄에 하나씩. 완결 문장 위주.
예)
안녕하세요 반갑습니다
확인 후 다시 연락드리겠습니다
감사합니다 좋은 하루 보내세요
===== (여기까지 복사) =====
"""
def ensure_files():
    if not os.path.exists(GUIDE):
        with open(GUIDE,"w",encoding="utf-8") as f: f.write(GUIDE_TEXT)
    if not os.path.exists(PHRASES):
        with open(PHRASES,"w",encoding="utf-8") as f: f.write("# 타 AI 교정결과(표현 한 줄씩)를 붙여넣고 저장하세요.\n")

# ---- 한글 조합 ----
CHO=list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
JUNG=list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
JONG=list(" ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")
LOWER=dict(zip("qwertyuiopasdfghjklzxcvbnm","ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔㅁㄴㅇㄹㅎㅗㅓㅏㅣㅋㅌㅊㅍㅠㅜㅡ"))
UPPER={"Q":"ㅃ","W":"ㅉ","E":"ㄸ","R":"ㄲ","T":"ㅆ","O":"ㅒ","P":"ㅖ"}
VC={("ㅗ","ㅏ"):"ㅘ",("ㅗ","ㅐ"):"ㅙ",("ㅗ","ㅣ"):"ㅚ",("ㅜ","ㅓ"):"ㅝ",("ㅜ","ㅔ"):"ㅞ",("ㅜ","ㅣ"):"ㅟ",("ㅡ","ㅣ"):"ㅢ"}
TC={("ㄱ","ㅅ"):"ㄳ",("ㄴ","ㅈ"):"ㄵ",("ㄴ","ㅎ"):"ㄶ",("ㄹ","ㄱ"):"ㄺ",("ㄹ","ㅁ"):"ㄻ",("ㄹ","ㅂ"):"ㄼ",("ㄹ","ㅅ"):"ㄽ",("ㄹ","ㅌ"):"ㄾ",("ㄹ","ㅍ"):"ㄿ",("ㄹ","ㅎ"):"ㅀ",("ㅂ","ㅅ"):"ㅄ"}
TS={v:k for k,v in TC.items()}; VOWELS=set(JUNG)
def compose(latin):
    out=[]; st={"cho":None,"jung":None,"jong":None}
    def build(c,ju,jo): return chr(0xAC00+(CHO.index(c)*21+JUNG.index(ju))*28+(JONG.index(jo) if jo else 0))
    def emit():
        c,ju,jo=st["cho"],st["jung"],st["jong"]
        if c and ju: out.append(build(c,ju,jo))
        else:
            for x in (c,ju,jo):
                if x: out.append(x)
        st["cho"]=st["jung"]=st["jong"]=None
    for ch in latin:
        j=UPPER.get(ch) if ch in UPPER else LOWER.get(ch.lower())
        if j is None: emit(); out.append(ch); continue
        c,ju,jo=st["cho"],st["jung"],st["jong"]
        if j in VOWELS:
            if c and ju is None: st["jung"]=j
            elif c and ju and jo is None:
                comb=VC.get((ju,j))
                if comb: st["jung"]=comb
                else: emit(); st["jung"]=j
            elif c and ju and jo:
                if jo in TS:
                    a,b=TS[jo]; out.append(build(c,ju,a)); st["cho"]=b; st["jung"]=j; st["jong"]=None
                else: out.append(build(c,ju,None)); st["cho"]=jo; st["jung"]=j; st["jong"]=None
            else: emit(); st["jung"]=j
        else:
            if c is None and ju is None: st["cho"]=j
            elif c and ju is None: emit(); st["cho"]=j
            elif c and ju and jo is None:
                if j in JONG: st["jong"]=j
                else: emit(); st["cho"]=j
            else:
                comb=TC.get((jo,j))
                if comb: st["jong"]=comb
                else: emit(); st["cho"]=j
    emit(); return "".join(out)

# ---- phrases 로딩 ----
PHRASE_LIST=[]; _phrase_mtime=0
USAGE={}; USAGE_PATH=os.path.join(LOG_DIR,"usage.json")
def load_usage():
    global USAGE
    try:
        import json
        with open(USAGE_PATH,encoding="utf-8") as f: USAGE=json.load(f) or {}
    except Exception: USAGE={}
def save_usage():
    try:
        import json
        with open(USAGE_PATH,"w",encoding="utf-8") as f: json.dump(USAGE,f,ensure_ascii=False)
    except Exception: pass
def record_use(text):
    # Tab으로 채택한 표현의 빈도를 올린다 -> 다음부터 위로 정렬된다.
    if not text: return
    USAGE[text]=USAGE.get(text,0)+1; save_usage()
def _usage_of(t): return USAGE.get(t,0)
PINNED=set(); PINNED_PATH=os.path.join(LOG_DIR,"pinned.json")
def load_pinned():
    global PINNED
    try:
        import json
        with open(PINNED_PATH,encoding="utf-8") as f: PINNED=set(json.load(f) or [])
    except Exception: PINNED=set()
def save_pinned():
    try:
        import json
        with open(PINNED_PATH,"w",encoding="utf-8") as f: json.dump(sorted(PINNED),f,ensure_ascii=False)
    except Exception: pass
def _is_pinned(t): return t in PINNED
def toggle_pin(t):
    t=(t or "").strip()
    if not t: return "고정할 표현을 목록에서 고르세요"
    if t in PINNED: PINNED.discard(t); save_pinned(); return "고정 해제: "+t
    PINNED.add(t); save_pinned(); return "고정됨 ★: "+t
SETTINGS_PATH=os.path.join(LOG_DIR,"settings.json")
def load_settings():
    try:
        import json
        with open(SETTINGS_PATH,encoding="utf-8") as f: return json.load(f) or {}
    except Exception: return {}
def save_settings(d):
    try:
        import json
        with open(SETTINGS_PATH,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False)
    except Exception: debug("설정 저장 실패:\n"+traceback.format_exc())
_RUN_KEY=r"Software\Microsoft\Windows\CurrentVersion\Run"
def _autostart_cmd():
    import sys
    if getattr(sys,"frozen",False): return '"%s"'%sys.executable          # 배포 exe
    py=sys.executable.replace("python.exe","pythonw.exe")                 # 소스 실행(pythonw)
    return '"%s" "%s"'%(py, os.path.abspath(__file__))
def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,_RUN_KEY) as k:
            winreg.QueryValueEx(k,"TypingHelper"); return True
    except Exception: return False
def set_autostart(on):
    # HKCU Run 키에 등록/해제. 관리자 권한 불필요.
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,_RUN_KEY,0,winreg.KEY_SET_VALUE) as k:
            if on: winreg.SetValueEx(k,"TypingHelper",0,winreg.REG_SZ,_autostart_cmd())
            else:
                try: winreg.DeleteValue(k,"TypingHelper")
                except FileNotFoundError: pass
        return True
    except Exception: debug("autostart 실패:\n"+traceback.format_exc()); return False
def _win_is_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k,"AppsUseLightTheme")[0]==0
    except Exception: return False
def compute_theme(mode):
    # mode: auto/light/dark -> 대시보드 색 팔레트
    dark=_win_is_dark() if mode=="auto" else (mode=="dark")
    if dark:
        return {"dark":True,"bg":"#1f2430","fg":"#e5e7eb","sub":"#9aa4b2","listbg":"#0f172a","listfg":"#e5e7eb"}
    return {"dark":False,"bg":"#f5f6f8","fg":"#1f2937","sub":"#6b7280","listbg":"#ffffff","listfg":"#111827"}
def load_phrases():
    global PHRASE_LIST,_phrase_mtime
    try:
        mt=os.path.getmtime(PHRASES)
        if mt==_phrase_mtime: return
        _phrase_mtime=mt
        out=[]; seen=set()
        with open(PHRASES,encoding="utf-8") as f:
            for ln in f:
                s=ln.rstrip("\r\n").rstrip()          # 끝 공백/개행 제거
                if not s.strip() or s.lstrip().startswith("#"): continue
                if s in seen: continue                  # 중복 줄 제거(첫 등장 유지)
                seen.add(s); out.append(s)
        PHRASE_LIST=out; debug(f"phrases {len(out)}개 로드")
    except Exception: pass
def reload_phrases():
    global _phrase_mtime
    _phrase_mtime=0; load_phrases()      # mtime 무시하고 강제로 다시 읽는다
def _has_long_digits(t,n=10):
    # 카드/계좌/전화는 보통 공백·하이픈으로 끊겨 있으므로 구분자는 숫자열을 끊지 않는다.
    # 예) "1234 5678 9012 3456"(16자리) 감지. 날짜(8자리)는 n=10으로 대부분 제외.
    run=0
    for c in t:
        if c.isdigit(): run+=1
        elif c in " -.": pass
        else: run=0
        if run>=n: return True
    return False
def add_phrase(text):
    # 사용자가 손으로 넣는 표현. 수집/교정 경로와 무관하게 저장 즉시 자동완성에 쓰인다.
    t=" ".join(text.split())             # 앞뒤/중복 공백 정리
    if not t: return "빈 표현입니다"
    if t.startswith("#"): return "'#'로 시작하는 줄은 주석이라 쓸 수 없습니다"
    if t in PHRASE_LIST: return "이미 목록에 있습니다"
    try:
        need_nl=False                    # 마지막 줄에 개행이 없으면 붙여준다
        if os.path.exists(PHRASES) and os.path.getsize(PHRASES)>0:
            with open(PHRASES,"rb") as f:
                f.seek(-1,os.SEEK_END); need_nl = f.read(1) not in (b"\n",b"\r")
        with open(PHRASES,"a",encoding="utf-8") as f:
            if need_nl: f.write("\n")
            f.write(t+"\n")
    except Exception:
        debug("표현 추가 실패:\n"+traceback.format_exc()); return "저장 실패 (로그 확인)"
    reload_phrases()
    if _has_long_digits(t): return "추가됨 - 긴 숫자가 있습니다. 민감정보가 아닌지 확인하세요"
    return "추가됨: "+t
TRASH_PATH=os.path.join(LOG_DIR,"phrases_trash.txt")
def del_phrase(text):
    t=(text or "").strip()
    if not t: return "삭제할 표현을 목록에서 고르세요"
    try:
        with open(PHRASES,encoding="utf-8") as f: lines=f.readlines()
        keep=[ln for ln in lines if ln.rstrip("\r\n")!=t]
        if len(keep)==len(lines): return "목록에 없는 표현입니다"
        with open(TRASH_PATH,"a",encoding="utf-8") as tf: tf.write(t+"\n")   # 휴지통 보관(복원 가능)
        with open(PHRASES,"w",encoding="utf-8") as f: f.writelines(keep)
    except Exception:
        debug("표현 삭제 실패:\n"+traceback.format_exc()); return "삭제 실패 (로그 확인)"
    reload_phrases(); return "삭제됨(휴지통 보관): "+t
def restore_last_deleted():
    # 가장 최근 삭제한 표현을 되살린다.
    try:
        if not os.path.exists(TRASH_PATH): return "휴지통이 비어 있습니다"
        with open(TRASH_PATH,encoding="utf-8") as f: tl=[l.rstrip("\r\n") for l in f if l.strip()]
        if not tl: return "휴지통이 비어 있습니다"
        last=tl.pop()
        with open(TRASH_PATH,"w",encoding="utf-8") as f:
            for l in tl: f.write(l+"\n")
        add_phrase(last)   # phrases.txt에 되살리고 reload
        return "복원됨: "+last
    except Exception:
        debug("복원 실패:\n"+traceback.format_exc()); return "복원 실패 (로그 확인)"
def _export_to(path):
    import shutil
    shutil.copy(PHRASES, path); return "내보냄: "+os.path.basename(path)
def export_phrases():
    from tkinter import filedialog
    p=filedialog.asksaveasfilename(defaultextension=".txt", initialfile="phrases_export.txt",
        filetypes=[("텍스트 파일","*.txt")], title="표현 내보내기")
    if not p: return ""
    try: return _export_to(p)
    except Exception: debug("export 실패:\n"+traceback.format_exc()); return "내보내기 실패 (로그 확인)"
def _import_from(path):
    try: raw=open(path,encoding="utf-8").read()
    except UnicodeDecodeError: raw=open(path,encoding="cp949",errors="ignore").read()
    added=0
    for ln in raw.splitlines():
        t=ln.rstrip().strip()
        if t and not t.startswith("#") and t not in PHRASE_LIST:
            add_phrase(t); added+=1
    return "가져옴: %d개 추가"%added
def import_phrases():
    from tkinter import filedialog
    p=filedialog.askopenfilename(filetypes=[("텍스트 파일","*.txt"),("모든 파일","*.*")], title="표현 가져오기")
    if not p: return ""
    try: return _import_from(p)
    except Exception: debug("import 실패:\n"+traceback.format_exc()); return "가져오기 실패 (로그 확인)"
MAX_SUG=6
OV_FONT=11   # 커서 위 제안 목록 글자 크기(9~20)
OV_MAXW=40   # 제안 목록 최대 폭(글자수) - 넘으면 말줄임
UIFONT="Malgun Gothic"   # 대시보드/오버레이 폰트(없으면 _pick_font로 대체)
def _pick_font():
    # 맑은 고딕이 없으면 다른 한글 폰트로 폴백(한글 깨짐 방지)
    try:
        import tkinter.font as _tkfont
        fams=set(_tkfont.families())
        for f in ("Malgun Gothic","맑은 고딕","Noto Sans KR","나눔고딕","Gulim","Dotum","Batang","Segoe UI"):
            if f in fams: return f
    except Exception: pass
    return "Malgun Gothic"
def _match_from_boundary(prefix, n):
    # 각 표현에서 '단어 경계'(맨 앞 또는 공백 다음)에 prefix가 오는 가장 이른 위치를 찾아
    # 그 위치부터 끝까지(꼬리)를 후보로 낸다. 예) prefix="너한테",
    # "켜고 너한테 말하는 거야..." -> 후보 "너한테 말하는 거야..."
    L=len(prefix); pl=prefix.lower(); seen=set(); ranked=[]
    for p in PHRASE_LIST:
        positions=[0]+[i+1 for i,c in enumerate(p) if c==" "]
        for pos in positions:
            tail=p[pos:]
            if len(tail)>L and (tail.startswith(prefix) or tail.lower().startswith(pl)):
                if tail not in seen:
                    seen.add(tail)
                    ranked.append((1 if _is_pinned(tail) else 0, _usage_of(tail), 0 if pos==0 else 1, len(tail), tail))  # 고정>자주쓴것>시작>짧은것
                break   # 한 표현에서 가장 이른 경계만 사용
    ranked.sort(key=lambda x:(-x[0],-x[1],x[2],x[3]))
    return [t for *_,t in ranked][:n]
def _suffix_candidates(s):
    # "그래서 확인 후" -> ["그래서 확인 후", "확인 후", "후"] (전체 먼저, 뒤 단어로 백오프)
    # 앞 단어가 저장된 표현에 없어도 뒤쪽 단어부터는 매칭되게 한다.
    s=s.strip()
    if not s: return []
    words=[w for w in s.split(" ") if w]
    out=[]
    for i in range(len(words)):
        cand=" ".join(words[i:])
        if i==0 or len(cand)>=2:   # 전체는 항상, 백오프 접미는 2자 이상만(노이즈 억제)
            out.append(cand)
    return out
def _matches_for(text, n=MAX_SUG, min_prefix=1):
    # 접두사(text)에 접미 백오프 + 단어경계 매칭. (후보목록, 매칭접두사) 반환.
    if not text or not PHRASE_LIST: return [], ""
    for prefix in _suffix_candidates(text):
        if len(prefix)<min_prefix: continue
        hits=_match_from_boundary(prefix, n)
        if hits: return hits, prefix
    return [], ""
def _line_before_caret(text, cap=80):
    # UIA로 읽은 '줄 시작~커서' 텍스트에서 현재 줄(마지막 줄바꿈 이후)만 잘라낸다.
    if not text: return ""
    seg=text.replace("\r","\n").split("\n")[-1]
    return seg[-cap:]
def top_matches(cur_latin, n=None):
    # 커서 위 목록용 - 키 입력을 한글로 조합(우선)하거나 영문 자판 그대로 매칭.
    if n is None: n=MAX_SUG      # 설정에서 바뀐 개수를 호출 시점에 반영
    if len(cur_latin)<MIN_PREFIX or not PHRASE_LIST: return [], ""
    for base in (compose(cur_latin), cur_latin):
        items,pref=_matches_for(base, n)
        if items: return items, pref
    return [], ""
def reco_matches(q, k=40):
    """대시보드 추천창용 - 사용자가 상자에 입력한 질의(q)로 표현 목록을 걸러 정렬한다.
    한글 IME로 직접 친 질의와 영문 자판(dkssud)으로 친 질의를 모두 처리한다.
    앞부분 일치를 먼저, 그 다음 부분 문자열 포함 순으로 돌려준다."""
    if not q: return PHRASE_LIST[:k]
    ql=q.lower()
    qh=compose(q) if q.isascii() else q   # 영문 자판이면 한글로 조합해 본다
    cho_q=q if _is_chosung_query(q) else (qh if _is_chosung_query(qh) else "")  # 초성 검색
    pre=[]; sub=[]; cho=[]
    for p in PHRASE_LIST:
        pl=p.lower()
        if p.startswith(q) or (qh and p.startswith(qh)) or pl.startswith(ql): pre.append(p)
        elif q in p or (qh and qh in p) or ql in pl: sub.append(p)
        elif cho_q and _chosung(p).startswith(cho_q): cho.append(p)   # ㅂㄹㅍ -> 브리핑
    results=pre+sub+cho
    if len(results)<k:                                   # 오타 허용(RapidFuzz)로 보강
        try:
            from rapidfuzz import process, fuzz
            have=set(results); pool=[p for p in PHRASE_LIST if p not in have]
            for cand,score,_ in process.extract(qh or q, pool, scorer=fuzz.WRatio,
                                                 limit=k-len(results), score_cutoff=70):
                results.append(cand)
        except Exception: pass
    results.sort(key=lambda p: p not in PINNED)   # 고정(★) 표현을 위로(안정 정렬)
    return results[:k]
def _chosung(s):
    # 한글 음절의 첫 자음(초성)만 뽑아 잇는다. "브리핑해줘" -> "ㅂㄹㅍㅎㅈ"
    out=[]
    for ch in s:
        o=ord(ch)
        if 0xAC00<=o<=0xD7A3: out.append(CHO[(o-0xAC00)//588])
        else: out.append(ch)
    return "".join(out)
def _is_chosung_query(q):
    q=q.replace(" ","")
    return len(q)>=2 and all(c in CHO for c in q)

# ---- 상태 ----
_buf=[]; _lock=threading.Lock(); _last_input=time.time()
_ctrl=False; _paste=False; _last_clip=""; COLLECTING=True; ACOMP=True; _alt=False
_cur=[]; _injecting=False; _last_written=""; _today_count=0; _clip_seq=0
USE_UIA_PREFIX=True; _uia_prefix=""; _last_key=0.0; _in_password=False   # UIA 커서앞 텍스트 + 최근타이핑 + 비번칸 여부
_app_blocked=False; _last_fg_app=""; _fg_pid_cache=0; BLOCKED_APPS=set()   # 앱별 자동완성 on/off
_self_focused=False   # 우리 대시보드에 포커스면 제안/수집 안 함
OUR_PID=ctypes.windll.kernel32.GetCurrentProcessId()  # 우리 창엔 제안하지 않기 위한 식별
# 커서 위 제안 목록 상태. 리스너/훅 스레드는 값만 바꾸고 ver를 올리며,
# 실제 그리기는 Tk 메인루프의 overlay_tick 이 맡는다(스레드 간 Tk 호출 제거).
S={"items":[],"idx":0,"pref":"","rem":"","ver":0,"close":False}
KBD=Controller(); LISTENER=None; ROOT=None
VK_C,VK_V,VK_X,VK_TAB,VK_ESC=67,86,88,9,27
VK_UP,VK_DOWN=38,40
# 캐럿을 움직이지 않는 키들 - 자동완성 버퍼(_cur)를 지우면 안 된다.
# Shift가 빠지면 '있습니다', '예쁘다' 처럼 쌍자음/ㅒㅖ가 든 단어에서 접두사가 통째로 날아간다.
_KEEP_CUR=frozenset({
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr,
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
    keyboard.Key.caps_lock, keyboard.Key.tab,
})

def on_press(key):
    global _ctrl,_last_input,_paste,_injecting,_last_key,_alt
    # 여기서 예외가 새어나가면 pynput이 리스너를 조용히 중단시킨다.
    # join()을 하는 곳이 없어서 수집이 멎어도 아무도 모른다 - 전체를 감싼다.
    try:
        _last_key=time.time()
        if _injecting: return
        if key in (keyboard.Key.ctrl_l,keyboard.Key.ctrl_r): _ctrl=True; return
        if key in (keyboard.Key.alt_l,keyboard.Key.alt_r,keyboard.Key.alt_gr,keyboard.Key.alt): _alt=True; return
        if _ctrl and _alt and key==keyboard.Key.space:   # 빠른 토글: 자동완성 on/off
            _toggle_acomp_hotkey(); return
        vk=getattr(key,"vk",None)
        if _ctrl and vk in (VK_C,VK_V,VK_X):
            if vk==VK_V: _paste=True
            _cur.clear(); _update_sug()
            return
        ch=getattr(key,"char",None)
        # 수집 버퍼 (비밀번호 필드/우리 대시보드에서는 기록하지 않는다)
        if COLLECTING and not _in_password and not _self_focused:
            _last_input=time.time()
            with _lock:
                if ch is not None: _buf.append(ch)
                elif key==keyboard.Key.space: _buf.append(" ")
                elif key==keyboard.Key.enter: _buf.append("\n")
                elif key==keyboard.Key.backspace:
                    if _buf: _buf.pop()
                elif key==keyboard.Key.tab: _buf.append("\t")
        # 자동완성용 현재줄 버퍼 (비밀번호/우리 대시보드에서는 조합/제안 건너뜀)
        if _in_password or _self_focused:
            if _cur: _cur.clear()
        elif ch is not None: _cur.append(ch)
        elif key==keyboard.Key.space: _cur.append(" ")
        elif key==keyboard.Key.backspace:
            _cur.clear()   # 한글 1자=영문 여러타라 하나만 pop하면 어긋남 -> 통째로 비움
        elif key in (keyboard.Key.enter,keyboard.Key.esc): _cur.clear()
        elif key not in _KEEP_CUR: _cur.clear()   # 방향키·Home/End 등 캐럿 이동 시
        _update_sug()
    except Exception:
        debug("on_press 예외:\n"+traceback.format_exc())

def on_release(key):
    global _ctrl,_alt
    if key in (keyboard.Key.ctrl_l,keyboard.Key.ctrl_r): _ctrl=False
    elif key in (keyboard.Key.alt_l,keyboard.Key.alt_r,keyboard.Key.alt_gr,keyboard.Key.alt): _alt=False

def _set_sug(items,pref,idx=0,close=False):
    # ver를 '맨 마지막'에 올려야 그리는 쪽이 반쯤 갱신된 상태를 보지 않는다.
    S["items"]=items; S["pref"]=pref; S["idx"]=idx
    S["rem"]=items[idx][len(pref):] if items else ""
    S["close"]=close   # True=즉시 숨김(Esc/삽입), False=잠깐 유지 후 숨김(편집 중 깜빡임 방지)
    S["ver"]+=1
def _persist_acomp():
    try:
        d=load_settings(); d["acomp"]=ACOMP; save_settings(d)
    except Exception: pass
def _toggle_acomp_hotkey():
    global ACOMP
    ACOMP=not ACOMP
    if not ACOMP: _set_sug([],"")
    _persist_acomp()
def _update_sug():
    if _self_focused or _in_password or _app_blocked or not ACOMP: _set_sug([],""); return
    try: _cur_s="".join(_cur)      # 훅/COM 두 스레드가 부르므로 동시변경 대비 스냅샷
    except Exception: _cur_s=""
    items,pref=top_matches(_cur_s)                     # 키 입력 조합(즉각)
    if not items and USE_UIA_PREFIX and _uia_prefix:   # 버퍼가 비었/어긋났으면 실제 텍스트로 보정
        items,pref=_matches_for(_uia_prefix, MAX_SUG, min_prefix=2)
    _set_sug(items,pref)          # 글자를 더 치면 선택은 항상 첫 항목으로
def move_sel(d):
    # 화살표로 후보 이동. 저수준 훅 콜백에서 불리므로 Tk를 건드리지 않는다.
    n=len(S["items"])
    if not n: return
    _set_sug(S["items"],S["pref"],(S["idx"]+d)%n)

def do_insert():
    global _injecting,_last_clip
    rem=S["rem"]
    if not rem: return
    try: acc=S["items"][S["idx"]] if S["items"] else None    # 채택한 전체 후보
    except Exception: acc=None
    _injecting=True
    try:
        if len(rem)>=6 and pyperclip:      # 긴 문장: 클립보드 붙여넣기로 빠르게(한 글자씩보다 안정적)
            orig=None
            try: orig=pyperclip.paste()
            except Exception: orig=None
            _last_clip=rem                 # writer가 이 삽입을 '복사됨'으로 기록하지 않게
            pyperclip.copy(rem); time.sleep(0.02)
            KBD.press(keyboard.Key.ctrl); KBD.press("v"); KBD.release("v"); KBD.release(keyboard.Key.ctrl)
            time.sleep(0.12)
            if orig is not None:           # 사용자 클립보드 원상복구
                try: pyperclip.copy(orig); _last_clip=orig
                except Exception: pass
        else:
            KBD.type(rem)
    except Exception:
        debug("insert fail:\n"+traceback.format_exc())
        try: KBD.type(rem)                 # 클립보드 경로 실패 시 타이핑으로 폴백
        except Exception: pass
    try:                                   # 자리표시자 {..}: 첫 자리로 커서 이동 + 선택
        i=rem.find("{"); j=(rem.find("}", i) if i>=0 else -1)
        if 0<=i<j:
            for _ in range(len(rem)-(j+1)):
                KBD.press(keyboard.Key.left); KBD.release(keyboard.Key.left)
            KBD.press(keyboard.Key.shift)
            for _ in range(j-i+1):
                KBD.press(keyboard.Key.left); KBD.release(keyboard.Key.left)
            KBD.release(keyboard.Key.shift)
    except Exception: debug("placeholder nav 실패:\n"+traceback.format_exc())
    time.sleep(0.03); _injecting=False
    if acc: record_use(acc)
    _cur.clear(); _set_sug([],"",close=True)

def win_filter(msg, data):
    # suppress_event()는 값을 반환하지 않고 SuppressException(Exception 상속)을 '발생'시켜
    # pynput에 억제를 알린다. 따라서 두 가지를 지켜야 한다.
    #  (1) 삽입 스레드를 먼저 띄운다 - 예외가 나면 그 뒤 줄은 실행되지 않는다.
    #  (2) 그 호출을 try/except Exception 으로 감싸지 않는다 - 감싸면 억제가 사라져
    #      Tab이 앱으로 그대로 새고, 삽입도 일어나지 않는다(기존 버그).
    # 저수준 훅 콜백이라 여기서는 Tk를 절대 호출하지 않는다(훅 타임아웃 방지).
    try:
        if msg not in (256,260) or not ACOMP or LISTENER is None or not S["items"]: return
        vk=getattr(data,"vkCode",0)
    except Exception:
        debug("filter err:\n"+traceback.format_exc()); return
    if vk==VK_TAB: threading.Thread(target=do_insert,daemon=True).start()
    elif vk==VK_UP: move_sel(-1)
    elif vk==VK_DOWN: move_sel(1)
    elif vk==VK_ESC: _set_sug([],"",close=True)
    else: return
    LISTENER.suppress_event()   # 예외를 던진다 - 반드시 바깥으로 전파되어야 한다

# ---- 캐럿 위치 ----
class RECT(ctypes.Structure):
    _fields_=[("left",wintypes.LONG),("top",wintypes.LONG),("right",wintypes.LONG),("bottom",wintypes.LONG)]
class GTI(ctypes.Structure):
    _fields_=[("cbSize",wintypes.DWORD),("flags",wintypes.DWORD),("hwndActive",wintypes.HWND),
              ("hwndFocus",wintypes.HWND),("hwndCapture",wintypes.HWND),("hwndMenuOwner",wintypes.HWND),
              ("hwndMoveSize",wintypes.HWND),("hwndCaret",wintypes.HWND),("rcCaret",RECT)]
u32=ctypes.windll.user32
# restype을 안 주면 ctypes가 c_int(32비트)로 받아 64비트에서 HWND가 잘릴 수 있다.
u32.GetForegroundWindow.restype = wintypes.HWND
u32.GetWindowThreadProcessId.restype = wintypes.DWORD
try: u32.GetClipboardSequenceNumber.restype = wintypes.DWORD
except Exception: pass
def clip_seq():
    """클립보드를 열지 않고 내용이 바뀌었는지만 확인한다(프로세스 공유 자원이라 잦은 open은 위험)."""
    try: return int(u32.GetClipboardSequenceNumber())
    except Exception: return time.monotonic_ns()   # 실패 시 매번 다른 값 -> 항상 읽기로 폴백
def caret_xy():
    try:
        gti=GTI(); gti.cbSize=ctypes.sizeof(GTI)
        tid=u32.GetWindowThreadProcessId(u32.GetForegroundWindow(),0)
        if u32.GetGUIThreadInfo(tid,ctypes.byref(gti)) and gti.hwndCaret:
            pt=wintypes.POINT(gti.rcCaret.left,gti.rcCaret.bottom)
            u32.ClientToScreen(gti.hwndCaret,ctypes.byref(pt))
            if pt.x>0 or pt.y>0: return pt.x+2, pt.y+2
    except Exception: pass
    try:
        pt=wintypes.POINT(); u32.GetCursorPos(ctypes.byref(pt)); return pt.x+12, pt.y+18
    except Exception: return None
_k32=ctypes.windll.kernel32
_k32.OpenProcess.restype=wintypes.HANDLE
_k32.OpenProcess.argtypes=[wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.QueryFullProcessImageNameW.restype=wintypes.BOOL
_k32.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
_k32.CloseHandle.argtypes=[wintypes.HANDLE]
def _proc_name(pid):
    # 포커스 창 프로세스의 실행파일명(소문자). 앱별 on/off 판별용.
    if not pid: return ""
    h=_k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h: return ""
    try:
        buf=ctypes.create_unicode_buffer(260); sz=wintypes.DWORD(260)
        if _k32.QueryFullProcessImageNameW(h,0,buf,ctypes.byref(sz)):
            return os.path.basename(buf.value).lower()
    except Exception: pass
    finally:
        _k32.CloseHandle(h)
    return ""
_caret_xy=None   # UIA 추적 스레드가 채우는 최신 캐럿 좌표(없으면 caret_xy 폴백)
def caret_tracker():
    # UI Automation으로 포커스 요소의 캐럿(텍스트 선택) 위치를 따라간다.
    # GetGUIThreadInfo가 못 잡는 Chromium/Electron 계열도 여기서 잡힌다. COM이라 별도 STA 스레드.
    global _caret_xy,_uia_prefix,_in_password,_app_blocked,_last_fg_app,_fg_pid_cache,_self_focused
    try:
        import comtypes, comtypes.client as _cc
        try: comtypes.CoInitialize()
        except Exception: pass
        _cc.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as _UIA
        uia=_cc.CreateObject(_UIA.CUIAutomation, interface=_UIA.IUIAutomation)
        TPID=_UIA.UIA_TextPatternId; ITP=_UIA.IUIAutomationTextPattern
        debug("UIA 캐럿 추적 시작")
    except Exception:
        debug("UIA 불가(GetGUIThreadInfo/마우스 폴백):\n"+traceback.format_exc()); return
    EP_START=_UIA.TextPatternRangeEndpoint_Start; U_LINE=_UIA.TextUnit_Line
    fg_pid=wintypes.DWORD(); _logged=False
    while True:
        try:
            if not ACOMP: time.sleep(0.2); continue
            fg=u32.GetForegroundWindow(); u32.GetWindowThreadProcessId(fg, ctypes.byref(fg_pid))
            if fg_pid.value==OUR_PID:                  # 우리 대시보드엔 제안/수집하지 않는다
                _self_focused=True
                if _uia_prefix: _uia_prefix=""
                if S["items"]: _set_sug([],"",close=True)
                _in_password=False; time.sleep(0.12); continue
            _self_focused=False
            pid=fg_pid.value
            if pid!=_fg_pid_cache:
                _fg_pid_cache=pid; _last_fg_app=_proc_name(pid)   # 포커스 앱 실행파일명 캐시
            _app_blocked=_last_fg_app in BLOCKED_APPS
            if _app_blocked:                           # 이 앱은 자동완성 끔
                if _uia_prefix: _uia_prefix=""
                if S["items"]: _set_sug([],"",close=True)
                time.sleep(0.12); continue
            el=uia.GetFocusedElement()
            try: pw=bool(el.CurrentIsPassword) if el is not None else False   # 비밀번호 필드?
            except Exception: pw=False
            _in_password=pw
            if pw:                                     # 비번칸: 아무것도 읽지/제안하지 않음
                if _uia_prefix: _uia_prefix=""
                time.sleep(0.1); continue
            active=bool(S["items"]); recent=(time.time()-_last_key)<3.0
            if not (active or recent):                 # 유휴: 무거운 읽기 생략(CPU 절약)
                time.sleep(0.15); continue
            xy=None; newp=""
            if el is not None:
                try:
                    tp=el.GetCurrentPattern(TPID)
                    if tp:
                        sel=tp.QueryInterface(ITP).GetSelection()
                        if sel and sel.Length>0:
                            r0=sel.GetElement(0)
                            if active:                 # 위치는 목록이 떠 있을 때만 필요
                                v=list(r0.GetBoundingRectangles())
                                if len(v)>=4: xy=(int(v[0])+2, int(v[1]+v[3])+2)
                            try:                       # 커서 앞 현재 줄 텍스트
                                rng=r0.Clone(); rng.MoveEndpointByUnit(EP_START,U_LINE,-1)
                                newp=_line_before_caret(rng.GetText(120))
                                if newp and not _logged: debug("UIA 텍스트 보정 사용 시작"); _logged=True
                            except Exception: pass
                except Exception: pass
                if xy is None and active:
                    try:
                        r=el.CurrentBoundingRectangle
                        if r.right>r.left: xy=(int(r.left)+6, int(r.bottom)+2)
                    except Exception: pass
            if xy: _caret_xy=xy
            if newp!=_uia_prefix:                      # 실제 텍스트가 바뀌면(마우스/편집/삭제) 반영
                _uia_prefix=newp
                if time.time()-_last_key<1.5: _update_sug()   # 최근 타이핑 중일 때만 능동 표시
        except Exception: pass
        time.sleep(0.035 if S["items"] else 0.07)

# ---- 수집 writer ----
def _emit(mf,rf,han,raw,tag=""):
    global _last_written,_today_count
    if han==_last_written: return
    _last_written=han
    ts=f"[{datetime.now():%H:%M:%S}]"; t=f" [{tag}]" if tag else ""
    mf.write(f"{ts}{t} {han}\n"); rf.write(f"{ts}{t} {raw}\n"); mf.flush(); rf.flush()
    _today_count+=1
def flush(mf,rf):
    global _buf
    with _lock:
        if not _buf: return
        raw="".join(_buf); _buf=[]
    for line in raw.split("\n"):
        if not line.strip(): continue
        _emit(mf,rf,compose(line),line)
def writer():
    global _paste,_last_clip,_today_count,_clip_seq
    try:
        cur=date.today(); mf=open(mainpath(),"a",encoding="utf-8"); rf=open(rawpath(),"a",encoding="utf-8")
    except Exception:
        debug("writer 시작 실패:\n"+traceback.format_exc()); return
    while True:
        try:      # 루프 본문을 감싸 일시 오류(파일 잠김/클립보드 오류 등)에도 수집이 멈추지 않게
            time.sleep(0.4); load_phrases()
            if date.today()!=cur:
                flush(mf,rf); mf.close(); rf.close(); cur=date.today()
                mf=open(mainpath(),"a",encoding="utf-8"); rf=open(rawpath(),"a",encoding="utf-8")
                _today_count=0
            if COLLECTING and pyperclip:
                seq=clip_seq()
                if seq!=_clip_seq:
                    _clip_seq=seq
                    try: clip=pyperclip.paste()
                    except Exception: clip=""
                    if clip and clip!=_last_clip:
                        _last_clip=clip
                        if len(clip)<=2000 and not _has_long_digits(clip):   # 민감/초장문 제외
                            flush(mf,rf); one=clip.replace("\n"," ⏎ ")
                            _emit(mf,rf,one,one,"복사됨")
            if _paste:
                _paste=False; cp=(_last_clip or "")
                if cp and len(cp)<=2000 and not _has_long_digits(cp):
                    flush(mf,rf); one=cp.replace("\n"," ⏎ ")
                    _emit(mf,rf,one,one,"붙여넣기")
            with _lock: n=len(_buf)
            if n and (time.time()-_last_input>=FLUSH_IDLE or n>=FLUSH_MAX): flush(mf,rf)
        except Exception:
            debug("writer 루프 예외(계속):\n"+traceback.format_exc()); time.sleep(0.5)

def count_today_lines():
    try:
        with open(mainpath(),encoding="utf-8") as f: return sum(1 for _ in f)
    except Exception: return 0
def _open(p):
    try: os.startfile(p)
    except Exception: debug("open fail "+p+"\n"+traceback.format_exc())

# ---- 오버레이 ----
OV=None; OVLIST=None; OVHINT=None; _drawn_ver=-1
_ov_shown=False; _empty_ticks=0; _last_pos=None
_ui_q=[]; _ui_lock=threading.Lock(); _TRAY=None
def post_ui(fn):
    # 다른 스레드(트레이 등)가 Tk 작업을 Tk 메인루프에서 실행하도록 큐에 넣는다.
    with _ui_lock: _ui_q.append(fn)
def build_overlay(root):
    global OV,OVLIST,OVHINT
    OV=tk.Toplevel(root); OV.overrideredirect(True); OV.attributes("-topmost",True)
    try: OV.attributes("-alpha",0.95)
    except Exception: pass
    OV.configure(bg="#374151")
    OVLIST=tk.Listbox(OV,font=(UIFONT,OV_FONT),activestyle="none",bd=0,
                      highlightthickness=0,exportselection=False,
                      bg="#111827",fg="#e5e7eb",selectbackground="#2563eb",selectforeground="white")
    OVLIST.pack(fill="both",padx=1,pady=(1,0))
    OVHINT=tk.Label(OV,text="↑↓ 선택 · Tab 완성 · Esc 닫기",
                    font=(UIFONT,8),bg="#1f2937",fg="#9ca3af",anchor="w",padx=6)
    OVHINT.pack(fill="x",padx=1,pady=(0,1))
    OV.update_idletasks()
    # 팝업이 포커스를 가져가면 입력 필드의 한/영 상태가 초기화된다(영어로 바뀜).
    # NOACTIVATE 로 절대 활성화되지 않는 순수 표시용 창으로 만든다.
    try:
        GWL_EXSTYLE=-20; WS_EX_NOACTIVATE=0x08000000; WS_EX_TOOLWINDOW=0x00000080
        u32.GetParent.restype=wintypes.HWND; u32.GetParent.argtypes=[wintypes.HWND]
        u32.GetWindowLongW.restype=wintypes.LONG; u32.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int]
        u32.SetWindowLongW.restype=wintypes.LONG; u32.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.LONG]
        hwnd=OV.winfo_id(); gp=u32.GetParent(hwnd) or hwnd
        cur=u32.GetWindowLongW(gp,GWL_EXSTYLE)
        u32.SetWindowLongW(gp,GWL_EXSTYLE,cur|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW)
    except Exception: debug("noactivate 실패:\n"+traceback.format_exc())
    def _on_ov_click(e):
        try:
            idx=OVLIST.nearest(e.y)
            if idx is None or idx<0 or idx>=len(S["items"]): return
            _set_sug(S["items"], S["pref"], idx)          # 클릭한 항목으로 선택
            threading.Thread(target=do_insert, daemon=True).start()
        except Exception: debug("ov click:\n"+traceback.format_exc())
    OVLIST.bind("<ButtonRelease-1>", _on_ov_click)        # 마우스로 골라 바로 삽입
    OV.withdraw()
def _place(xy):
    x,y=xy; w=OV.winfo_reqwidth(); h=OV.winfo_reqheight()
    sw=OV.winfo_screenwidth(); sh=OV.winfo_screenheight()
    if x+w>sw: x=max(0,sw-w-4)
    if y+h>sh: y=max(0,y-h-30)          # 아래 공간 없으면 캐럿 위쪽으로
    OV.geometry(f"+{x}+{y}")
def draw_overlay():
    # 내용/위치 갱신. 숨김 판단은 overlay_tick.
    global _ov_shown,_last_pos
    if not OV: return
    items=S["items"]
    if not items: return
    xy=_caret_xy or caret_xy()          # UIA 추적값 우선, 없으면 Win32/마우스 폴백
    if not xy: return
    idx=S["idx"]
    if idx>=len(items): idx=len(items)-1
    OVLIST.delete(0,tk.END)
    disp=[(p if len(p)<=OV_MAXW else p[:OV_MAXW-1]+"…") for p in items]   # 긴 제안은 …로
    for d in disp: OVLIST.insert(tk.END,"  "+d)
    OVLIST.config(height=len(items), width=min(OV_MAXW+3, max(len(x) for x in disp)+4))
    OVLIST.selection_clear(0,tk.END); OVLIST.selection_set(idx); OVLIST.see(idx)
    OV.update_idletasks(); _place(xy); _last_pos=xy
    if not _ov_shown: OV.deiconify(); OV.lift(); _ov_shown=True
def _hide_ov():
    global _ov_shown
    if OV and _ov_shown: OV.withdraw(); _ov_shown=False
def hide_overlay(): _hide_ov()
_HIDE_TICKS=10   # 10 x 25ms ≈ 0.25초 동안 후보가 계속 비어야 숨긴다
def overlay_tick():
    # 오버레이/트레이 관련 Tk 작업은 전부 여기(메인루프)서만 한다.
    global _drawn_ver,_empty_ticks,_last_pos
    try:
        while True:                    # 다른 스레드가 요청한 UI 작업 처리
            with _ui_lock: fn=_ui_q.pop(0) if _ui_q else None
            if not fn: break
            try: fn()
            except Exception: debug("ui_q 예외:\n"+traceback.format_exc())
        items=S["items"]; ver=S["ver"]
        if not ACOMP:
            _hide_ov(); _empty_ticks=0
        elif items:                    # 후보 있음 -> 계속 노출
            _empty_ticks=0
            if ver!=_drawn_ver or not _ov_shown:
                _drawn_ver=ver; draw_overlay()
            elif _caret_xy and _caret_xy!=_last_pos:   # 내용 그대로, 캐럿만 이동 -> 따라가기
                _place(_caret_xy); _last_pos=_caret_xy
        else:                          # 후보 없음
            _drawn_ver=ver
            if S.get("close"): _hide_ov(); _empty_ticks=0
            else:
                _empty_ticks+=1
                if _empty_ticks>=_HIDE_TICKS: _hide_ov()
    except Exception: debug("overlay 예외:\n"+traceback.format_exc())
    if ROOT: ROOT.after(25,overlay_tick)

# ---- 트레이 아이콘 ----
def _tray_image():
    img=_PILImage.new("RGB",(64,64),(37,99,235))
    d=_PILDraw.Draw(img)
    d.rectangle([10,20,53,44],outline=(255,255,255),width=3)   # 키보드 느낌
    for x in (17,27,37,47): d.rectangle([x,26,x+4,30],fill=(255,255,255))
    for x in (22,32,42):    d.rectangle([x,34,x+4,38],fill=(255,255,255))
    return img
def start_tray(on_open,on_quit,on_collect,on_acomp):
    global _TRAY
    if not HAVE_TRAY: debug("트레이 없음(미탑재)"); return None
    try:
        menu=pystray.Menu(
            pystray.MenuItem("열기", lambda i,it: on_open(), default=True),
            pystray.MenuItem("수집 켜기/끄기", lambda i,it: on_collect()),
            pystray.MenuItem("자동완성 켜기/끄기", lambda i,it: on_acomp()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", lambda i,it: on_quit()),
        )
        _TRAY=pystray.Icon("TypingHelper", _tray_image(), APP_NAME, menu)
        threading.Thread(target=_TRAY.run, daemon=True).start()
        debug("트레이 시작"); return _TRAY
    except Exception:
        debug("트레이 실패:\n"+traceback.format_exc()); return None

# ---- 대시보드 ----
_MUTEX=None
def single_instance():
    # windll.kernel32.GetLastError() 는 ctypes 자체 호출에 덮여 신뢰할 수 없다.
    # 그래서 중복 실행이 안 잡히고 인스턴스가 여러 개 떴다.
    # use_last_error=True + ctypes.get_last_error() 로 읽어야 실제 에러코드가 나온다.
    global _MUTEX
    try:
        k=ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateMutexW.restype=wintypes.HANDLE
        k.CreateMutexW.argtypes=[wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        _MUTEX=k.CreateMutexW(None, False, "TypingHelper_SingleInstance_Mutex")  # 핸들은 프로세스 수명 동안 유지
        if ctypes.get_last_error()==183:  # ERROR_ALREADY_EXISTS
            debug("이미 실행 중 - 종료")
            try: ctypes.windll.user32.MessageBoxW(0,"타이핑 도우미가 이미 실행 중입니다.\n(작업표시줄 확인)","타이핑 도우미",0x40)
            except Exception: pass
            os._exit(0)
    except Exception: debug("mutex 체크 실패(무시):\n"+traceback.format_exc())

def run_ui():
    global LISTENER,ROOT,_today_count,COLLECTING,ACOMP,MAX_SUG,OV_FONT,UIFONT
    single_instance()
    ensure_files(); load_phrases(); load_usage(); load_pinned()
    _cfg=load_settings(); COLLECTING=_cfg.get("collecting",True); ACOMP=_cfg.get("acomp",True)
    TH=compute_theme(_cfg.get("theme","auto"))   # 대시보드 색 팔레트
    BLOCKED_APPS.clear(); BLOCKED_APPS.update(_cfg.get("disabled_apps",[]))   # 앱별 자동완성 끔 목록
    try: MAX_SUG=max(3,min(12,int(_cfg.get("max_sug",6) or 6)))   # 제안 개수 복원
    except Exception: MAX_SUG=6
    try: OV_FONT=max(9,min(20,int(_cfg.get("ov_font",11) or 11)))   # 제안 글자 크기 복원
    except Exception: OV_FONT=11
    _today_count=count_today_lines()   # 시작 시 한 번만 읽고, 이후엔 _emit이 센다
    threading.Thread(target=writer,daemon=True).start()
    LISTENER=keyboard.Listener(on_press=on_press,on_release=on_release,win32_event_filter=win_filter)
    LISTENER.start(); debug("리스너 시작")
    threading.Thread(target=caret_tracker,daemon=True).start()

    root=tk.Tk(); ROOT=root; root.title(f"{APP_NAME} v{APP_VERSION}"); root.geometry("400x880"); root.minsize(400,700)
    try:
        _ws=_cfg.get("win_size")
        if _ws: root.geometry(_ws)          # 기억한 창 크기 복원(WxH)
    except Exception: pass
    UIFONT=_pick_font()                     # 맑은 고딕 없으면 대체 폰트로
    root.resizable(False,True); root.configure(bg=TH["bg"])
    build_overlay(root)
    if HAVE_SVTTK:
        try: sv_ttk.set_theme("dark" if TH["dark"] else "light", root)
        except Exception: debug("sv_ttk 적용 실패:\n"+traceback.format_exc())
    F=(UIFONT,10); FB=(UIFONT,11,"bold"); FT=(UIFONT,14,"bold")

    AUTO_COPY=tk.BooleanVar(value=bool(_cfg.get("autocopy",False)))   # 자동복사 상태 복원
    def _save_cfg():
        d=load_settings(); d.update({"collecting":COLLECTING,"acomp":ACOMP,"autocopy":bool(AUTO_COPY.get())}); save_settings(d)

    # 하단 바를 먼저 bottom에 고정 -> 위 내용이 늘어도 절대 잘리지 않는다(기존 '하단 버튼 잘림' 대응)
    bottom=tk.Frame(root,bg=TH["bg"]); bottom.pack(side="bottom",fill="x",pady=(10,10),padx=24)
    def _save_geo():
        try:
            wh=root.geometry().split("+")[0]     # "WxH" (위치 제외 - 오프스크린 방지)
            if "x" in wh:
                d=load_settings(); d["win_size"]=wh; save_settings(d)
        except Exception: pass
    def show_window():
        try: root.deiconify(); root.after(10, lambda:(root.lift(), root.focus_force()))
        except Exception: pass
    def hide_bg():
        # 트레이가 있으면 창을 완전히 숨겨(작업표시줄에서도 사라짐) 트레이로만 남긴다.
        _save_geo()
        if HAVE_TRAY and _TRAY is not None: root.withdraw()
        else: root.iconify()
    def quit_all():
        debug("사용자 종료"); _save_geo()
        try:
            if _TRAY is not None: _TRAY.stop()
        except Exception: pass
        try: root.destroy()
        except Exception: pass
        os._exit(0)
    tk.Button(bottom,text=("트레이로 숨기기" if HAVE_TRAY else "백그라운드로 숨기기"),font=F,command=hide_bg,relief="flat",bg="#e5e7eb",cursor="hand2").pack(side="left",expand=True,fill="x",padx=(0,4))
    tk.Button(bottom,text="종료",font=F,command=quit_all,relief="flat",bg="#fecaca",cursor="hand2").pack(side="left",expand=True,fill="x",padx=(4,0))
    root.protocol("WM_DELETE_WINDOW", quit_all)   # X = 실제 종료

    tk.Label(root,text="⌨  타이핑 도우미",font=FT,bg=TH["bg"],fg=TH["fg"]).pack(pady=(14,2))
    tk.Label(root,text="v"+APP_VERSION,font=(UIFONT,8),bg=TH["bg"],fg=TH["sub"]).pack()
    tk.Label(root,text="입력 중 커서 위 목록 → Tab 채움 · ↑↓ 이동 · Esc 닫기",
             font=(UIFONT,9),bg=TH["bg"],fg=TH["sub"]).pack(pady=(0,2))
    status_var=tk.StringVar(); stat=tk.Label(root,textvariable=status_var,font=FB,bg=TH["bg"]); stat.pack()
    info_var=tk.StringVar(); tk.Label(root,textvariable=info_var,font=F,bg=TH["bg"],fg=TH["sub"]).pack(pady=(2,8))

    def refresh():
        if LISTENER is not None and not LISTENER.is_alive():
            status_var.set("⚠ 키보드 후킹 중단됨 - 앱을 다시 시작하세요"); stat.config(fg="#dc2626")
        else:
            s="● 수집 중" if COLLECTING else "■ 수집 멈춤"
            a="자동완성 ON" if ACOMP else "자동완성 OFF"
            status_var.set(f"{s}   |   {a}"); stat.config(fg="#059669" if COLLECTING else "#dc2626")
        # 예전엔 여기서 오늘자 로그 전체를 1.2초마다 다시 읽었다(파일이 클수록 UI가 느려짐).
        info_var.set(f"오늘 {_today_count}줄 · 표현 {len(PHRASE_LIST)}개" + (f" (★{len(PINNED)})" if PINNED else ""))
        try:
            _fa=_last_fg_app or "(없음)"; _st="꺼짐" if _last_fg_app in BLOCKED_APPS else "켜짐"
            app_var.set(f"직전 앱: {_fa} · 자동완성 {_st}\n끈 앱: {', '.join(sorted(BLOCKED_APPS)) or '없음'}")
        except Exception: pass
        try: _refresh_toggles()
        except Exception: pass
        root.after(1200,refresh)
    def toggle_collect():
        global COLLECTING; COLLECTING=not COLLECTING; _save_cfg(); _refresh_toggles()
    def toggle_acomp():
        global ACOMP; ACOMP=not ACOMP
        if not ACOMP: _set_sug([],"")
        _save_cfg(); _refresh_toggles()
    def mkbtn(parent,txt,cmd,bg="#2563eb",fg="white",side_pad=(0,0)):
        b=tk.Button(parent,text=txt,font=FB,command=cmd,bg=bg,fg=fg,relief="flat",
                    activebackground=bg,cursor="hand2",height=1)
        b.pack(side="left",expand=True,fill="x",padx=side_pad); return b
    def mkrow(pady=3):
        fr=tk.Frame(root,bg=TH["bg"]); fr.pack(fill="x",padx=20,pady=pady); return fr
    # 상태 토글 한 줄
    r_tog=mkrow()
    b_collect=mkbtn(r_tog,"수집", toggle_collect, bg="#374151", side_pad=(0,3))
    b_acomp=mkbtn(r_tog,"자동완성", toggle_acomp, bg="#4b5563", side_pad=(3,0))
    def _refresh_toggles():
        try:
            b_collect.config(text=("● 수집: 켜짐" if COLLECTING else "■ 수집: 꺼짐"),
                             bg=("#059669" if COLLECTING else "#6b7280"),
                             activebackground=("#059669" if COLLECTING else "#6b7280"))
            b_acomp.config(text=("✓ 자동완성: 켜짐" if ACOMP else "✕ 자동완성: 꺼짐"),
                           bg=("#2563eb" if ACOMP else "#6b7280"),
                           activebackground=("#2563eb" if ACOMP else "#6b7280"))
        except Exception: pass
    _refresh_toggles()
    # 열기 한 줄
    r_open=mkrow()
    mkbtn(r_open,"📋 가이드", lambda:_open(GUIDE), side_pad=(0,2))
    mkbtn(r_open,"📁 폴더", lambda:_open(LOG_DIR), side_pad=(2,2))
    mkbtn(r_open,"📝 교정결과", lambda:_open(PHRASES), side_pad=(2,0))
    # 설정 한 줄: 자동시작 + 테마
    r_set=mkrow()
    as_btn=tk.Button(r_set,font=FB,relief="flat",fg="white",cursor="hand2",height=1)
    def _refresh_as():
        on=autostart_enabled()
        as_btn.config(text=("🔌 자동시작: 켜짐" if on else "🔌 자동시작: 꺼짐"),
                      bg=("#0d9488" if on else "#6b7280"), activebackground=("#0d9488" if on else "#6b7280"))
    def toggle_autostart():
        set_autostart(not autostart_enabled()); _refresh_as()
    as_btn.config(command=toggle_autostart); _refresh_as()
    as_btn.pack(side="left",expand=True,fill="x",padx=(0,3))
    _thmap={"auto":"자동","light":"라이트","dark":"다크"}
    th_btn=tk.Button(r_set,font=FB,relief="flat",fg="white",bg="#7c3aed",activebackground="#7c3aed",cursor="hand2",height=1)
    def _cycle_theme():
        order=["auto","light","dark"]; d=load_settings(); cur=d.get("theme","auto")
        nxt=order[(order.index(cur)+1)%3] if cur in order else "auto"
        d["theme"]=nxt; save_settings(d)
        th_btn.config(text="🎨 테마: "+_thmap[nxt])
        try:
            nt=compute_theme(nxt)
            if HAVE_SVTTK: sv_ttk.set_theme("dark" if nt["dark"] else "light", root)
        except Exception: pass
    th_btn.config(command=_cycle_theme, text="🎨 테마: "+_thmap.get(_cfg.get("theme","auto"),"자동"))
    th_btn.pack(side="left",expand=True,fill="x",padx=(3,0))
    # 앱별 자동완성 on/off
    appf=tk.LabelFrame(root,text=" 앱별 자동완성 ",font=F,bg=TH["bg"],fg=TH["sub"],padx=8,pady=4)
    appf.pack(fill="x",padx=16,pady=(2,2))
    app_var=tk.StringVar(value="직전 앱을 확인 중...")
    tk.Label(appf,textvariable=app_var,font=(UIFONT,9),bg=TH["bg"],fg=TH["sub"],
             anchor="w",justify="left",wraplength=340).pack(fill="x")
    def _toggle_app():
        name=_last_fg_app
        if not name:
            app_var.set("직전에 쓰던 다른 앱이 없습니다. 다른 창을 클릭한 뒤 다시 눌러주세요."); return
        if name in BLOCKED_APPS: BLOCKED_APPS.discard(name)
        else: BLOCKED_APPS.add(name)
        try:
            d=load_settings(); d["disabled_apps"]=sorted(BLOCKED_APPS); save_settings(d)
        except Exception: pass
    tk.Button(appf,text="직전 앱에서 자동완성 켜기 / 끄기",font=F,command=_toggle_app,relief="flat",
              bg="#4b5563",fg="white",cursor="hand2").pack(fill="x",pady=(4,0))
    tk.Label(root,text="빠른 토글: Ctrl + Alt + Space",font=(UIFONT,8),bg=TH["bg"],fg=TH["sub"]).pack(pady=(0,2))
    # 제안 개수 + 내보내기/가져오기
    r_io=tk.Frame(root,bg=TH["bg"]); r_io.pack(fill="x",padx=20,pady=(0,4))
    tk.Label(r_io,text="제안 개수",font=F,bg=TH["bg"],fg=TH["sub"]).pack(side="left")
    _ms=tk.IntVar(value=MAX_SUG)
    def _set_maxsug(*_):
        global MAX_SUG
        try: v=int(_ms.get())
        except Exception: return
        v=max(3,min(12,v)); MAX_SUG=v
        try: d=load_settings(); d["max_sug"]=v; save_settings(d)
        except Exception: pass
    tk.Spinbox(r_io,from_=3,to=12,width=3,textvariable=_ms,command=_set_maxsug,
               font=F,justify="center").pack(side="left",padx=(6,10))
    tk.Label(r_io,text="글자 크기",font=F,bg=TH["bg"],fg=TH["sub"]).pack(side="left")
    _fs=tk.IntVar(value=OV_FONT)
    def _set_ovfont(*_):
        global OV_FONT
        try: v=int(_fs.get())
        except Exception: return
        v=max(9,min(20,v)); OV_FONT=v
        try:
            if OVLIST: OVLIST.config(font=(UIFONT,v))
        except Exception: pass
        try: d=load_settings(); d["ov_font"]=v; save_settings(d)
        except Exception: pass
    tk.Spinbox(r_io,from_=9,to=20,width=3,textvariable=_fs,command=_set_ovfont,
               font=F,justify="center").pack(side="left",padx=(6,0))
    def _io_msg(fn):
        try:
            r=fn()
            if r:
                from tkinter import messagebox; messagebox.showinfo("표현 관리", r, parent=root)
                try: refill()
                except Exception: pass
        except Exception: debug("io 실패:\n"+traceback.format_exc())
    tk.Button(r_io,text="⬇ 가져오기",font=F,command=lambda:_io_msg(import_phrases),relief="flat",
              bg="#4b5563",fg="white",cursor="hand2").pack(side="right")
    tk.Button(r_io,text="⬆ 내보내기",font=F,command=lambda:_io_msg(export_phrases),relief="flat",
              bg="#4b5563",fg="white",cursor="hand2").pack(side="right",padx=(0,4))

    # ---- 추천 목록 패널 ----
    panel=tk.LabelFrame(root,text=" 추천 목록 (검색 / 직접 추가) ",font=F,
                        bg=TH["bg"],fg="#374151",padx=8,pady=6)
    panel.pack(fill="both",expand=True,padx=16,pady=(8,4))

    q_var=tk.StringVar()
    q_entry=tk.Entry(panel,textvariable=q_var,font=(UIFONT,12))
    q_entry.pack(fill="x",pady=(2,6))
    _PH="검색어 입력 · 새 문구는 Enter로 추가"           # 흐린 안내(placeholder)
    def _q():
        return "" if getattr(q_entry,"_ph",False) else q_var.get()
    def _clear_ph(*_):
        if getattr(q_entry,"_ph",False):
            q_entry._ph=False; q_entry.delete(0,tk.END)
            try: q_entry.config(fg=TH["listfg"])
            except Exception: pass
    def _set_ph(*_):
        if not q_var.get():
            q_entry._ph=True
            try: q_entry.config(fg=TH["sub"])
            except Exception: pass
            q_entry.insert(0,_PH)
    q_entry.bind("<FocusIn>", _clear_ph, add="+")
    q_entry.bind("<FocusOut>", _set_ph, add="+")

    listwrap=tk.Frame(panel,bg=TH["bg"]); listwrap.pack(fill="both",expand=True)
    sb=tk.Scrollbar(listwrap); sb.pack(side="right",fill="y")
    reco=tk.Listbox(listwrap,font=(UIFONT,12),activestyle="none",
                    bg=TH["listbg"],fg=TH["listfg"],selectbackground="#2563eb",selectforeground="white",
                    highlightthickness=1,highlightbackground="#d1d5db",yscrollcommand=sb.set)
    reco.pack(side="left",fill="both",expand=True); sb.config(command=reco.yview)

    def current_text():
        sel=reco.curselection()
        t = reco.get(sel[0]) if sel else (reco.get(0) if reco.size()>0 else "")
        return t[2:] if t.startswith("★ ") else t
    def refill(*_):
        items=reco_matches(_q().strip())
        reco.delete(0,tk.END)
        for it in items: reco.insert(tk.END, ("★ "+it) if it in PINNED else it)
        if reco.size()>0: reco.selection_clear(0,tk.END); reco.selection_set(0)
        if AUTO_COPY.get() and items and pyperclip:
            try: pyperclip.copy(items[0])
            except Exception: pass
    q_var.trace_add("write",refill)

    def do_copy():
        t=current_text()
        if t and pyperclip:
            try: pyperclip.copy(t)
            except Exception: pass
    def do_paste():
        # 복사 후 대시보드를 숨겨 직전 창으로 포커스를 넘기고, Ctrl+V 를 보낸다.
        global _injecting
        t=current_text()
        if not t: return
        if pyperclip:
            try: pyperclip.copy(t)
            except Exception: pass
        root.iconify()
        def _send():
            time.sleep(0.35); _injecting=True
            try:
                KBD.press(keyboard.Key.ctrl); KBD.press("v"); KBD.release("v"); KBD.release(keyboard.Key.ctrl)
            except Exception: debug("paste fail:\n"+traceback.format_exc())
            time.sleep(0.05); _injecting=False
        threading.Thread(target=_send,daemon=True).start()
    def toggle_autocopy():
        AUTO_COPY.set(not AUTO_COPY.get())
        ac_btn.config(text=("자동복사 ON" if AUTO_COPY.get() else "자동복사 OFF"),
                      bg=("#059669" if AUTO_COPY.get() else "#9ca3af"))
        if AUTO_COPY.get(): do_copy()   # 켜는 즉시 현재 1순위 복사
        _save_cfg()

    reco.bind("<Double-Button-1>", lambda e: do_copy())
    q_entry.bind("<Return>", lambda e: do_add())

    brow=tk.Frame(panel,bg=TH["bg"]); brow.pack(fill="x",pady=(6,0))
    tk.Button(brow,text="복사",font=FB,command=do_copy,relief="flat",bg="#2563eb",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=(0,3))
    tk.Button(brow,text="붙여넣기(Ctrl+Enter)",font=FB,command=do_paste,relief="flat",bg="#7c3aed",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=3)
    ac_btn=tk.Button(brow,text="자동복사 OFF",font=FB,command=toggle_autocopy,relief="flat",
                     bg="#9ca3af",fg="white",cursor="hand2",height=1)
    ac_btn.pack(side="left",expand=True,fill="x",padx=(3,0))

    # 사용자가 직접 표현을 넣고 빼는 줄. 넣는 즉시 phrases.txt에 저장되고 자동완성에 반영된다.
    msg_var=tk.StringVar(value="문구를 쓰고 Enter(또는 ＋표현 추가) → 바로 자동완성에 반영 · 목록 더블클릭=복사")
    def do_add():
        msg_var.set(add_phrase(_q())); q_var.set(""); refill()
    def do_del():
        msg_var.set(del_phrase(current_text())); refill()
    def do_restore():
        msg_var.set(restore_last_deleted()); refill()
    def do_pin():
        msg_var.set(toggle_pin(current_text())); refill()
    arow=tk.Frame(panel,bg=TH["bg"]); arow.pack(fill="x",pady=(4,0))
    tk.Button(arow,text="＋ 추가",font=FB,command=do_add,relief="flat",bg="#059669",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=(0,2))
    tk.Button(arow,text="★ 고정",font=FB,command=do_pin,relief="flat",bg="#d97706",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=2)
    tk.Button(arow,text="삭제",font=FB,command=do_del,relief="flat",bg="#b91c1c",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=2)
    tk.Button(arow,text="↩ 복원",font=FB,command=do_restore,relief="flat",bg="#6b7280",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=(2,0))
    tk.Label(panel,textvariable=msg_var,font=(UIFONT,9),bg=TH["bg"],fg="#6b7280",
             anchor="w",justify="left",wraplength=330).pack(fill="x",pady=(4,0))
    q_entry.bind("<Control-Return>", lambda e: do_paste())

    _set_ph(); refill()   # 시작 시 placeholder 표시
    if not _cfg.get("onboarded"):         # 첫 실행 간단 안내(1회)
        def _onboard():
            try:
                from tkinter import messagebox
                messagebox.showinfo("타이핑 도우미 시작하기",
                    "1) 평소처럼 타이핑하면 커서 위에 추천 목록이 떠요.\n"
                    "2) ↑/↓로 고르고 Tab으로 채웁니다 (Esc로 닫기).\n"
                    "3) 자주 쓰는 문구는 아래 상자에 쓰고 Enter로 추가.\n"
                    "4) Ctrl+Alt+Space로 자동완성을 껐다 켤 수 있어요.\n\n"
                    "표현은 '교정결과(phrases.txt)'로 관리됩니다.", parent=root)
            except Exception: pass
            try:
                d=load_settings(); d["onboarded"]=True; save_settings(d)
            except Exception: pass
        root.after(700,_onboard)
    start_tray(on_open=lambda: post_ui(show_window), on_quit=lambda: post_ui(quit_all),
               on_collect=toggle_collect, on_acomp=toggle_acomp)
    refresh(); overlay_tick(); debug("mainloop 진입"); root.mainloop()

if __name__=="__main__":
    try:
        debug("main 진입"); run_ui()
    except Exception:
        debug("MAIN CRASH:\n"+traceback.format_exc())
