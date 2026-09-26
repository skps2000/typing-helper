# -*- coding: utf-8 -*-
import os, time, threading, traceback, ctypes
from ctypes import wintypes
# 교차 빌드(Wine) 환경의 tcl/tk 경로. 그 경로가 실제로 존재할 때만 설정한다.
# 무조건 setdefault 하면 C:\py311 이 없는 PC에서 소스 실행 시 tk.Tk() 가 죽는다.
for _var, _p in (("TCL_LIBRARY", r"C:\py311\tcl\tcl8.6"), ("TK_LIBRARY", r"C:\py311\tcl\tk8.6")):
    if _var not in os.environ and os.path.isdir(_p): os.environ[_var] = _p
from datetime import datetime, date, timedelta

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
        p=os.path.join(LOG_DIR,"_debug.log")
        try:
            if os.path.getsize(p)>512*1024: open(p,"w",encoding="utf-8").close()   # 상한 넘으면 비움
        except Exception: pass
        with open(p,"a",encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {m}\n")
    except Exception: pass
debug("=== v44(매칭 미세최적화: 경계캐시+풀 1회+최근상한) boot ===")
try:
    from pynput import keyboard
    from pynput.keyboard import Controller
    try: import pyperclip
    except Exception: pyperclip=None
    import tkinter as tk
    import customtkinter as ctk
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
APP_VERSION="0.42.0"
GUIDE=os.path.join(LOG_DIR,"교정프롬프트_가이드.txt")
PHRASES=os.path.join(LOG_DIR,"phrases.txt")
SNIPPETS=os.path.join(LOG_DIR,"상용구.txt")   # 상용구/단축키: 한 줄에 "단축키=문구" 또는 "문구"
FLUSH_IDLE, FLUSH_MAX = 1.5, 200
MIN_PREFIX=2
RECENT_TTL=3600   # 최근 입력을 자동완성 후보로 유지하는 시간(초) = 1시간
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
    if not os.path.exists(SNIPPETS):
        with open(SNIPPETS,"w",encoding="utf-8") as f:
            f.write("# 상용구 / 단축키 - 한 줄에 하나씩.\n")
            f.write("# 형식) 단축키=문구   또는   문구  (단축키 없이 문구만 써도 됩니다)\n")
            f.write("# 자동확장) 타이핑 중 '단축키'를 치고 스페이스/엔터를 누르면 그 자리에서 문구로 바뀝니다.\n")
            f.write("#          (예: ㄱㅅ + 스페이스 -> '감사합니다. 좋은 하루 보내세요.')\n")
            f.write("# 검색) 백틱( ` )을 누르면 검색창이 열려 단축키/문구 일부로 찾아 Enter 삽입.\n")
            f.write("# 예)\n")
            f.write("ㄱㅅ=감사합니다. 좋은 하루 보내세요.\n")
            f.write("확인 후 다시 연락드리겠습니다.\n")

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

# ---- 상용구 / 단축키 ----
SNIPPET_LIST=[]      # [(단축키, 문구)] - 단축키는 비어 있을 수 있다
SNIPPET_TEXTS=[]     # 문구만
SNIPPET_ALIAS={}     # {단축키(표시형): 문구} - 타이핑 중 자동확장용
_snip_mtime=0
def load_snippets():
    global SNIPPET_LIST,SNIPPET_TEXTS,_snip_mtime
    try:
        mt=os.path.getmtime(SNIPPETS)
    except Exception: return
    if mt==_snip_mtime: return
    _snip_mtime=mt
    out=[]; seen=set()
    try:
        with open(SNIPPETS,encoding="utf-8") as f:
            for ln in f:
                s=ln.rstrip("\r\n")
                if not s.strip() or s.lstrip().startswith("#"): continue
                if "=" in s:
                    a,t=s.split("=",1); a=a.strip(); t=t.strip()
                else:
                    a,t="",s.strip()
                if not t or t in seen: continue
                seen.add(t); out.append((a,t))
    except Exception: return
    SNIPPET_LIST=out; SNIPPET_TEXTS=[t for _,t in out]
    global SNIPPET_ALIAS
    SNIPPET_ALIAS={a:t for a,t in out if a}   # 단축키가 있는 것만 자동확장 대상
    debug(f"상용구 {len(out)}개 로드")
def _snippet_alias_hits(q):
    # 검색어 q(원문/조합)가 단축키의 앞부분과 맞으면 그 문구를 돌려준다(단축키 검색).
    if not SNIPPET_LIST or not q: return []
    keys=[q.lower()]
    try:
        h=compose(q).strip().lower()
        if h and h!=keys[0]: keys.append(h)
    except Exception: pass
    out=[]
    for a,t in SNIPPET_LIST:
        al=(a or "").lower()
        if al and any(al.startswith(k) for k in keys): out.append(t)
    return out

# ---- 최근 입력(최근 RECENT_TTL초) 실시간 후보 ----
RECENT={}                      # 문구 -> [횟수, 마지막시각]
_recent_lock=threading.Lock()
def _all_jamo(t):
    return t!="" and all((0x3130<=ord(c)<=0x318F) or c.isspace() for c in t)
def _recent_ok(t):
    t=(t or "").strip()
    if not (4<=len(t)<=80): return False    # 자동완성에 쓸만한 길이만
    if _has_long_digits(t): return False    # 카드/계좌/전화 등 제외
    low=t.lower()
    if "@" in t or "http" in low or "password" in low: return False
    if _all_jamo(t): return False           # 한/영 깨짐(자모만) 제외
    return True
def note_recent(text, now=None):
    # 방금 완결된 입력을 최근 후보로 적립(빈도++). writer 스레드에서 호출.
    t=(text or "").strip()
    if not _recent_ok(t): return
    now=now or time.time()
    with _recent_lock:
        v=RECENT.get(t)
        if v: v[0]+=1; v[1]=now
        else: RECENT[t]=[1,now]
        if len(RECENT)>200:                    # 상한: 오래된 것부터 정리(정렬 비용·메모리 억제)
            for k in sorted(RECENT, key=lambda k:RECENT[k][1])[:len(RECENT)-200]:
                RECENT.pop(k,None)
def recent_active(now=None):
    # 만료(1시간 초과) 제거 후, 자주/최근 순으로 정렬된 문구 목록.
    now=now or time.time(); cut=now-RECENT_TTL
    with _recent_lock:
        for k in [k for k,v in RECENT.items() if v[1]<cut]: RECENT.pop(k,None)
        return sorted(RECENT.keys(), key=lambda k:(-RECENT[k][0], -RECENT[k][1]))
def _recent_rank(t):
    v=RECENT.get(t); return v[0] if v else 0
def _match_pool():
    # 매칭/검색 후보 풀: 최근입력(핫) + 상용구 + 저장표현(중복 제거, 이 순서로 우선).
    r=recent_active()
    seen=set(r); base=list(r)
    for t in SNIPPET_TEXTS:
        if t not in seen: seen.add(t); base.append(t)
    return base+[p for p in PHRASE_LIST if p not in seen] if base else list(PHRASE_LIST)
def seed_recent():
    # 시작 시 오늘 로그에서 최근 1시간 입력을 복원(재시작해도 이어지게).
    import re
    try:
        now=time.time(); td=date.today()
        with open(mainpath(),encoding="utf-8") as f:
            for ln in f:
                m=re.match(r"^\[(\d\d):(\d\d):(\d\d)\](?:\s*\[[^\]]*\])?\s?(.*)$", ln.rstrip("\r\n"))
                if not m: continue
                txt=m.group(4).strip()
                if not txt: continue
                try: ts=datetime(td.year,td.month,td.day,int(m.group(1)),int(m.group(2)),int(m.group(3))).timestamp()
                except Exception: continue
                if 0<=now-ts<=RECENT_TTL: note_recent(txt, ts)
    except Exception: pass
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
LIGHT_MODE=False   # 가벼운 모드: 커서 앞 텍스트 UIA 읽기를 생략(부담↓, 키 입력 매칭만)
def _dir_size(path):
    # 폴더 내 파일 총 크기(바이트). 데이터 용량 표시용.
    t=0
    try:
        for fn in os.listdir(path):
            fp=os.path.join(path,fn)
            try:
                if os.path.isfile(fp): t+=os.path.getsize(fp)
            except Exception: pass
    except Exception: pass
    return t
def extract_candidates(root=None, limit=200, min_len=6, max_len=42):
    # 수집 로그(typing_*)에서 자동완성용 표현 후보를 뽑아 정제한다.
    # 민감정보/조합깨짐/짧거나 너무 긴 것/이미 있는 표현을 제외하고 빈도순 정렬.
    import re, glob
    from collections import Counter
    root=root or LOG_DIR
    JAMO=re.compile(r"[\u3130-\u318F]"); HANGUL=re.compile(r"[가-힣]")
    def bad(t):
        tl=t.lower()
        if "@" in t or "http" in tl or "www." in tl: return True
        if re.search(r"\d{4,}", t.replace(" ","").replace("-","")): return True
        if any(k in tl for k in ("password","비번","비밀번호","otp","인증","카드","계좌","주민")): return True
        if re.search(r"\d", t) and re.search(r"[!@#$%^&*]", t): return True   # 비번류
        if JAMO.search(t): return True                                        # 한/영 깨짐
        han=len(HANGUL.findall(t))
        if han < max(3, len(t)*0.4): return True                             # 한글 비율 낮음
        return False
    cnt=Counter()
    for fp in glob.glob(os.path.join(root,"typing_*.txt")):
        try:
            for ln in open(fp,encoding="utf-8"):
                m=re.match(r"^\[\d\d:\d\d:\d\d\]\s?(.*)$", ln.rstrip("\r\n"))
                if not m: continue
                t=m.group(1).strip()
                if not t or t.startswith("[복사됨]") or t.startswith("[붙여넣기]"): continue
                if not (min_len<=len(t)<=max_len): continue
                if bad(t): continue
                cnt[t]+=1
        except Exception: pass
    have=set(PHRASE_LIST)
    return [t for t,_ in sorted(cnt.items(), key=lambda kv:(-kv[1], len(kv[0]))) if t not in have][:limit]
def _clean_old_logs(days=30, root=None, today=None):
    # typing_/raw_ 로그 중 파일명 날짜가 오래된 것 삭제. days<=0이면 아무것도 안 함.
    import re
    if not days or days<=0: return 0
    root=root or LOG_DIR; today=today or date.today()
    cutoff=today-timedelta(days=days); n=0
    try:
        for fn in os.listdir(root):
            m=re.match(r"(?:typing|raw)_(\d{4}-\d{2}-\d{2})\.txt$", fn)
            if not m: continue
            try: d=date.fromisoformat(m.group(1))
            except Exception: continue
            if d<cutoff:
                try: os.remove(os.path.join(root,fn)); n+=1
                except Exception: pass
    except Exception: pass
    return n
_BOUND={}
def _bounds(p):
    # 표현의 단어경계 오프셋([0] + 공백 다음 위치들)을 표현별로 캐시(매칭 때마다 재계산 방지).
    b=_BOUND.get(p)
    if b is None:
        if len(_BOUND)>4000: _BOUND.clear()   # 무한 성장 방지(세션 장기 사용)
        b=[0]+[i+1 for i,c in enumerate(p) if c==" "]
        _BOUND[p]=b
    return b
def _match_from_boundary(prefix, n, pool=None):
    # 각 표현에서 '단어 경계'(맨 앞 또는 공백 다음)에 prefix가 오는 가장 이른 위치를 찾아
    # 그 위치부터 끝까지(꼬리)를 후보로 낸다. 예) prefix="너한테",
    # "켜고 너한테 말하는 거야..." -> 후보 "너한테 말하는 거야..."
    L=len(prefix); pl=prefix.lower(); seen=set(); ranked=[]
    for p in (pool if pool is not None else _match_pool()):   # 최근입력(핫) + 상용구 + 저장표현
        positions=_bounds(p)         # 단어경계 위치(표현별 캐시)
        for pos in positions:
            tail=p[pos:]
            if len(tail)>L and (tail.startswith(prefix) or tail.lower().startswith(pl)):
                if tail not in seen:
                    seen.add(tail)
                    # 고정 > 최근핫 > 자주쓴것 > 시작 > 짧은것
                    ranked.append((1 if _is_pinned(tail) else 0, _recent_rank(tail), _usage_of(tail), 0 if pos==0 else 1, len(tail), tail))
                break   # 한 표현에서 가장 이른 경계만 사용
    ranked.sort(key=lambda x:(-x[0],-x[1],-x[2],x[3],x[4]))
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
def _matches_for(text, n=MAX_SUG, min_prefix=1, pool=None):
    # 접두사(text)에 접미 백오프 + 단어경계 매칭. (후보목록, 매칭접두사) 반환.
    if not text: return [], ""
    if pool is None: pool=_match_pool()          # 풀은 한 번만 만들어 재사용(재정렬/재구성 방지)
    for prefix in _suffix_candidates(text):
        if len(prefix)<min_prefix: continue
        hits=_match_from_boundary(prefix, n, pool)
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
    if len(cur_latin)<MIN_PREFIX: return [], ""
    pool=_match_pool()           # 풀을 한 번만 만들어 두 base 매칭에 공유
    for base in (compose(cur_latin), cur_latin):
        items,pref=_matches_for(base, n, pool=pool)
        if items: return items, pref
    return [], ""
def reco_matches(q, k=40):
    """대시보드 추천창용 - 사용자가 상자에 입력한 질의(q)로 표현 목록을 걸러 정렬한다.
    한글 IME로 직접 친 질의와 영문 자판(dkssud)으로 친 질의를 모두 처리한다.
    앞부분 일치를 먼저, 그 다음 부분 문자열 포함 순으로 돌려준다."""
    pool=_match_pool()                     # 최근입력 + 상용구 + 저장표현
    if not q: return pool[:k]
    ql=q.lower()
    qh=compose(q) if q.isascii() else q   # 영문 자판이면 한글로 조합해 본다
    cho_q=q if _is_chosung_query(q) else (qh if _is_chosung_query(qh) else "")  # 초성 검색
    alias=_snippet_alias_hits(q)          # 단축키로 상용구 찾기
    pre=[]; sub=[]; cho=[]
    for p in pool:
        pl=p.lower()
        if p.startswith(q) or (qh and p.startswith(qh)) or pl.startswith(ql): pre.append(p)
        elif q in p or (qh and qh in p) or ql in pl: sub.append(p)
        elif cho_q and _chosung(p).startswith(cho_q): cho.append(p)   # ㅂㄹㅍ -> 브리핑
    results=[]; seen=set()
    for grp in (alias, pre, sub, cho):
        for p in grp:
            if p not in seen: seen.add(p); results.append(p)
    if len(results)<k:                                   # 오타 허용(RapidFuzz)로 보강
        try:
            from rapidfuzz import process, fuzz
            rest=[p for p in pool if p not in seen]
            for cand,score,_ in process.extract(qh or q, rest, scorer=fuzz.WRatio,
                                                 limit=k-len(results), score_cutoff=70):
                results.append(cand)
        except Exception: pass
    results.sort(key=lambda p: p not in PINNED)   # 고정(★) 표현을 위로(안정 정렬)
    return results[:k]
def _sorted_for_display(items, mode):
    # 대시보드 추천 목록 정렬. 고정(★)은 항상 위. mode: 관련도/가나다/최근
    if mode=="가나다": return sorted(items, key=lambda p:(p not in PINNED, p))
    if mode=="최근":   return sorted(items, key=lambda p:(p not in PINNED, -(PHRASE_LIST.index(p) if p in PHRASE_LIST else 0)))
    return items       # 관련도(기본): reco_matches 순서 유지
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
_dismiss=False        # ESC로 목록을 닫음 - 다시 '타이핑'하기 전까지 재노출 안 함
OUR_PID=ctypes.windll.kernel32.GetCurrentProcessId()  # 우리 창엔 제안하지 않기 위한 식별
# 커서 위 제안 목록 상태. 리스너/훅 스레드는 값만 바꾸고 ver를 올리며,
# 실제 그리기는 Tk 메인루프의 overlay_tick 이 맡는다(스레드 간 Tk 호출 제거).
S={"items":[],"idx":0,"pref":"","rem":"","ver":0,"close":False}
KBD=Controller(); LISTENER=None; ROOT=None
VK_C,VK_V,VK_X,VK_TAB,VK_ESC=67,86,88,9,27
VK_UP,VK_DOWN=38,40
VK_BQ=0xC0   # 백틱( ` ) = VK_OEM_3 -> 상용구/문구 검색 팝업 트리거
VK_SPACE,VK_RETURN=0x20,0x0D   # 단축키 자동확장 트리거(스페이스/엔터)
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
    global _ctrl,_last_input,_paste,_injecting,_last_key,_alt,_dismiss
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
            _cur.clear(); request_sug()
            return
        ch=getattr(key,"char",None)
        if ch=="`":                 # 백틱은 상용구 검색 트리거 - 수집/버퍼에 넣지 않는다
            _cur.clear(); request_sug(); return
        # 목록이 떠 있는 동안의 ↑/↓ 는 '목록 탐색'이다(이동은 win_filter가 처리).
        # 여기서 _cur를 지우거나 제안을 다시 계산하면 선택이 0번으로 리셋돼 연속 이동이 안 된다.
        if key in (keyboard.Key.up,keyboard.Key.down) and ACOMP and S["items"] and not _self_focused and not _in_password:
            return
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
        elif ch is not None: _dismiss=False; _cur.append(ch)      # 다시 타이핑 -> 목록 재개
        elif key==keyboard.Key.space: _dismiss=False; _cur.append(" ")
        elif key==keyboard.Key.backspace:
            _cur.clear()   # 한글 1자=영문 여러타라 하나만 pop하면 어긋남 -> 통째로 비움
        elif key==keyboard.Key.esc: _cur.clear(); _dismiss=True   # ESC -> 다시 칠 때까지 숨김
        elif key==keyboard.Key.enter: _cur.clear()
        elif key not in _KEEP_CUR: _cur.clear()   # 방향키·Home/End 등 캐럿 이동 시
        request_sug()                              # 계산은 워커에서 - 여기선 즉시 반환
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
    if _dismiss or _self_focused or _in_password or _app_blocked or not ACOMP: _set_sug([],""); return
    try: _cur_s="".join(_cur)      # 훅/COM 두 스레드가 부르므로 동시변경 대비 스냅샷
    except Exception: _cur_s=""
    items,pref=top_matches(_cur_s)                     # 키 입력 조합(즉각)
    if not items and USE_UIA_PREFIX and _uia_prefix:   # 버퍼가 비었/어긋났으면 실제 텍스트로 보정
        items,pref=_matches_for(_uia_prefix, MAX_SUG, min_prefix=2)
    _set_sug(items,pref)          # 글자를 더 치면 선택은 항상 첫 항목으로
# 제안 계산은 전용 워커에서만 한다 -> on_press(리스너 스레드)는 버퍼만 갱신하고 즉시 반환.
# 어떤 경우에도 키 입력 처리가 매칭 비용을 기다리지 않게 한다(타이핑 무방해 보장).
_sug_event=threading.Event()
def request_sug():
    _sug_event.set()
def _sug_worker():
    while True:
        try:
            _sug_event.wait(); _sug_event.clear()   # 여러 키가 몰리면 최신 상태로 한 번만 계산(코얼레싱)
            _update_sug()
        except Exception: debug("sug worker 예외:\n"+traceback.format_exc())
        time.sleep(0.008)                            # 폭주 입력을 살짝 합쳐 CPU 절약(체감 지연 없음)
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

def _alias_expand_for():
    # 지금 치고 있는 마지막 낱말이 단축키와 정확히 일치하면 (지울 글자 수, 문구)를 돌려준다.
    # 한글 조합 결과(compose)가 화면 표시와 같으므로 그 길이만큼만 지운다.
    if not SNIPPET_ALIAS: return None
    try: raw="".join(_cur)
    except Exception: return None
    tok=raw.split(" ")[-1]        # 마지막 공백 이후 = 현재 낱말
    if not tok: return None
    hang=compose(tok)             # 한글 모드에서 화면에 보이는 형태
    for disp in (hang, tok):      # 한글 별칭 우선, 그다음 영문/기호 별칭
        t=SNIPPET_ALIAS.get(disp)
        if t is not None and disp: return (len(disp), t)
    return None
def do_expand(dellen, text, add_enter):
    # 단축키 자리(dellen 글자)를 지우고 문구를 삽입한 뒤 트리거(스페이스/엔터)를 다시 넣는다.
    global _injecting,_last_clip
    _injecting=True
    try:
        for _ in range(max(0,dellen)):
            KBD.press(keyboard.Key.backspace); KBD.release(keyboard.Key.backspace)
        time.sleep(0.01)
        if len(text)>=6 and pyperclip:      # 긴 문구는 클립보드 붙여넣기
            orig=None
            try: orig=pyperclip.paste()
            except Exception: orig=None
            _last_clip=text
            pyperclip.copy(text); time.sleep(0.02)
            KBD.press(keyboard.Key.ctrl); KBD.press("v"); KBD.release("v"); KBD.release(keyboard.Key.ctrl)
            time.sleep(0.12)
            if orig is not None:
                try: pyperclip.copy(orig); _last_clip=orig
                except Exception: pass
        else:
            KBD.type(text)
        if add_enter:
            KBD.press(keyboard.Key.enter); KBD.release(keyboard.Key.enter)
        else:
            KBD.type(" ")                    # 눌렀던 스페이스 복원
    except Exception:
        debug("expand fail:\n"+traceback.format_exc())
    time.sleep(0.02); _injecting=False
    _cur.clear(); _set_sug([],"",close=True)
    try: record_use(text)
    except Exception: pass

def win_filter(msg, data):
    # suppress_event()는 값을 반환하지 않고 SuppressException(Exception 상속)을 '발생'시켜
    # pynput에 억제를 알린다. 따라서 두 가지를 지켜야 한다.
    #  (1) 삽입 스레드를 먼저 띄운다 - 예외가 나면 그 뒤 줄은 실행되지 않는다.
    #  (2) 그 호출을 try/except Exception 으로 감싸지 않는다 - 감싸면 억제가 사라져
    #      Tab이 앱으로 그대로 새고, 삽입도 일어나지 않는다(기존 버그).
    # 저수준 훅 콜백이라 여기서는 Tk를 절대 호출하지 않는다(훅 타임아웃 방지).
    exp=None
    try:
        if msg not in (256,260) or LISTENER is None or _injecting: return  # 우리가 넣는 키는 무시
        vk=getattr(data,"vkCode",0)
        _ok=(ACOMP and not _in_password and not _self_focused)
        if vk==VK_BQ:                      # 백틱: 상용구/문구 검색 팝업
            if not _ok: return
            act="pick"
        elif vk in (VK_SPACE,VK_RETURN):   # 단축키 자동확장 트리거
            act=None
            if _ok:
                exp=_alias_expand_for()
                if exp: act="expand"
            if act is None: return         # 일반 스페이스/엔터는 그대로 통과
        elif not ACOMP or not S["items"]: return
        elif vk==VK_TAB: act="tab"
        elif vk==VK_UP: act="up"
        elif vk==VK_DOWN: act="down"
        elif vk==VK_ESC: act="esc"
        else: return
    except Exception:
        debug("filter err:\n"+traceback.format_exc()); return
    # 억제(suppress_event)는 예외를 던지므로 try 밖에서 호출해야 전파된다.
    if act=="pick": post_ui(open_picker)
    elif act=="expand":
        d,t=exp; threading.Thread(target=do_expand,args=(d,t,vk==VK_RETURN),daemon=True).start()
    elif act=="tab": threading.Thread(target=do_insert,daemon=True).start()
    elif act=="up": move_sel(-1)
    elif act=="down": move_sel(1)
    elif act=="esc":
        global _dismiss; _dismiss=True   # ESC -> 다시 타이핑 전까지 재노출 안 함(on_press가 억제로 안 불릴 수 있어 여기서도 세움)
        _set_sug([],"",close=True)
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
_uia_stat={"last_log":0.0}
def _uia_log(dt, parts):
    # UIA 한 사이클이 느릴 때만(15ms↑) + 2초 스로틀로 _debug.log에 단계별 소요를 남긴다.
    # 어느 앱에서 무엇이 느린지 실측용(부하 거의 없음: 임계 미만이면 즉시 반환).
    if dt<0.015: return
    now=time.time()
    if now-_uia_stat["last_log"]<2.0: return
    _uia_stat["last_log"]=now
    br=" ".join("%s=%.1f"%(k,v*1000) for k,v in parts.items() if v>=0.001)
    debug("[UIA 느림] total=%.1fms %s app=%s"%(dt*1000, br, _last_fg_app or "?"))
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
            if not ACOMP:
                _in_password=False; time.sleep(0.4); continue
            # 유휴(최근 타이핑도 없고 목록도 없음)면 UIA를 '전혀' 호출하지 않는다.
            # 이게 포커스된 앱(브라우저/오피스 등)이 느려지던 주원인이었다.
            active=bool(S["items"]); recent=(time.time()-_last_key)<2.0
            if not (active or recent):
                time.sleep(0.4); continue
            fg=u32.GetForegroundWindow(); u32.GetWindowThreadProcessId(fg, ctypes.byref(fg_pid))
            if fg_pid.value==OUR_PID:                  # 우리 대시보드엔 제안/수집하지 않는다
                _self_focused=True
                if _uia_prefix: _uia_prefix=""
                if S["items"]: _set_sug([],"",close=True)
                _in_password=False; time.sleep(0.2); continue
            _self_focused=False
            pid=fg_pid.value
            if pid!=_fg_pid_cache:
                _fg_pid_cache=pid; _last_fg_app=_proc_name(pid)   # 포커스 앱 실행파일명 캐시
            _app_blocked=_last_fg_app in BLOCKED_APPS
            if _app_blocked:                           # 이 앱은 자동완성 끔
                if _uia_prefix: _uia_prefix=""
                if S["items"]: _set_sug([],"",close=True)
                time.sleep(0.2); continue
            t0=time.perf_counter(); parts={}
            el=uia.GetFocusedElement(); parts["focus"]=time.perf_counter()-t0
            try: pw=bool(el.CurrentIsPassword) if el is not None else False   # 비밀번호 필드?
            except Exception: pw=False
            _in_password=pw
            if pw:                                     # 비번칸: 아무것도 읽지/제안하지 않음
                if _uia_prefix: _uia_prefix=""
                time.sleep(0.2); continue
            # 필요한 것만 조회한다:
            #  - 위치(want_pos): 목록이 떠 있을 때만(오버레이 배치용)
            #  - 텍스트(want_text): 키 버퍼가 비었/짧아 보정이 필요할 때만. 이 GetText가 가장 무거워
            #    정상 타이핑(버퍼 정상) 중엔 건너뛴다 → 포커스 앱 렉의 주원인 제거.
            want_pos=active
            try: _curlen=len(_cur)
            except Exception: _curlen=0
            want_text=(not LIGHT_MODE) and (_curlen<MIN_PREFIX)
            xy=None; newp=""; got_text=False
            if el is not None and (want_pos or want_text):
                try:
                    ts=time.perf_counter(); tp=el.GetCurrentPattern(TPID); parts["pat"]=time.perf_counter()-ts
                    if tp:
                        ts=time.perf_counter(); sel=tp.QueryInterface(ITP).GetSelection(); parts["sel"]=time.perf_counter()-ts
                        if sel and sel.Length>0:
                            r0=sel.GetElement(0)
                            if want_pos:
                                ts=time.perf_counter()
                                v=list(r0.GetBoundingRectangles())
                                if len(v)>=4: xy=(int(v[0])+2, int(v[1]+v[3])+2)
                                parts["pos"]=time.perf_counter()-ts
                            if want_text:              # 커서 앞 현재 줄 텍스트(무거움 - 필요할 때만)
                                ts=time.perf_counter()
                                try:
                                    rng=r0.Clone(); rng.MoveEndpointByUnit(EP_START,U_LINE,-1)
                                    newp=_line_before_caret(rng.GetText(120)); got_text=True
                                    if newp and not _logged: debug("UIA 텍스트 보정 사용 시작"); _logged=True
                                except Exception: pass
                                parts["text"]=time.perf_counter()-ts
                except Exception: pass
                if xy is None and want_pos:
                    try:
                        r=el.CurrentBoundingRectangle
                        if r.right>r.left: xy=(int(r.left)+6, int(r.bottom)+2)
                    except Exception: pass
            if xy: _caret_xy=xy
            if got_text and newp!=_uia_prefix:         # 실제 텍스트가 바뀌면(마우스/편집/삭제) 반영
                _uia_prefix=newp
                if time.time()-_last_key<1.5: request_sug()   # 최근 타이핑 중일 때만 능동 표시(계산은 워커)
            _uia_log(time.perf_counter()-t0, parts)
        except Exception: pass
        time.sleep(0.05 if S["items"] else 0.12)

# ---- 수집 writer ----
def _emit(mf,rf,han,raw,tag=""):
    global _last_written,_today_count
    if han==_last_written: return
    _last_written=han
    ts=f"[{datetime.now():%H:%M:%S}]"; t=f" [{tag}]" if tag else ""
    mf.write(f"{ts}{t} {han}\n"); rf.write(f"{ts}{t} {raw}\n"); mf.flush(); rf.flush()
    _today_count+=1
    if not tag: note_recent(han)   # 방금 친 문장을 최근 1시간 자동완성 후보로 즉시 적립
import re as _re
_SENT=_re.compile(r"[^\n.!?。…]*[\n.!?。…]+")   # 경계로 끝나는 한 덩어리(연속 부호는 함께)
def _split_sentences(raw, final=False):
    # 완결 문장 리스트와 남은 조각(remainder)을 돌려준다. final=True면 남은 조각도 완결로 취급.
    parts=_SENT.findall(raw)
    consumed=sum(len(p) for p in parts); remainder=raw[consumed:]
    out=[]
    for p in parts:
        t=p.strip().strip("\n").strip()   # 줄바꿈 경계는 제거(문장부호는 유지)
        if t: out.append(t)
    if final and remainder.strip():
        out.append(remainder.strip()); remainder=""
    return out, ("" if final else remainder.lstrip())
def flush(mf,rf, final=False):
    global _buf
    with _lock:
        if not _buf: return
        segs, remainder = _split_sentences("".join(_buf), final)
        _buf=[remainder] if remainder else []
    for line in segs:
        _emit(mf,rf,compose(line),line)
def writer():
    global _paste,_last_clip,_today_count,_clip_seq
    try:
        cur=date.today(); mf=open(mainpath(),"a",encoding="utf-8"); rf=open(rawpath(),"a",encoding="utf-8")
    except Exception:
        debug("writer 시작 실패:\n"+traceback.format_exc()); return
    while True:
        try:      # 루프 본문을 감싸 일시 오류(파일 잠김/클립보드 오류 등)에도 수집이 멈추지 않게
            time.sleep(0.4); load_phrases(); load_snippets()
            if date.today()!=cur:
                flush(mf,rf,final=True); mf.close(); rf.close(); cur=date.today()
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
                            flush(mf,rf,final=True); one=clip.replace("\n"," ⏎ ")
                            _emit(mf,rf,one,one,"복사됨")
            if _paste:
                _paste=False; cp=(_last_clip or "")
                if cp and len(cp)<=2000 and not _has_long_digits(cp):
                    flush(mf,rf,final=True); one=cp.replace("\n"," ⏎ ")
                    _emit(mf,rf,one,one,"붙여넣기")
            with _lock: bt="".join(_buf)
            if bt:
                if any(c in bt for c in "\n.!?。…"): flush(mf,rf,final=False)   # 완결 문장 즉시 저장
                if time.time()-_last_input>=FLUSH_IDLE or len(bt)>=FLUSH_MAX: flush(mf,rf,final=True)
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
    _ov_hover=[-1]
    def _ov_reset(i):
        if 0<=i<OVLIST.size():
            try: OVLIST.itemconfig(i, background=OVLIST.cget("bg"), foreground=OVLIST.cget("fg"))
            except Exception: pass
    def _on_ov_motion(e):
        try:
            i=OVLIST.nearest(e.y)
            if i==_ov_hover[0]: return
            _ov_reset(_ov_hover[0]); _ov_hover[0]=i
            if 0<=i<OVLIST.size(): OVLIST.itemconfig(i, background="#374151", foreground="white")
        except Exception: pass
    def _on_ov_leave(e):
        _ov_reset(_ov_hover[0]); _ov_hover[0]=-1
    OVLIST.bind("<Motion>", _on_ov_motion)
    OVLIST.bind("<Leave>", _on_ov_leave)
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

# ---- 상용구/문구 검색 팝업(백틱 트리거) ----
PICK=None; PK_ENTRY=None; PK_LIST=None; PK_VAR=None; _pick_target=0
def build_picker(root):
    global PICK,PK_ENTRY,PK_LIST,PK_VAR
    dark=(ctk.get_appearance_mode()=="Dark")
    bg="#0f172a" if dark else "#ffffff"; fg="#e5e7eb" if dark else "#111827"
    ebg="#1b2130" if dark else "#f1f3f6"; bd="#2563eb"; sub="#94a3b8" if dark else "#6b7280"
    PICK=tk.Toplevel(root); PICK.withdraw(); PICK.overrideredirect(True); PICK.attributes("-topmost",True)
    PICK.configure(bg=bd)
    wrap=tk.Frame(PICK,bg=bg); wrap.pack(fill="both",expand=True,padx=2,pady=2)
    tk.Label(wrap,text=" 상용구·문구 검색   ↑↓ 이동 · Enter 삽입 · Esc 닫기",bg=bg,fg=sub,
             font=(UIFONT,9),anchor="w").pack(fill="x",pady=(3,1))
    PK_VAR=tk.StringVar()
    PK_ENTRY=tk.Entry(wrap,textvariable=PK_VAR,font=(UIFONT,13),bg=ebg,fg=fg,insertbackground=fg,relief="flat")
    PK_ENTRY.pack(fill="x",padx=5,pady=(0,4),ipady=6)
    PK_LIST=tk.Listbox(wrap,font=(UIFONT,12),height=8,bg=bg,fg=fg,selectbackground="#2563eb",
                       selectforeground="white",relief="flat",highlightthickness=0,activestyle="none")
    PK_LIST.pack(fill="both",expand=True,padx=5,pady=(0,5))
    def _fill(items):
        PK_LIST.delete(0,tk.END)
        for it in items: PK_LIST.insert(tk.END,"  "+it)
        if PK_LIST.size(): PK_LIST.selection_clear(0,tk.END); PK_LIST.selection_set(0)
    def _refill(*_):
        q=PK_VAR.get().strip()
        try: _fill(reco_matches(q,60) if q else _match_pool()[:60])
        except Exception: debug("picker refill:\n"+traceback.format_exc())
    PK_VAR.trace_add("write",_refill)
    def _move(d):
        n=PK_LIST.size()
        if not n: return "break"
        cur=PK_LIST.curselection(); i=(cur[0] if cur else 0)+d; i=max(0,min(n-1,i))
        PK_LIST.selection_clear(0,tk.END); PK_LIST.selection_set(i); PK_LIST.see(i); return "break"
    def _sel():
        s=PK_LIST.curselection()
        if not s and PK_LIST.size(): s=(0,)
        if not s: return ""
        t=PK_LIST.get(s[0]); return t[2:] if t.startswith("  ") else t
    def _go(*_):
        t=_sel(); hide_picker()
        if t: _pick_insert(t)
        return "break"
    def _esc(*_): hide_picker(); return "break"
    for w in (PK_ENTRY,PK_LIST):
        w.bind("<Down>", lambda e:_move(1)); w.bind("<Up>", lambda e:_move(-1))
        w.bind("<Return>", _go); w.bind("<Escape>", _esc)
    PK_LIST.bind("<Double-Button-1>", _go)
    PICK.bind("<FocusOut>", lambda e: PICK.after(120, _focus_guard))
    PICK.withdraw()
def _focus_guard():
    # 팝업 밖을 누르면 닫는다(포커스가 팝업 밖으로 나갔을 때만).
    try:
        if PICK and PICK.winfo_viewable() and PICK.focus_displayof() is None: hide_picker()
    except Exception: pass
def hide_picker():
    try:
        if PICK: PICK.withdraw()
    except Exception: pass
def open_picker():
    global _pick_target
    if PICK is None: return
    try: _pick_target=u32.GetForegroundWindow()
    except Exception: _pick_target=0
    try:
        PK_VAR.set("")
        PK_LIST.delete(0,tk.END)
        for it in _match_pool()[:60]: PK_LIST.insert(tk.END,"  "+it)
        if PK_LIST.size(): PK_LIST.selection_set(0)
    except Exception: pass
    xy=_caret_xy or caret_xy() or (500,400); x,y=xy
    w,h=320,280
    try:
        sw=PICK.winfo_screenwidth(); sh=PICK.winfo_screenheight()
        if x+w>sw: x=max(0,sw-w-6)
        if y+h>sh: y=max(0,y-h-24)
    except Exception: pass
    try:
        PICK.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
        PICK.deiconify(); PICK.lift()
        PICK.after(20, lambda:(PICK.focus_force(), PK_ENTRY.focus_set(), PK_ENTRY.selection_range(0,"end")))
    except Exception: debug("open_picker:\n"+traceback.format_exc())
def _pick_insert(text):
    # 선택한 문구를 직전에 쓰던 앱에 삽입(클립보드 붙여넣기, 실패 시 타이핑).
    global _injecting,_last_clip
    if not text: return
    try:
        if _pick_target: u32.SetForegroundWindow(_pick_target)
    except Exception: pass
    def _send():
        global _injecting,_last_clip
        time.sleep(0.12); _injecting=True
        try:
            if pyperclip:
                try: orig=pyperclip.paste()
                except Exception: orig=None
                _last_clip=text
                pyperclip.copy(text); time.sleep(0.03)
                KBD.press(keyboard.Key.ctrl); KBD.press("v"); KBD.release("v"); KBD.release(keyboard.Key.ctrl)
                time.sleep(0.12)
                if orig is not None:
                    try: pyperclip.copy(orig); _last_clip=orig
                    except Exception: pass
            else:
                KBD.type(text)
            i=text.find("{"); j=(text.find("}",i) if i>=0 else -1)   # 자리표시자 {..} 이동
            if 0<=i<j:
                for _ in range(len(text)-(j+1)): KBD.press(keyboard.Key.left); KBD.release(keyboard.Key.left)
                KBD.press(keyboard.Key.shift)
                for _ in range(j-i+1): KBD.press(keyboard.Key.left); KBD.release(keyboard.Key.left)
                KBD.release(keyboard.Key.shift)
        except Exception:
            debug("pick insert:\n"+traceback.format_exc())
            try: KBD.type(text)
            except Exception: pass
        time.sleep(0.03); _injecting=False
        try: record_use(text)
        except Exception: pass
    threading.Thread(target=_send,daemon=True).start()

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
    global LISTENER,ROOT,_today_count,COLLECTING,ACOMP,MAX_SUG,OV_FONT,UIFONT,LIGHT_MODE
    single_instance()
    ensure_files(); load_phrases(); load_snippets(); load_usage(); load_pinned()
    _cfg=load_settings(); COLLECTING=_cfg.get("collecting",True); ACOMP=_cfg.get("acomp",True)
    TH=compute_theme(_cfg.get("theme","auto"))   # 대시보드 색 팔레트
    BLOCKED_APPS.clear(); BLOCKED_APPS.update(_cfg.get("disabled_apps",[]))   # 앱별 자동완성 끔 목록
    try: MAX_SUG=max(3,min(12,int(_cfg.get("max_sug",6) or 6)))   # 제안 개수 복원
    except Exception: MAX_SUG=6
    try: OV_FONT=max(9,min(20,int(_cfg.get("ov_font",11) or 11)))   # 제안 글자 크기 복원
    except Exception: OV_FONT=11
    LIGHT_MODE=bool(_cfg.get("light_mode",False))                   # 가벼운 모드 복원
    try: _clean_old_logs(int(_cfg.get("log_keep_days",30) or 0))    # 시작 시 오래된 로그 정리
    except Exception: pass
    _today_count=count_today_lines()   # 시작 시 한 번만 읽고, 이후엔 _emit이 센다
    seed_recent()                      # 오늘 로그의 최근 1시간 입력을 자동완성 후보로 복원
    threading.Thread(target=writer,daemon=True).start()
    LISTENER=keyboard.Listener(on_press=on_press,on_release=on_release,win32_event_filter=win_filter)
    LISTENER.start(); debug("리스너 시작")
    threading.Thread(target=_sug_worker,daemon=True).start()   # 제안 계산 워커(입력 스레드와 분리)
    threading.Thread(target=caret_tracker,daemon=True).start()

    try: ctk.set_default_color_theme("blue")
    except Exception: pass
    root=ctk.CTk(); ROOT=root; root.title(f"{APP_NAME} v{APP_VERSION}"); root.geometry("384x330"); root.minsize(360,300)
    try: ctk.set_appearance_mode({"auto":"system","light":"light","dark":"dark"}.get(_cfg.get("theme","auto"),"system"))
    except Exception: pass
    UIFONT=_pick_font()
    root.resizable(False,True)
    build_overlay(root); build_picker(root)
    F=(UIFONT,13); FB=(UIFONT,13,"bold"); FT=(UIFONT,18,"bold"); FS=(UIFONT,11)
    _dark=(ctk.get_appearance_mode()=="Dark")
    LB_BG="#1b2130" if _dark else "#ffffff"; LB_FG="#e6e9f0" if _dark else "#1c2430"
    SUB=("gray45","gray60")

    def _save_cfg():
        d=load_settings(); d.update({"collecting":COLLECTING,"acomp":ACOMP}); save_settings(d)

    # 하단 바 먼저 고정
    bottom=ctk.CTkFrame(root,fg_color="transparent"); bottom.pack(side="bottom",fill="x",pady=(8,12),padx=16)
    def show_window():
        try: root.deiconify(); root.after(10, lambda:(root.lift(), root.focus_force()))
        except Exception: pass
    def hide_bg():
        if HAVE_TRAY and _TRAY is not None: root.withdraw()
        else: root.iconify()
    def quit_all():
        debug("사용자 종료")
        try:
            if _TRAY is not None: _TRAY.stop()
        except Exception: pass
        try: root.destroy()
        except Exception: pass
        os._exit(0)
    ctk.CTkButton(bottom,text=("트레이로 숨기기" if HAVE_TRAY else "백그라운드로 숨기기"),font=F,command=hide_bg,
                  fg_color="transparent",border_width=1,text_color=SUB,hover_color=("#e5e7eb","#222b3c")).pack(side="left",expand=True,fill="x",padx=(0,4))
    ctk.CTkButton(bottom,text="종료",font=F,command=quit_all,fg_color="#b3402f",hover_color="#8f3325").pack(side="left",expand=True,fill="x",padx=(4,0))
    root.protocol("WM_DELETE_WINDOW", quit_all)

    ctk.CTkLabel(root,text="⌨  타이핑 도우미",font=FT).pack(pady=(16,0))
    ctk.CTkLabel(root,text="v"+APP_VERSION,font=(UIFONT,10),text_color=SUB).pack()
    status_var=tk.StringVar(); stat=ctk.CTkLabel(root,textvariable=status_var,font=FB); stat.pack(pady=(10,0))
    info_var=tk.StringVar(); ctk.CTkLabel(root,textvariable=info_var,font=FS,text_color=SUB).pack(pady=(2,2))

    def refresh():
        if LISTENER is not None and not LISTENER.is_alive():
            status_var.set("⚠ 키보드 후킹 중단됨 - 앱을 다시 시작하세요"); stat.configure(text_color="#dc2626")
        else:
            s="● 수집 중" if COLLECTING else "■ 수집 멈춤"; a="자동완성 ON" if ACOMP else "자동완성 OFF"
            status_var.set(f"{s}   |   {a}"); stat.configure(text_color=("#16a34a" if COLLECTING else "#9aa0a6"))
        info_var.set(f"오늘 {_today_count}줄 · 표현 {len(PHRASE_LIST)}개" + (f" (★{len(PINNED)})" if PINNED else "") + f" · 데이터 {_dir_size(LOG_DIR)//1024}KB")
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
    def mkbtn(parent,txt,cmd,color="#3b82f6",side_pad=(0,0),h=34,font=None):
        b=ctk.CTkButton(parent,text=txt,font=(font or FB),command=cmd,fg_color=color,height=h)
        b.pack(side="left",expand=True,fill="x",padx=side_pad); return b
    def mkrow(parent=None,pady=4,padx=14):
        fr=ctk.CTkFrame(parent or root,fg_color="transparent"); fr.pack(fill="x",padx=padx,pady=pady); return fr
    r_tog=mkrow()
    b_collect=mkbtn(r_tog,"수집", toggle_collect, side_pad=(0,4))
    b_acomp=mkbtn(r_tog,"자동완성", toggle_acomp, side_pad=(4,0))
    def _refresh_toggles():
        try:
            b_collect.configure(text=("● 수집: 켜짐" if COLLECTING else "■ 수집: 꺼짐"),
                                fg_color=("#16a34a" if COLLECTING else "#6b7280"),
                                hover_color=("#128a3e" if COLLECTING else "#5a626e"))
            b_acomp.configure(text=("✓ 자동완성: 켜짐" if ACOMP else "✕ 자동완성: 꺼짐"),
                              fg_color=("#3b82f6" if ACOMP else "#6b7280"),
                              hover_color=("#2f6fd6" if ACOMP else "#5a626e"))
        except Exception: pass
    _refresh_toggles()

    # 안내 + 더보기 토글 (기본 화면은 토글 2개만, 나머지는 여기 안으로)
    ctk.CTkLabel(root,text="입력 중 커서 위 목록 → Tab 채움 · 백틱( ` )으로 문구 검색",
                 font=FS,text_color=SUB).pack(pady=(4,2))
    _more_open=bool(_cfg.get("more_open",False))
    more_btn=ctk.CTkButton(root,font=F,fg_color="transparent",text_color=SUB,anchor="center",height=30,
                           hover_color=("#e5e7eb","#222b3c"))
    more_btn.pack(fill="x",padx=16,pady=(4,2))
    more=ctk.CTkFrame(root,fg_color="transparent")
    H_SMALL="384x300"; H_BIG="384x660"
    def _refresh_more():
        more_btn.configure(text=("▲   접기" if _more_open else "⚙   더보기 · 설정 · 상용구   ▼"))
        if _more_open:
            more.pack(fill="x",padx=2,pady=(0,2))
            try:                                   # 내용 높이에 맞춰 창을 정확히 키운다(잘림 방지)
                root.update_idletasks()
                h=root.winfo_reqheight(); sh=root.winfo_screenheight()
                root.geometry("384x%d" % max(300, min(h, sh-90)))
            except Exception: root.geometry(H_BIG)
        else:
            more.pack_forget(); root.geometry(H_SMALL)
    def _toggle_more():
        nonlocal _more_open
        _more_open=not _more_open
        try: d=load_settings(); d["more_open"]=_more_open; save_settings(d)
        except Exception: pass
        _refresh_more()
    more_btn.configure(command=_toggle_more)

    # ── 관리(열기/추출) ──
    ctk.CTkLabel(more,text="관리",font=(UIFONT,11,"bold"),text_color=SUB,anchor="w").pack(fill="x",padx=16,pady=(6,1))
    r_open=mkrow(more,pady=2)
    mkbtn(r_open,"문구", lambda:_open(PHRASES), color="#4b5563", side_pad=(0,3), h=30, font=FS)
    mkbtn(r_open,"상용구", lambda:_open(SNIPPETS), color="#4b5563", side_pad=(3,3), h=30, font=FS)
    mkbtn(r_open,"폴더", lambda:_open(LOG_DIR), color="#4b5563", side_pad=(3,3), h=30, font=FS)
    mkbtn(r_open,"가이드", lambda:_open(GUIDE), color="#4b5563", side_pad=(3,0), h=30, font=FS)
    def _io_msg(fn):
        try:
            r=fn()
            if r:
                from tkinter import messagebox; messagebox.showinfo("표현 관리", r, parent=root)
                reload_phrases()
        except Exception: debug("io 실패:\n"+traceback.format_exc())
    def _do_extract():
        try:
            cands=extract_candidates()
            p=os.path.join(LOG_DIR,"추출후보.txt")
            with open(p,"w",encoding="utf-8") as f:
                f.write("# 수집 데이터에서 뽑은 표현 후보입니다.\n")
                f.write("# 원하는 줄만 남기고 저장한 뒤, '가져오기'로 이 파일을 선택하면 추가됩니다.\n\n")
                f.write("\n".join(cands)+"\n")
            _open(p)
            from tkinter import messagebox
            messagebox.showinfo("표현 추출", f"수집 데이터에서 {len(cands)}개 후보를 '추출후보.txt'에 저장했어요.\n원하는 것만 남기고 '가져오기'로 추가하세요.", parent=root)
        except Exception: debug("추출 실패:\n"+traceback.format_exc())
    r_io2=mkrow(more,pady=2)
    mkbtn(r_io2,"추출", _do_extract, color="#4b5563", side_pad=(0,3), h=30, font=FS)
    mkbtn(r_io2,"가져오기", lambda:_io_msg(import_phrases), color="#4b5563", side_pad=(3,3), h=30, font=FS)
    mkbtn(r_io2,"내보내기", lambda:_io_msg(export_phrases), color="#4b5563", side_pad=(3,0), h=30, font=FS)

    # ── 설정 ──
    ctk.CTkLabel(more,text="설정",font=(UIFONT,11,"bold"),text_color=SUB,anchor="w").pack(fill="x",padx=16,pady=(8,1))
    r_set=mkrow(more,pady=2)
    as_btn=ctk.CTkButton(r_set,font=FS,height=30)
    def _refresh_as():
        on=autostart_enabled()
        as_btn.configure(text=("자동시작: 켜짐" if on else "자동시작: 꺼짐"), fg_color=("#0d9488" if on else "#6b7280"))
    def toggle_autostart():
        set_autostart(not autostart_enabled()); _refresh_as()
    as_btn.configure(command=toggle_autostart); _refresh_as(); as_btn.pack(side="left",expand=True,fill="x",padx=(0,3))
    _thmap={"auto":"자동","light":"라이트","dark":"다크"}
    th_btn=ctk.CTkButton(r_set,font=FS,height=30,fg_color="#7c3aed",hover_color="#6a2fd0")
    def _cycle_theme():
        order=["auto","light","dark"]; d=load_settings(); cur=d.get("theme","auto")
        nxt=order[(order.index(cur)+1)%3] if cur in order else "auto"
        d["theme"]=nxt; save_settings(d)
        th_btn.configure(text="테마: "+_thmap[nxt])
        try: ctk.set_appearance_mode({"auto":"system","light":"light","dark":"dark"}[nxt])
        except Exception: pass
    th_btn.configure(command=_cycle_theme, text="테마: "+_thmap.get(_cfg.get("theme","auto"),"자동")); th_btn.pack(side="left",expand=True,fill="x",padx=(3,0))

    # 앱별 자동완성
    appf=ctk.CTkFrame(more); appf.pack(fill="x",padx=14,pady=(6,2))
    ctk.CTkLabel(appf,text="앱별 자동완성",font=(UIFONT,10,"bold"),text_color=SUB,anchor="w").pack(fill="x",padx=10,pady=(5,0))
    app_var=tk.StringVar(value="직전 앱을 확인 중...")
    ctk.CTkLabel(appf,textvariable=app_var,font=FS,text_color=SUB,justify="left",anchor="w",wraplength=330).pack(fill="x",padx=10)
    def _toggle_app():
        name=_last_fg_app
        if not name:
            app_var.set("직전에 쓰던 다른 앱이 없습니다. 다른 창을 클릭한 뒤 다시 눌러주세요."); return
        if name in BLOCKED_APPS: BLOCKED_APPS.discard(name)
        else: BLOCKED_APPS.add(name)
        try:
            d=load_settings(); d["disabled_apps"]=sorted(BLOCKED_APPS); save_settings(d)
        except Exception: pass
    ctk.CTkButton(appf,text="직전 앱 자동완성 켜기 / 끄기",font=FS,command=_toggle_app,fg_color="#4b5563",height=30).pack(fill="x",padx=10,pady=(4,7))
    ctk.CTkLabel(more,text="빠른 토글: Ctrl + Alt + Space",font=(UIFONT,10),text_color=SUB).pack(pady=(1,1))

    # 제안 개수 + 글자 크기
    r_io=mkrow(more,pady=2)
    ctk.CTkLabel(r_io,text="제안 개수",font=FS,text_color=SUB).pack(side="left")
    _ms=tk.IntVar(value=MAX_SUG)
    def _set_maxsug(*_):
        global MAX_SUG
        try: v=int(_ms.get())
        except Exception: return
        v=max(3,min(12,v)); MAX_SUG=v
        try: d=load_settings(); d["max_sug"]=v; save_settings(d)
        except Exception: pass
    tk.Spinbox(r_io,from_=3,to=12,width=3,textvariable=_ms,command=_set_maxsug,font=F,justify="center",
               relief="flat",bg=LB_BG,fg=LB_FG,buttonbackground=LB_BG,highlightthickness=0).pack(side="left",padx=(6,12))
    ctk.CTkLabel(r_io,text="글자 크기",font=FS,text_color=SUB).pack(side="left")
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
    tk.Spinbox(r_io,from_=9,to=20,width=3,textvariable=_fs,command=_set_ovfont,font=F,justify="center",
               relief="flat",bg=LB_BG,fg=LB_FG,buttonbackground=LB_BG,highlightthickness=0).pack(side="left",padx=(6,0))

    # 가벼운 모드 + 로그 보관/정리
    r_perf=mkrow(more,pady=(2,4))
    lm_btn=ctk.CTkButton(r_perf,font=FS,height=30)
    def _refresh_lm():
        on=LIGHT_MODE
        lm_btn.configure(text=("가벼운 모드: 켜짐" if on else "가벼운 모드: 꺼짐"), fg_color=("#0d9488" if on else "#6b7280"))
    def _toggle_lm():
        global LIGHT_MODE
        LIGHT_MODE=not LIGHT_MODE
        try: d=load_settings(); d["light_mode"]=LIGHT_MODE; save_settings(d)
        except Exception: pass
        _refresh_lm()
    lm_btn.configure(command=_toggle_lm); _refresh_lm(); lm_btn.pack(side="left",expand=True,fill="x",padx=(0,3))
    _kd=tk.IntVar(value=int(_cfg.get("log_keep_days",30) or 0))
    def _set_keep(*_):
        try: v=int(_kd.get())
        except Exception: return
        v=max(0,min(365,v))
        try: d=load_settings(); d["log_keep_days"]=v; save_settings(d)
        except Exception: pass
    def _do_clean():
        try:
            days=int(_kd.get() or 0) or 30
            n=_clean_old_logs(days)
            from tkinter import messagebox; messagebox.showinfo("로그 정리", f"오래된 로그 {n}개를 정리했습니다.", parent=root)
        except Exception: debug("로그 정리 실패:\n"+traceback.format_exc())
    ctk.CTkButton(r_perf,text="정리",font=FS,command=_do_clean,fg_color="#4b5563",width=48,height=30).pack(side="right",padx=(3,0))
    ctk.CTkLabel(r_perf,text="일 보관",font=FS,text_color=SUB).pack(side="right",padx=(2,0))
    tk.Spinbox(r_perf,from_=0,to=365,width=4,textvariable=_kd,command=_set_keep,font=F,justify="center",
               relief="flat",bg=LB_BG,fg=LB_FG,buttonbackground=LB_BG,highlightthickness=0).pack(side="right",padx=(3,0))
    _refresh_more()

    if not _cfg.get("onboarded"):
        def _onboard():
            try:
                from tkinter import messagebox
                messagebox.showinfo("타이핑 도우미 시작하기",
                    "1) 평소처럼 타이핑하면 커서 위에 추천 목록이 떠요.\n"
                    "2) ↑/↓로 고르고 Tab으로 채웁니다 (Esc로 닫기).\n"
                    "3) 백틱( ` )을 누르면 문구·상용구 검색창이 열려요.\n"
                    "4) 단축키를 치고 스페이스/엔터 → 그 자리에서 상용구로 자동확장.\n"
                    "5) Ctrl+Alt+Space로 자동완성을 껐다 켤 수 있어요.\n\n"
                    "· 최근 1시간에 친 문장은 자동으로 후보에 올라옵니다.\n"
                    "· 문구는 '더보기 → 📝문구', 상용구/단축키는 '더보기 → ⚡상용구' 파일로 관리합니다.",
                    parent=root)
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
