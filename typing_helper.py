# -*- coding: utf-8 -*-
import os, time, threading, traceback, ctypes
from ctypes import wintypes
# 교차 빌드(Wine) 환경의 tcl/tk 경로. 그 경로가 실제로 존재할 때만 설정한다.
# 무조건 setdefault 하면 C:\py311 이 없는 PC에서 소스 실행 시 tk.Tk() 가 죽는다.
for _var, _p in (("TCL_LIBRARY", r"C:\py311\tcl\tcl8.6"), ("TK_LIBRARY", r"C:\py311\tcl\tk8.6")):
    if _var not in os.environ and os.path.isdir(_p): os.environ[_var] = _p
from datetime import datetime, date

LOG_DIR = os.path.join(os.path.expanduser("~"), "Documents", "TypingLog")
os.makedirs(LOG_DIR, exist_ok=True)
def debug(m):
    try:
        with open(os.path.join(LOG_DIR,"_debug.log"),"a",encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {m}\n")
    except Exception: pass
debug("=== v8(오버레이 지속+트레이) boot ===")
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

APP_NAME="타이핑 도우미"
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
def load_phrases():
    global PHRASE_LIST,_phrase_mtime
    try:
        mt=os.path.getmtime(PHRASES)
        if mt==_phrase_mtime: return
        _phrase_mtime=mt
        out=[]
        with open(PHRASES,encoding="utf-8") as f:
            for ln in f:
                s=ln.rstrip("\n")
                if s.strip() and not s.lstrip().startswith("#"): out.append(s)
        PHRASE_LIST=out; debug(f"phrases {len(out)}개 로드")
    except Exception: pass
def reload_phrases():
    global _phrase_mtime
    _phrase_mtime=0; load_phrases()      # mtime 무시하고 강제로 다시 읽는다
def _has_long_digits(t,n=8):
    run=0
    for c in t:
        run=run+1 if c.isdigit() else 0
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
def del_phrase(text):
    t=(text or "").strip()
    if not t: return "삭제할 표현을 목록에서 고르세요"
    try:
        with open(PHRASES,encoding="utf-8") as f: lines=f.readlines()
        keep=[ln for ln in lines if ln.rstrip("\r\n")!=t]
        if len(keep)==len(lines): return "목록에 없는 표현입니다"
        with open(PHRASES,"w",encoding="utf-8") as f: f.writelines(keep)
    except Exception:
        debug("표현 삭제 실패:\n"+traceback.format_exc()); return "삭제 실패 (로그 확인)"
    reload_phrases(); return "삭제됨: "+t
MAX_SUG=6
def top_matches(cur_latin, n=MAX_SUG):
    # 커서 위 목록용 - 상위 n개 후보와 '이미 화면에 입력돼 있는 접두사'를 함께 돌려준다.
    # 한글 조합 접두사를 먼저 맞춰보고, 걸리는 게 없으면 영문 자판 그대로 맞춘다.
    if len(cur_latin)<MIN_PREFIX or not PHRASE_LIST: return [], ""
    ph=compose(cur_latin)
    hits=[p for p in PHRASE_LIST if len(p)>len(ph) and p.startswith(ph)]
    if hits: return hits[:n], ph
    pl=cur_latin.lower()
    hits=[p for p in PHRASE_LIST if len(p)>len(pl) and p.lower().startswith(pl)]
    if hits: return hits[:n], cur_latin
    return [], ""
def reco_matches(q, k=40):
    """대시보드 추천창용 - 사용자가 상자에 입력한 질의(q)로 표현 목록을 걸러 정렬한다.
    한글 IME로 직접 친 질의와 영문 자판(dkssud)으로 친 질의를 모두 처리한다.
    앞부분 일치를 먼저, 그 다음 부분 문자열 포함 순으로 돌려준다."""
    if not q: return PHRASE_LIST[:k]
    ql=q.lower()
    qh=compose(q) if q.isascii() else q   # 영문 자판이면 한글로 조합해 본다
    pre=[]; sub=[]
    for p in PHRASE_LIST:
        pl=p.lower()
        if p.startswith(q) or (qh and p.startswith(qh)) or pl.startswith(ql): pre.append(p)
        elif q in p or (qh and qh in p) or ql in pl: sub.append(p)
    return (pre+sub)[:k]

# ---- 상태 ----
_buf=[]; _lock=threading.Lock(); _last_input=time.time()
_ctrl=False; _paste=False; _last_clip=""; COLLECTING=True; ACOMP=True
_cur=[]; _injecting=False; _last_written=""; _today_count=0; _clip_seq=0
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
    global _ctrl,_last_input,_paste,_injecting
    # 여기서 예외가 새어나가면 pynput이 리스너를 조용히 중단시킨다.
    # join()을 하는 곳이 없어서 수집이 멎어도 아무도 모른다 - 전체를 감싼다.
    try:
        if _injecting: return
        if key in (keyboard.Key.ctrl_l,keyboard.Key.ctrl_r): _ctrl=True; return
        vk=getattr(key,"vk",None)
        if _ctrl and vk in (VK_C,VK_V,VK_X):
            if vk==VK_V: _paste=True
            _cur.clear(); _update_sug()
            return
        ch=getattr(key,"char",None)
        # 수집 버퍼
        if COLLECTING:
            _last_input=time.time()
            with _lock:
                if ch is not None: _buf.append(ch)
                elif key==keyboard.Key.space: _buf.append(" ")
                elif key==keyboard.Key.enter: _buf.append("\n")
                elif key==keyboard.Key.backspace:
                    if _buf: _buf.pop()
                elif key==keyboard.Key.tab: _buf.append("\t")
        # 자동완성용 현재줄 버퍼
        if ch is not None: _cur.append(ch)
        elif key==keyboard.Key.space: _cur.append(" ")
        elif key==keyboard.Key.backspace:
            if _cur: _cur.pop()
        elif key in (keyboard.Key.enter,keyboard.Key.esc): _cur.clear()
        elif key not in _KEEP_CUR: _cur.clear()   # 방향키·Home/End 등 캐럿이 움직인 경우만
        _update_sug()
    except Exception:
        debug("on_press 예외:\n"+traceback.format_exc())

def on_release(key):
    global _ctrl
    if key in (keyboard.Key.ctrl_l,keyboard.Key.ctrl_r): _ctrl=False

def _set_sug(items,pref,idx=0,close=False):
    # ver를 '맨 마지막'에 올려야 그리는 쪽이 반쯤 갱신된 상태를 보지 않는다.
    S["items"]=items; S["pref"]=pref; S["idx"]=idx
    S["rem"]=items[idx][len(pref):] if items else ""
    S["close"]=close   # True=즉시 숨김(Esc/삽입), False=잠깐 유지 후 숨김(편집 중 깜빡임 방지)
    S["ver"]+=1
def _update_sug():
    if not ACOMP: _set_sug([],""); return
    items,pref=top_matches("".join(_cur))
    _set_sug(items,pref)          # 글자를 더 치면 선택은 항상 첫 항목으로
def move_sel(d):
    # 화살표로 후보 이동. 저수준 훅 콜백에서 불리므로 Tk를 건드리지 않는다.
    n=len(S["items"])
    if not n: return
    _set_sug(S["items"],S["pref"],(S["idx"]+d)%n)

def do_insert():
    global _injecting
    rem=S["rem"]
    if not rem: return
    _injecting=True
    try: KBD.type(rem)
    except Exception: debug("insert fail:\n"+traceback.format_exc())
    time.sleep(0.03); _injecting=False
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
        while True:
            time.sleep(0.4); load_phrases()
            if date.today()!=cur:
                flush(mf,rf); mf.close(); rf.close(); cur=date.today()
                mf=open(mainpath(),"a",encoding="utf-8"); rf=open(rawpath(),"a",encoding="utf-8")
                _today_count=0
            if COLLECTING and pyperclip:
                # 0.4초마다 클립보드를 여는 대신 시퀀스 번호로 변경 여부부터 본다.
                seq=clip_seq()
                if seq!=_clip_seq:
                    _clip_seq=seq
                    try: clip=pyperclip.paste()
                    except Exception: clip=""
                    if clip and clip!=_last_clip:
                        flush(mf,rf); one=clip.replace("\n"," ⏎ ")
                        _emit(mf,rf,one,one,"복사됨"); _last_clip=clip
            if _paste:
                _paste=False; flush(mf,rf); one=(_last_clip or "").replace("\n"," ⏎ ")
                _emit(mf,rf,one,one,"붙여넣기")
            with _lock: n=len(_buf)
            if n and (time.time()-_last_input>=FLUSH_IDLE or n>=FLUSH_MAX): flush(mf,rf)
    except Exception:
        debug("writer 크래시:\n"+traceback.format_exc())

def count_today_lines():
    try:
        with open(mainpath(),encoding="utf-8") as f: return sum(1 for _ in f)
    except Exception: return 0
def _open(p):
    try: os.startfile(p)
    except Exception: debug("open fail "+p+"\n"+traceback.format_exc())

# ---- 오버레이 ----
OV=None; OVLIST=None; OVHINT=None; _drawn_ver=-1
_ov_xy=None; _ov_shown=False; _empty_ticks=0
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
    OVLIST=tk.Listbox(OV,font=("Malgun Gothic",11),activestyle="none",bd=0,
                      highlightthickness=0,exportselection=False,
                      bg="#111827",fg="#e5e7eb",selectbackground="#2563eb",selectforeground="white")
    OVLIST.pack(fill="both",padx=1,pady=(1,0))
    OVHINT=tk.Label(OV,text="↑↓ 선택 · Tab 완성 · Esc 닫기",
                    font=("Malgun Gothic",8),bg="#1f2937",fg="#9ca3af",anchor="w",padx=6)
    OVHINT.pack(fill="x",padx=1,pady=(0,1))
    OV.withdraw()
def draw_overlay():
    # 내용/위치만 갱신한다. 숨길지 여부는 overlay_tick 이 판단(깜빡임 방지).
    global _ov_xy,_ov_shown
    if not OV: return
    items=S["items"]
    if not items: return
    xy=caret_xy() or _ov_xy            # 캐럿을 못 찾으면(Electron 등) 마지막 위치 재사용
    if not xy: return
    _ov_xy=xy
    idx=S["idx"]
    if idx>=len(items): idx=len(items)-1
    OVLIST.delete(0,tk.END)
    for p in items: OVLIST.insert(tk.END,"  "+p)
    OVLIST.config(height=len(items), width=min(60,max(len(p) for p in items)+4))
    OVLIST.selection_clear(0,tk.END); OVLIST.selection_set(idx); OVLIST.see(idx)
    OV.update_idletasks()
    x,y=xy; w=OV.winfo_reqwidth(); h=OV.winfo_reqheight()
    sw=OV.winfo_screenwidth(); sh=OV.winfo_screenheight()
    if x+w>sw: x=max(0,sw-w-4)
    if y+h>sh: y=max(0,y-h-26)         # 아래 공간이 없으면 캐럿 위쪽으로 띄운다
    OV.geometry(f"+{x}+{y}")
    if not _ov_shown: OV.deiconify(); OV.lift(); _ov_shown=True   # 이미 떠 있으면 재표시 안 함
def _hide_ov():
    global _ov_shown
    if OV and _ov_shown: OV.withdraw(); _ov_shown=False
def hide_overlay(): _hide_ov()
_HIDE_TICKS=8   # 8 x 60ms ≈ 0.5초 동안 후보가 계속 비어야 숨긴다
def overlay_tick():
    # 오버레이/트레이 관련 Tk 작업은 전부 여기(메인루프)서만 한다.
    global _drawn_ver,_empty_ticks
    try:
        while True:                    # 다른 스레드가 요청한 UI 작업 처리
            with _ui_lock: fn=_ui_q.pop(0) if _ui_q else None
            if not fn: break
            try: fn()
            except Exception: debug("ui_q 예외:\n"+traceback.format_exc())
        items=S["items"]; ver=S["ver"]
        if not ACOMP:
            _hide_ov(); _empty_ticks=0
        elif items:                    # 후보 있음 -> 계속 노출(내용만 갱신)
            _empty_ticks=0
            if ver!=_drawn_ver or not _ov_shown:
                _drawn_ver=ver; draw_overlay()
        else:                          # 후보 없음
            _drawn_ver=ver
            if S.get("close"): _hide_ov(); _empty_ticks=0     # Esc/삽입: 즉시
            else:                                             # 편집 중 잠깐 빈 것: 유지 후 숨김
                _empty_ticks+=1
                if _empty_ticks>=_HIDE_TICKS: _hide_ov()
    except Exception: debug("overlay 예외:\n"+traceback.format_exc())
    if ROOT: ROOT.after(60,overlay_tick)

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
    global LISTENER,ROOT,_today_count
    single_instance()
    ensure_files(); load_phrases()
    _today_count=count_today_lines()   # 시작 시 한 번만 읽고, 이후엔 _emit이 센다
    threading.Thread(target=writer,daemon=True).start()
    LISTENER=keyboard.Listener(on_press=on_press,on_release=on_release,win32_event_filter=win_filter)
    LISTENER.start(); debug("리스너 시작")

    root=tk.Tk(); ROOT=root; root.title(APP_NAME); root.geometry("400x880"); root.minsize(400,700)
    root.resizable(False,True); root.configure(bg="#f5f6f8")
    build_overlay(root)
    F=("Malgun Gothic",10); FB=("Malgun Gothic",11,"bold"); FT=("Malgun Gothic",14,"bold")

    AUTO_COPY=tk.BooleanVar(value=False)   # 자동복사: 입력 때마다 1순위 표현을 클립보드에 복사

    # 하단 바를 먼저 bottom에 고정 -> 위 내용이 늘어도 절대 잘리지 않는다(기존 '하단 버튼 잘림' 대응)
    bottom=tk.Frame(root,bg="#f5f6f8"); bottom.pack(side="bottom",fill="x",pady=(10,10),padx=24)
    def show_window():
        try: root.deiconify(); root.after(10, lambda:(root.lift(), root.focus_force()))
        except Exception: pass
    def hide_bg():
        # 트레이가 있으면 창을 완전히 숨겨(작업표시줄에서도 사라짐) 트레이로만 남긴다.
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
    tk.Button(bottom,text=("트레이로 숨기기" if HAVE_TRAY else "백그라운드로 숨기기"),font=F,command=hide_bg,relief="flat",bg="#e5e7eb",cursor="hand2").pack(side="left",expand=True,fill="x",padx=(0,4))
    tk.Button(bottom,text="종료",font=F,command=quit_all,relief="flat",bg="#fecaca",cursor="hand2").pack(side="left",expand=True,fill="x",padx=(4,0))
    root.protocol("WM_DELETE_WINDOW", quit_all)   # X = 실제 종료

    tk.Label(root,text="⌨  타이핑 도우미",font=FT,bg="#f5f6f8",fg="#1f2937").pack(pady=(14,4))
    status_var=tk.StringVar(); stat=tk.Label(root,textvariable=status_var,font=FB,bg="#f5f6f8"); stat.pack()
    info_var=tk.StringVar(); tk.Label(root,textvariable=info_var,font=F,bg="#f5f6f8",fg="#6b7280").pack(pady=(2,8))

    def refresh():
        if LISTENER is not None and not LISTENER.is_alive():
            status_var.set("⚠ 키보드 후킹 중단됨 - 앱을 다시 시작하세요"); stat.config(fg="#dc2626")
        else:
            s="● 수집 중" if COLLECTING else "■ 수집 멈춤"
            a="자동완성 ON" if ACOMP else "자동완성 OFF"
            status_var.set(f"{s}   |   {a}"); stat.config(fg="#059669" if COLLECTING else "#dc2626")
        # 예전엔 여기서 오늘자 로그 전체를 1.2초마다 다시 읽었다(파일이 클수록 UI가 느려짐).
        info_var.set(f"오늘 {_today_count}줄 수집 · 표현 {len(PHRASE_LIST)}개 로드됨")
        root.after(1200,refresh)
    def toggle_collect():
        global COLLECTING; COLLECTING=not COLLECTING
    def toggle_acomp():
        global ACOMP; ACOMP=not ACOMP
        if not ACOMP: _set_sug([],"")
    def mkbtn(txt,cmd,bg="#2563eb",fg="white"):
        tk.Button(root,text=txt,font=FB,command=cmd,bg=bg,fg=fg,relief="flat",
                  activebackground=bg,cursor="hand2",height=1).pack(fill="x",padx=24,pady=3)
    mkbtn("수집 켜기 / 끄기", toggle_collect, bg="#374151")
    mkbtn("자동완성 켜기 / 끄기", toggle_acomp, bg="#4b5563")
    mkbtn("📋  교정 프롬프트 가이드 열기", lambda:_open(GUIDE))
    mkbtn("📁  수집 데이터 폴더 열기", lambda:_open(LOG_DIR))
    mkbtn("📝  교정결과(phrases.txt) 열기", lambda:_open(PHRASES))

    # ---- 추천 목록 패널 ----
    panel=tk.LabelFrame(root,text=" 추천 목록 (검색 / 직접 추가) ",font=F,
                        bg="#f5f6f8",fg="#374151",padx=8,pady=6)
    panel.pack(fill="both",expand=True,padx=16,pady=(8,4))

    q_var=tk.StringVar()
    q_entry=tk.Entry(panel,textvariable=q_var,font=("Malgun Gothic",12))
    q_entry.pack(fill="x",pady=(2,6))

    listwrap=tk.Frame(panel,bg="#f5f6f8"); listwrap.pack(fill="both",expand=True)
    sb=tk.Scrollbar(listwrap); sb.pack(side="right",fill="y")
    reco=tk.Listbox(listwrap,font=("Malgun Gothic",12),activestyle="none",
                    bg="#ffffff",fg="#111827",selectbackground="#2563eb",selectforeground="white",
                    highlightthickness=1,highlightbackground="#d1d5db",yscrollcommand=sb.set)
    reco.pack(side="left",fill="both",expand=True); sb.config(command=reco.yview)

    def current_text():
        sel=reco.curselection()
        if sel: return reco.get(sel[0])
        if reco.size()>0: return reco.get(0)
        return ""
    def refill(*_):
        items=reco_matches(q_var.get().strip())
        reco.delete(0,tk.END)
        for it in items: reco.insert(tk.END,it)
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

    reco.bind("<Double-Button-1>", lambda e: do_copy())
    q_entry.bind("<Return>", lambda e: do_paste())

    brow=tk.Frame(panel,bg="#f5f6f8"); brow.pack(fill="x",pady=(6,0))
    tk.Button(brow,text="복사",font=FB,command=do_copy,relief="flat",bg="#2563eb",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=(0,3))
    tk.Button(brow,text="붙여넣기",font=FB,command=do_paste,relief="flat",bg="#7c3aed",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=3)
    ac_btn=tk.Button(brow,text="자동복사 OFF",font=FB,command=toggle_autocopy,relief="flat",
                     bg="#9ca3af",fg="white",cursor="hand2",height=1)
    ac_btn.pack(side="left",expand=True,fill="x",padx=(3,0))

    # 사용자가 직접 표현을 넣고 빼는 줄. 넣는 즉시 phrases.txt에 저장되고 자동완성에 반영된다.
    msg_var=tk.StringVar(value="위 상자에 문구를 쓰고 '표현 추가' → 바로 자동완성에 반영됩니다")
    def do_add():
        msg_var.set(add_phrase(q_var.get())); q_var.set(""); refill()
    def do_del():
        msg_var.set(del_phrase(current_text())); refill()
    arow=tk.Frame(panel,bg="#f5f6f8"); arow.pack(fill="x",pady=(4,0))
    tk.Button(arow,text="＋ 표현 추가",font=FB,command=do_add,relief="flat",bg="#059669",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=(0,3))
    tk.Button(arow,text="선택 삭제",font=FB,command=do_del,relief="flat",bg="#b91c1c",fg="white",
              cursor="hand2",height=1).pack(side="left",expand=True,fill="x",padx=(3,0))
    tk.Label(panel,textvariable=msg_var,font=("Malgun Gothic",9),bg="#f5f6f8",fg="#6b7280",
             anchor="w",justify="left",wraplength=330).pack(fill="x",pady=(4,0))
    q_entry.bind("<Control-Return>", lambda e: do_add())

    refill(); q_entry.focus_set()
    start_tray(on_open=lambda: post_ui(show_window), on_quit=lambda: post_ui(quit_all),
               on_collect=toggle_collect, on_acomp=toggle_acomp)
    refresh(); overlay_tick(); debug("mainloop 진입"); root.mainloop()

if __name__=="__main__":
    try:
        debug("main 진입"); run_ui()
    except Exception:
        debug("MAIN CRASH:\n"+traceback.format_exc())
