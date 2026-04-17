import time, re, unicodedata, sys, os, json, shutil, threading, subprocess, random
from pathlib import Path

C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAG = "\033[95m"
C_BLUE = "\033[94m"
C_DIM = "\033[2m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"
C_WHITE = "\033[97m"
C_FRAME = "\033[37m"
C_EDGE = "\033[38;2;70;160;255m"
C_CHR = "\033[38;2;255;115;30m"

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
CLR = "cls" if os.name == "nt" else "clear"
if os.name == "nt":
    os.system("")


def _rndcol():
    while True:
        r, g, b = (
            random.randint(60, 255),
            random.randint(60, 255),
            random.randint(60, 255),
        )
        if max(r, g, b) >= 180:
            return f"\033[38;2;{r};{g};{b}m"


def _bc(b):
    return C_EDGE if str(b).lower() == "edge" else C_CHR


def _vw(s):
    s = re.sub(r"\033\[[^m]*m", "", s)
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


_ANSI = re.compile(r"\033\[[^m]*m")


def _pw(s):
    return _vw(_ANSI.sub("", s))


def _row_color(i, total):
    h = i / max(total, 1)
    s = 0.82
    v = 0.98
    hi = int(h * 6)
    f = h * 6 - hi
    p = v * (1 - s)
    q = v * (1 - f * s)
    t2 = v * (1 - (1 - f) * s)
    rgb = [(v, t2, p), (q, v, p), (p, v, t2), (p, q, v), (t2, p, v), (v, p, q)][hi % 6]
    r, g, b = (int(x * 255) for x in rgb)
    return "\033[38;2;%d;%d;%dm" % (r, g, b)


def _ensure_deps():
    try:
        import importlib.util

        req = [("beautifulsoup4", "bs4"), ("selenium", "selenium"), ("lxml", "lxml")]
        miss = [p for p, m in req if not importlib.util.find_spec(m)]
        if not miss:
            return
        W = max(len(p) for p in miss) + 4
        os.system(CLR)
        print(f"\n  {C_BOLD}{C_CYAN}◈  FACEBOOK COMMENT SCRAPER{C_RESET}")
        print(f"  {C_DIM}Setting up required libraries...{C_RESET}\n")
        print(f"  {C_DIM}╔{'═'*(W+2)}╗{C_RESET}")
        for p in miss:
            print(
                f"  {C_DIM}║{C_RESET}   {C_YELLOW}{p}{C_RESET}{C_DIM}{(W-len(p)-1)*' '}║{C_RESET}"
            )
        print(f"  {C_DIM}╚{'═'*(W+2)}╝{C_RESET}\n")
        for pkg in miss:
            t0, evt = time.time(), threading.Event()

            def _spin(pkg=pkg, t0=t0, stop=evt):
                tick = 0
                sc = _rndcol()
                while not stop.is_set():
                    if tick % 8 == 0:
                        sc = _rndcol()
                    sys.stdout.write(
                        f"\r  {sc}{SPINNERS[tick%10]}{C_RESET}  {C_DIM}installing{C_RESET} {C_BOLD}{C_WHITE}{pkg}{C_RESET}  {C_DIM}{time.time()-t0:.1f}s{C_RESET}   "
                    )
                    sys.stdout.flush()
                    tick += 1
                    time.sleep(0.08)
                sys.stdout.write(
                    f"\r  {C_GREEN}✓{C_RESET}  {C_BOLD}{C_WHITE}{pkg}{C_RESET}  {C_DIM}ready · {time.time()-t0:.1f}s{C_RESET}   \n"
                )
                sys.stdout.flush()

            t = threading.Thread(target=_spin, daemon=True)
            t.start()
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            evt.set()
            t.join(2)
        print(f"\n  {C_GREEN}✓{C_RESET}  {C_BOLD}All libraries ready{C_RESET}\n")
    except Exception as e:
        print(f"  {C_RED}✗{C_RESET}  Dependency error: {e}")


_ensure_deps()
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By

SCROLL_PAUSE = 1.1
MAX_SCROLLS = 2000
OUTPUT_DIR = Path(".")
_devnull = []

_BADGE_WORDS = (
    r"Tài khoản đã xác minh|Đã xác minh|Fan cứng|Fan đang lên|Người theo dõi"
    r"|Theo dõi|Top fan|New member|Follower|Following|Admin|Moderator|Author"
    r"|Verified account|Tác giả|Tác giả bài viết|Quản trị viên|Người kiểm duyệt"
)
_RE_FB_ART = re.compile(r"\$\s*/\$|(?<![A-Za-z0-9])\$(?![A-Za-z0-9])")
_RE_BADGE = re.compile(
    rf"(?:(?:TOP\s+Comments?)\s+)?(?:\s*[-·,|]?\s*(?:{_BADGE_WORDS}))+\s*[-·,|]?\s*",
    re.IGNORECASE,
)
_RE_TOPUI = re.compile(r"^TOP\s+Comments?\s*", re.IGNORECASE)
_RE_IMG = re.compile(
    r"(?:Có thể là hình ảnh về|May be an image of|Hình ảnh về|Image of)[^.]*\.?",
    re.IGNORECASE,
)
_RE_TIME = re.compile(
    r"(?:^|\s+)\d+\s*\b(?:giờ|phút|ngày|tuần|tháng|năm|seconds?|minutes?|hours?|days?|weeks?"
    r"|months?|years?|hr|hrs?|min|mins?|sec|secs?|mo|yr)\b\s*(?:trước|ago|edited|đã chỉnh sửa)?\s*$",
    re.IGNORECASE,
)
_RE_VIDEO = re.compile(r"\d+:\d+\s*/\s*\d+:\d+")
_RE_SHARE = re.compile(
    r"^.*?(?:\d+\s*(?:giờ|phút|ngày|tuần|tháng)?\s*)?·\s*Đã chia sẻ với\s+(?:Nhóm\s+)?(?:công khai|Công khai)\s*",
    re.IGNORECASE,
)
_RE_DATE_SHARE = re.compile(
    r"^\d+\s+[Tt]háng\s+\d+.*?·\s*Đã chia sẻ với\s+(?:Nhóm\s+)?(?:công khai|Công khai)\s*",
    re.IGNORECASE,
)
_RE_AUTHOR_TS = re.compile(
    r"\s*\d+\s*(giờ|phút|ngày|tuần|tháng|năm)\s*$", re.IGNORECASE
)
_RE_AUTHOR_SUF = re.compile(r"\s*[·•]\s*.+$")
_RE_POST_TAIL = re.compile(
    r"\s*(?:Tất cả cảm xúc|All reactions?|Xem tất cả cảm xúc|See all reactions?)\s*:?\s*$",
    re.IGNORECASE,
)
_RE_TIME_INLINE = re.compile(r"\s*\blúc\s+\d+:\d+\b", re.IGNORECASE)
_RE_REACT = re.compile(
    r"(?:\s*[\xb7\u2022\-|,]\s*)?(?:(?:\d+\s*)?(?:Thích|Trả lời|Chia sẻ|Like|Reply|Share|Comment)\b\s*)+$",
    re.IGNORECASE,
)
_RE_TRAIL = re.compile(r"\s+[\d.,]+[KkMmTt]?\s*$")

JS_SCROLL = """
(function(step){
  var best=null,bs=-1,els=document.querySelectorAll('div');
  for(var i=0;i<els.length;i++){
    var e=els[i],s=window.getComputedStyle(e),ov=(s.overflow||'')+' '+(s.overflowY||'');
    if(!(ov.includes('scroll')||ov.includes('auto'))||e.scrollHeight<=e.clientHeight+50) continue;
    var sc=e.querySelectorAll('[role="article"]').length*10+e.scrollHeight/1000;
    if(sc>bs){bs=sc;best=e;}
  }
  var bef=best?best.scrollTop:(window.pageYOffset||document.documentElement.scrollTop);
  if(best)best.scrollTop+=step; else window.scrollBy(0,step);
  var aft=best?best.scrollTop:(window.pageYOffset||document.documentElement.scrollTop);
  var a=document.querySelectorAll('[role="article"]');
  var atBot=best?(best.scrollTop+best.clientHeight>=best.scrollHeight-30):(window.innerHeight+window.scrollY>=document.body.scrollHeight-30);
  return{moved:Math.abs(aft-bef)>5,arts:a.length,atBottom:atBot,height:best?best.scrollHeight:document.body.scrollHeight};
})(arguments[0]);
"""

JS_EXPAND_SM = """
(function(){
  var c=0;
  var SM=["xem thêm","see more","xem them"];
  function vis(e){return e.offsetWidth>0||e.offsetHeight>0;}
  var els=document.querySelectorAll('div[role="button"],span[role="button"],a,span,div');
  for(var i=0;i<els.length;i++){
    var el=els[i]; if(!el||!vis(el)) continue;
    var txt=((el.innerText||el.textContent||'').trim()).toLowerCase();
    if(SM.indexOf(txt)===-1) continue;
    var p=el.parentElement,ia=false;
    for(var d=0;d<8&&p;d++){if(p.getAttribute&&p.getAttribute('role')==='article'){ia=true;break;}p=p.parentElement;}
    if(ia){try{el.click();c++;}catch(e){}}
  }
  return c;
})();
"""

JS_LOAD_MORE = """
(function(){
  var c=0;
  var LM=["xem thêm bình luận","xem thêm phản hồi","xem thêm trả lời","xem thêm câu trả lời",
    "bình luận khác","xem trước","xem trước đó","xem bình luận trước","hiển thị thêm",
    "hiển thị bình luận","hiển thị thêm bình luận","view more","show more","load more",
    "more comments","view more comments","see more comments","more replies",
    "view more replies","see more replies","previous comments","previous replies","replies","phản hồi"];
  var EX=["ẩn","hide","thu gọn","đóng","close"];
  var SK=["reply","trả lời","thích","like","chia sẻ","share","comment","bình luận"];
  var seen=new Set();
  function getAll(){
    return document.querySelectorAll('[role="button"],[role="link"],a');
  }
  var els=getAll();
  for(var i=0;i<els.length;i++){
    var el=els[i];
    if(!el||!el.isConnected) continue;
    var raw=(el.innerText||el.textContent||el.getAttribute('aria-label')||'').trim();
    var txt=raw.toLowerCase();
    if(!txt||txt.length>120) continue;
    if(SK.indexOf(txt)!==-1) continue;
    var bad=false;
    for(var j=0;j<EX.length;j++){if(txt.indexOf(EX[j])!==-1){bad=true;break;}}
    if(bad) continue;
    var hit=false;
    for(var k=0;k<LM.length;k++){if(txt.indexOf(LM[k])!==-1){hit=true;break;}}
    if(!hit&&(txt.indexOf('phản hồi')!==-1||txt.indexOf('reply')!==-1||txt.indexOf('trả lời')!==-1)){
      if(txt.match(/[0-9]/)||txt.indexOf('xem')!==-1||txt.indexOf('thêm')!==-1||txt.indexOf('more')!==-1) hit=true;
    }
    if(!hit) continue;
    var key=raw+'|'+el.tagName+'|'+(el.className||'');
    if(seen.has(key)) continue;
    seen.add(key);
    try{
      el.scrollIntoView({block:'nearest',behavior:'instant'});
      el.click(); c++;
    }catch(e){}
  }
  return c;
})();
"""


def _isleep(s, ev=None):
    end = time.time() + s
    while time.time() < end:
        if ev and ev.is_set():
            return
        time.sleep(0.05)


def _wait_fb(driver, ev=None, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        if ev and ev.is_set():
            return
        try:
            if driver.execute_script("return document.readyState") == "complete":
                ok = driver.execute_script(
                    "return !!(document.querySelector('[data-pagelet]')||document.querySelector('[role=\"feed\"]')||document.querySelector('[role=\"article\"]'))"
                )
                if ok:
                    _isleep(0.5, ev)
                    return
        except Exception:
            pass
        _isleep(0.3, ev)
    _isleep(2, ev)


def is_browser_available(n):
    paths = {
        "edge": [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ],
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
    }
    return any(os.path.exists(p) for p in paths.get(n, [])) or bool(
        shutil.which("msedge" if n == "edge" else "chrome")
        or shutil.which("edge" if n == "edge" else "google-chrome")
    )


def is_browser_running(b):
    try:
        exe = "msedge.exe" if b == "edge" else "chrome.exe"
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"], stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        return exe.lower() in out.lower()
    except Exception:
        return False


def get_profile_path(b):
    base = os.environ.get("LOCALAPPDATA", "")
    p = (
        os.path.join(base, "Microsoft", "Edge", "User Data")
        if b == "edge"
        else os.path.join(base, "Google", "Chrome", "User Data")
    )
    return p if os.path.isdir(p) else None


def _list_pids(b):
    exe = "msedge.exe" if b == "edge" else "chrome.exe"
    pids = set()
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
        ).decode(errors="ignore")
        for l in out.splitlines():
            m = re.match(r'^"[^"]+","(\d+)"', l.strip())
            if m:
                pids.add(int(m.group(1)))
    except Exception:
        pass
    return pids


def _find_child_pids(svc, b):
    exe = "msedge.exe" if b == "edge" else "chrome.exe"
    pids = set()
    try:
        out = subprocess.check_output(
            [
                "wmic",
                "process",
                "where",
                f"ParentProcessId={svc} and Name='{exe}'",
                "get",
                "ProcessId",
                "/VALUE",
            ],
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
        ).decode(errors="ignore")
        for m in re.finditer(r"ProcessId=(\d+)", out):
            pids.add(int(m.group(1)))
    except Exception:
        pass
    return pids


def _hide_pid(pid):
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        u32 = ctypes.windll.user32
        PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        gl = getattr(u32, "GetWindowLongPtrW", u32.GetWindowLongW)
        sl = getattr(u32, "SetWindowLongPtrW", u32.SetWindowLongW)
        for _ in range(60):
            found = []

            def cb(h, _, f=found):
                tp = wintypes.DWORD()
                u32.GetWindowThreadProcessId(h, ctypes.byref(tp))
                f.append(h) if tp.value == pid and u32.IsWindowVisible(h) else None
                return True

            u32.EnumWindows(PROC(cb), 0)
            if found:
                [
                    sl(h, -20, (gl(h, -20) & ~0x40000) | 0x80) or u32.ShowWindow(h, 0)
                    for h in found
                ]
                return True
            time.sleep(0.1)
    except Exception:
        pass
    return False


def _hide_new(before, b, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        new = [p for p in _list_pids(b) if p not in before]
        if any(_hide_pid(p) for p in new):
            return
        time.sleep(0.1)


def build_driver(headless, browser="edge", profile_dir=None):
    BASE = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-notifications",
        "--disable-gpu",
        "--disable-logging",
        "--log-level=3",
        "--silent",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-debugging-port=0",
        "--disable-blink-features=AutomationControlled",
        "--lang=vi-VN",
    ]
    b = browser.lower()
    Opts = EdgeOptions if b == "edge" else ChromeOptions
    Svc = EdgeService if b == "edge" else ChromeService
    Drv = webdriver.Edge if b == "edge" else webdriver.Chrome

    def _make(flag, extra):
        o = Opts()
        if flag:
            o.add_argument(flag)
        for a in BASE + extra:
            o.add_argument(a)
        if profile_dir:
            o.add_argument(f"--user-data-dir={profile_dir}")
            o.add_argument("--profile-directory=Default")
        else:
            o.add_argument("--disable-extensions")
        o.add_experimental_option(
            "excludeSwitches", ["enable-automation", "enable-logging"]
        )
        o.add_experimental_option("useAutomationExtension", False)
        dn = open(os.devnull, "w")
        _devnull.append(dn)
        svc = Svc(log_output=dn)
        if b == "edge":
            svc.creation_flags = 0x08000000
        d = Drv(options=o, service=svc)
        d.execute_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        return d

    HL = [
        "--window-size=1920,1080",
        "--no-zygote",
        "--disable-software-rasterizer",
        "--disable-setuid-sandbox",
    ]
    PU = ["--window-size=2560,1600", "--start-maximized"]
    HI = ["--window-size=1280,900", "--window-position=-32000,-32000"]
    if profile_dir:
        if headless:
            for f in ("--headless=new", "--headless"):
                try:
                    return _make(f, HL)
                except Exception:
                    pass
        before = _list_pids(b)
        d = _make(None, HI if headless else PU)
        if headless:
            try:
                child = set()
                for _ in range(30):
                    child = _find_child_pids(d.service.process.pid, b)
                    if child:
                        break
                    time.sleep(0.1)
                for p in child or _list_pids(b) - before:
                    _hide_pid(p)
                if not child:
                    _hide_new(before, b)
            except Exception:
                _hide_new(before, b)
        return d
    if not headless:
        return _make(None, PU)
    for f in ("--headless=new", "--headless=old", "--headless"):
        try:
            return _make(f, HL)
        except Exception:
            pass
    return _make(None, PU)


def _ns(t):
    return re.sub(r"\s+", " ", t or "").strip()


def _nf(t):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", (t or "").strip().lower())
        if unicodedata.category(c) != "Mn"
    )


def _restore_emoji(tag):
    for img in tag.find_all("img"):
        alt = img.get("alt", "").strip()
        img.replace_with(alt) if alt and len(alt) <= 4 else img.decompose()


def _own_text(art, child_ids):
    parts, last = [], None
    btn_roles = ("button", "menu", "menuitem", "menuitemradio", "option")
    for s in art.find_all(string=True):
        p = getattr(s, "parent", None)
        if not p or p.name in ("script", "style"):
            continue
        if any(id(pp) in child_ids for pp in p.parents if pp is not art):
            continue
        txt_nf = _nf(_ns(str(s)))
        if p.get("role") in btn_roles and txt_nf not in ("xem them", "see more"):
            continue
        if any(
            pp.get("role") in btn_roles and txt_nf not in ("xem them", "see more")
            for pp in p.parents
        ):
            continue
        t = _ns(str(s))
        if t and t != last and t.lower() not in ("xem thêm", "see more", "xem them"):
            parts.append(t)
            last = t
    return " ".join(parts)


def _extract_author(art):
    bad = {"like", "reply", "share", "comment", "thich", "tra loi", "chia se"}
    for tag in art.find_all(["a", "span", "strong", "b"]):
        if tag.get("role") in ("button", "menu", "menuitem", "menuitemradio", "option"):
            continue
        t = _ns(tag.get_text(separator=" ", strip=True))
        if not t or len(t) > 120 or _nf(t) in bad:
            continue
        t = _RE_TOPUI.sub("", t).strip()
        t = _RE_BADGE.sub("", t).strip()
        t = _RE_AUTHOR_TS.sub("", t).strip()
        t = _RE_AUTHOR_SUF.sub("", t).strip()
        if t and len(t) <= 80:
            return t
    return "Anon"


def _strip_author(text, author):
    if not author or author == "Anon":
        return text
    for t in (text, text.lstrip("\xb7- |,")):
        if t.startswith(author):
            return t[len(author) :].strip()
    m = re.match(
        re.escape(author) + r"\s*\d*\s*(?:giờ|phút|ngày|tuần|tháng|năm)?\s*",
        text,
        re.IGNORECASE,
    )
    if m and m.start() == 0:
        return text[m.end() :].strip()
    idx = text.find(author)
    if 0 <= idx <= 3:
        return (text[:idx] + text[idx + len(author) :]).strip()
    return text


def _clean(text, author):
    c = _RE_FB_ART.sub(" ", text)
    c = _ns(c)
    c = _RE_VIDEO.sub("", c)
    c = _RE_TIME_INLINE.sub("", c)
    c = _RE_DATE_SHARE.sub("", c)
    c = _RE_SHARE.sub("", c)
    c = _RE_POST_TAIL.sub("", c)
    c = _RE_TOPUI.sub("", c)
    c = _RE_BADGE.sub("", c)
    c = _RE_IMG.sub("", c)
    c = _strip_author(c, author)
    for rx in (_RE_TIME, _RE_REACT, _RE_TRAIL):
        c = rx.sub("", c)
    c = c.lstrip("\xb7- |,·").strip()
    if re.fullmatch(r"\d+\s*(?:giờ|phút|ngày|tuần|tháng|năm|h|m|s)", c, re.IGNORECASE):
        return ""
    return c


def parse_comments(html, master, keys, ev=None):
    soup = BeautifulSoup(html, "lxml")
    all_arts = soup.find_all("div", attrs={"role": "article"})
    if not all_arts:
        all_arts = soup.find_all(
            "div", attrs={"data-ad-rendering-role": "comment"}
        ) or soup.find_all("div", attrs={"aria-label": True})
    art_id_set = {id(a) for a in all_arts}
    nested = [a for a in all_arts if any(id(p) in art_id_set for p in a.parents)]
    arts = nested if nested else all_arts
    cur, seen, nc, uc = [], set(), 0, 0
    for art in arts:
        if ev and ev.is_set():
            break
        try:
            cids = {id(c) for c in art.find_all("div", attrs={"role": "article"})}
            _restore_emoji(art)
            author = _extract_author(art)
            content = _clean(_ns(_own_text(art, cids)), author)
            if not content:
                continue
            key = f"{author}_{content[:240]}".lower()
            if key not in seen:
                seen.add(key)
                cur.append(key)
            if key not in master:
                master[key] = {"Author": author, "Content": content}
                nc += 1
            elif len(content) > len(master[key]["Content"]):
                master[key]["Content"] = content
                uc += 1
        except Exception:
            continue
    merged = list(dict.fromkeys([k for k in keys if k not in seen] + cur))
    keys.clear()
    keys.extend(merged)
    return nc, uc


def scroll_and_metrics(driver, step=900):
    try:
        m = driver.execute_script(JS_SCROLL, step)
        if m:
            return (
                m.get("moved", False),
                int(m.get("arts") or 0),
                int(m.get("height") or 0),
                bool(m.get("atBottom", False)),
            )
    except Exception:
        pass
    return False, 0, 0, False


def expand_text(driver, ev=None):
    try:
        n = int(driver.execute_script(JS_EXPAND_SM) or 0)
        if n:
            _isleep(0.4, ev)
        return n
    except Exception:
        return 0


def load_more(driver, ev=None):
    try:
        n = int(driver.execute_script(JS_LOAD_MORE) or 0)
        if n:
            _isleep(0.9, ev)
        return n
    except Exception:
        return 0


def set_all_comments_mode(driver, ev=None):
    EX = ["moi nhat", "newest", "phu hop", "relevant"]
    TR = [
        "most relevant",
        "phu hop",
        "top comments",
        "binh luan hang dau",
        "hang dau",
        "mac dinh",
        "default",
        "moi nhat",
        "newest",
        "top fan",
        "highlighted",
    ]
    AT = ["all comments", "tat ca binh luan", "tất cả bình luận", "tất cả"]
    if ev and ev.is_set():
        return False
    try:
        for btn in driver.find_elements(
            By.XPATH, "//*[@role='button' or self::button or @aria-haspopup='menu']"
        ):
            t = _nf(btn.text)
            if any(k in t for k in TR) or any(k in t for k in AT):
                if any(k in t for k in AT) and not any(k in t for k in EX):
                    return True
                break
    except Exception:
        pass
    for _ in range(3):
        if ev and ev.is_set():
            return False
        opened = False
        try:
            btns = driver.find_elements(
                By.XPATH, "//*[@role='button' or self::button or @aria-haspopup='menu']"
            )
        except Exception:
            btns = []
        for btn in btns:
            try:
                t = _nf(btn.text)
                if t and len(t) < 40 and any(k in t for k in TR):
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center',behavior:'instant'});",
                        btn,
                    )
                    _isleep(0.5, ev)
                    if ev and ev.is_set():
                        return False
                    driver.execute_script("arguments[0].click();", btn)
                    opened = True
                    _isleep(1.0, ev)
                    break
            except Exception:
                continue
        if not opened:
            return False
        try:
            opts = driver.find_elements(
                By.XPATH,
                "//*[@role='menuitemradio' or @role='menuitem' or @role='option']",
            ) or driver.find_elements(By.XPATH, "//*[@role='button' or self::button]")
        except Exception:
            opts = []
        for o in opts:
            try:
                t = _nf(o.text)
                if t and any(k in t for k in AT) and not any(k in t for k in EX):
                    driver.execute_script("arguments[0].click();", o)
                    _isleep(2.0, ev)
                    return True
            except Exception:
                continue
        _isleep(0.5, ev)
    return False


def _scrape_url(url, driver, limit, ev, state=None):
    driver.get(url)
    _wait_fb(driver, ev)
    if ev.is_set():
        return [], True
    for lbl in ["Dong", "Close", "Not Now", "Dismiss", "Maybe Later"]:
        try:
            for b in driver.find_elements(By.XPATH, f"//*[@aria-label='{lbl}']"):
                b.click()
                _isleep(0.2, ev)
        except Exception:
            pass
    for _ in range(5):
        if ev.is_set():
            break
        if not set_all_comments_mode(driver, ev):
            _isleep(1.0, ev)
            continue
        _wait_fb(driver, ev)
        _isleep(2.0, ev)
        if set_all_comments_mode(driver, ev):
            break
        _isleep(1.0, ev)
    master = {}
    gkeys = []
    no_move = no_new = idle = last_h = ab_count = scroll_i = 0
    early = False
    ended = False

    def _limit_hit():
        return limit and len(gkeys) >= limit

    def _drain_replies(ev, rounds=10):
        if _limit_hit():
            return 0
        prev_arts = 0
        no_chg = 0
        total = 0
        for _ in range(rounds):
            if ev.is_set() or _limit_hit():
                break
            lm = load_more(driver, ev)
            total += lm
            if ev.is_set() or _limit_hit():
                break
            try:
                cur_arts = driver.execute_script(
                    "return document.querySelectorAll('[role=\"article\"]').length"
                )
            except Exception:
                cur_arts = prev_arts
            if lm == 0 and cur_arts == prev_arts:
                no_chg += 1
                if no_chg >= 2:
                    break
            else:
                no_chg = 0
            prev_arts = cur_arts
            parse_comments(driver.page_source, master, gkeys, ev)
            if state:
                state["_found"] = len(gkeys)
        return total

    for scroll_i in range(MAX_SCROLLS):
        if ev.is_set():
            early = True
            break
        if _limit_hit():
            break
        expand_text(driver, ev)
        if scroll_i % 4 == 0:
            _drain_replies(ev)
        if ev.is_set():
            early = True
            break
        if _limit_hit():
            break
        moved, _, cur_h, at_bottom = scroll_and_metrics(driver)
        _isleep(SCROLL_PAUSE, ev)
        if ev.is_set():
            early = True
            break
        new, upd = parse_comments(driver.page_source, master, gkeys, ev)
        if state:
            state["_found"] = len(gkeys)
        stale = not moved or abs(cur_h - last_h) < 5
        no_move = 0 if not stale else no_move + 1
        no_new = 0 if (new or upd) else no_new + 1
        idle = 0 if (not stale or new or upd) else idle + 1
        ab_count = ab_count + 1 if at_bottom else 0
        last_h = cur_h
        if ab_count >= 3 and no_new >= 3:
            _drain_replies(ev, rounds=6)
            nf, uf = parse_comments(driver.page_source, master, gkeys, ev)
            if state:
                state["_found"] = len(gkeys)
            if nf == 0 and uf == 0:
                ended = True
                break
            ab_count = 0
            no_new = 0
        elif no_move >= 5 and no_new >= 5:
            got = False
            for _a in range(3):
                if ev.is_set() or _limit_hit():
                    break
                _drain_replies(ev, rounds=6)
                _isleep(2.0, ev)
                n2, u2 = parse_comments(driver.page_source, master, gkeys, ev)
                if state:
                    state["_found"] = len(gkeys)
                if n2 or u2:
                    no_move = no_new = idle = 0
                    got = True
                    break
                m2, _, h2, ab2 = scroll_and_metrics(driver)
                _isleep(0.6, ev)
                if m2 and abs(h2 - last_h) > 10:
                    last_h = h2
                    no_move = 0
                    n3, u3 = parse_comments(driver.page_source, master, gkeys, ev)
                    if state:
                        state["_found"] = len(gkeys)
                    if n3 or u3:
                        no_new = 0
                        got = True
                        break
            if not got:
                ended = True
                break
        if idle >= 12 or (no_move >= 18 and no_new >= 14):
            ended = True
            break
        if _limit_hit():
            break

    if not _limit_hit() and not ended:
        _drain_replies(ev, rounds=14)
        for _ in range(2):
            if ev.is_set() or _limit_hit():
                break
            expand_text(driver, ev)
            load_more(driver, ev)
            _isleep(1.0, ev)
            parse_comments(driver.page_source, master, gkeys, ev)
            if state:
                state["_found"] = len(gkeys)
    out = [
        {"ID": i + 1, "Author": master[k]["Author"], "Content": master[k]["Content"]}
        for i, k in enumerate(gkeys)
        if k in master
    ]
    return (out[:limit] if limit else out), early


def _next_path(d=None):
    d = Path(d) if d else OUTPUT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return next(
        d / f"comments_{i}.json"
        for i in range(1, 99999)
        if not (d / f"comments_{i}.json").exists()
    )


def _save(comments, d=None):
    p = _next_path(d)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)
    return p


def _box(cols, title="", bc=C_DIM):
    W = max((_pw(c) for c in cols), default=0)
    if title:
        W = max(W, _vw(title) + 6)
    if title:
        pad = W + 2 - _vw(title) - 4
        lp = pad // 2
        rp = pad - lp
        top = f"  {bc}╔{'═'*lp}  {title}  {'═'*rp}╗{C_RESET}"
    else:
        top = f"  {bc}╔{'═'*(W+2)}╗{C_RESET}"
    rows = [
        f"  {bc}║{C_RESET} {col}{' '*max(0,W-_pw(col))} {bc}║{C_RESET}" for col in cols
    ]
    bot = f"  {bc}╚{'═'*(W+2)}╝{C_RESET}"
    return "\n".join([top] + rows + [bot])


def _drow(col, W, bc=C_DIM):
    return f"  {bc}║{C_RESET} {col}{' '*max(0,W-_pw(col))} {bc}║{C_RESET}"


def _opt(num, label, desc="", icon="", nbcol=C_DIM):
    icon_part = f"  {nbcol}{icon}{C_RESET}" if icon else ""
    desc_part = f"  {C_DIM}{desc}{C_RESET}" if desc else ""
    return f"  {C_CYAN}{num}{C_RESET}  {C_DIM}·{C_RESET}  {C_BOLD}{C_WHITE}{label}{C_RESET}{icon_part}{desc_part}"


def _opt_exit(num="3"):
    return f"  {C_CYAN}{num}{C_RESET}  {C_DIM}·{C_RESET}  {C_BOLD}{C_RED}Exit{C_RESET}"


def _ask(valid):
    UP_CLEAR = "\033[1A\r\033[2K"
    sys.stdout.write(f"\n  {C_YELLOW}›{C_RESET} ")
    sys.stdout.flush()
    while True:
        v = input("").strip()
        if valid(v):
            return v
        sys.stdout.write(f"{UP_CLEAR}  {C_YELLOW}›{C_RESET} ")
        sys.stdout.flush()


def _print_result(count, path, early):
    p = path.resolve()
    bc = C_YELLOW if early else C_GREEN
    st = "stopped early" if early else "completed"
    col1 = f"  {C_BOLD}{bc}{count:,}{C_RESET} {C_DIM}comments · {st}{C_RESET}"
    col2 = f"  {C_DIM}›{C_RESET}  {C_BOLD}{C_WHITE}{p.name}{C_RESET}"
    W = max(_pw(col1), _pw(col2)) + 2
    os.system(CLR)
    print(
        f"\n  {C_BOLD}{C_YELLOW}◈  STOPPED EARLY{C_RESET}\n"
        if early
        else f"\n  {C_BOLD}{C_GREEN}✦  DONE{C_RESET}\n"
    )
    print(f"  {bc}╔{'═'*(W+2)}╗{C_RESET}")
    print(_drow(col1, W, bc))
    print(f"  {bc}╠{'═'*(W+2)}╣{C_RESET}")
    print(_drow(col2, W, bc))
    print(f"  {bc}╚{'═'*(W+2)}╝{C_RESET}")
    print(f"\n  {C_GREEN}✓{C_RESET}  {C_DIM}{p.parent}{os.sep}{C_RESET}\n")
    try:
        os.startfile(str(p))
    except Exception:
        pass


def _print_batch(results, out_dir):
    PREV = 3
    shown = [r for r in results if r["count"] > 0]
    total = sum(r["count"] for r in results)
    skip = len(results) - len(shown)
    opath = Path(out_dir).resolve()
    bc = C_GREEN

    def _rcol(i, r):
        fn = Path(r["file"]).name if r["file"] else "—"
        nc = _row_color(i, len(shown))
        return f"  {C_BOLD}{nc}{r['count']:>5,}{C_RESET}  {C_DIM}›{C_RESET}  {C_WHITE}{fn}{C_RESET}"

    def render(exp=False):
        rows = shown if exp else shown[:PREV]
        ov = 0 if exp or len(shown) <= PREV else len(shown) - PREV
        col0 = f"  {C_BOLD}{C_CYAN}{len(shown)}{C_RESET}{C_DIM}/{len(results)}{C_RESET} {C_DIM}posts{C_RESET}  {C_DIM}·{C_RESET}  {C_BOLD}{C_CYAN}{total:,}{C_RESET} {C_DIM}comments total{C_RESET}"
        row_cols = [_rcol(i, r) for i, r in enumerate(rows)]
        skip_col = (
            f"  {C_YELLOW}▸ {skip} skipped{C_RESET}  {C_DIM}no comments{C_RESET}"
            if skip
            else None
        )
        ov_col = (
            f"  {C_DIM}+{C_RESET} {C_CYAN}{ov}{C_RESET} {C_DIM}more{C_RESET}"
            if ov
            else None
        )
        all_cols = (
            [col0]
            + row_cols
            + ([skip_col] if skip_col else [])
            + ([ov_col] if ov_col else [])
        )
        W = max(_pw(c) for c in all_cols)
        lines = [f"  {bc}╔{'═'*(W+2)}╗{C_RESET}"]
        lines += [_drow(col0, W, bc), f"  {bc}╠{'═'*(W+2)}╣{C_RESET}"]
        for c in row_cols:
            lines.append(_drow(c, W, bc))
        if skip_col:
            lines.append(_drow(skip_col, W, bc))
        if ov_col:
            lines.append(_drow(ov_col, W, bc))
        lines.append(f"  {bc}╚{'═'*(W+2)}╝{C_RESET}")
        return lines

    def show(exp):
        os.system(CLR)
        print(f"\n  {C_BOLD}{C_GREEN}✦  BATCH COMPLETE{C_RESET}\n")
        for l in render(exp):
            print(l)
        if len(shown) > PREV:
            print(
                f"\n  {C_DIM}[{C_RESET}{C_YELLOW}M{C_RESET}{C_DIM}] expand/collapse   [{C_RESET}{C_YELLOW}Q{C_RESET}{C_DIM}] exit{C_RESET}"
            )
        print(
            f"\n  {C_DIM}{opath.parent}{os.sep}{C_RESET}{C_BOLD}{C_WHITE}{opath.name}{C_RESET}"
        )
        print(f"\n  {C_GREEN}✓{C_RESET}  {C_DIM}all results saved{C_RESET}\n")

    exp = False
    show(exp)
    if len(shown) > PREV:
        try:
            import msvcrt

            while True:
                if msvcrt.kbhit():
                    ch = msvcrt.getch().lower()
                    if ch == b"m":
                        exp = not exp
                        show(exp)
                    elif ch in (b"\r", b"\x1b", b"q"):
                        break
                time.sleep(0.05)
        except Exception:
            pass
    try:
        os.startfile(str(opath))
    except Exception:
        pass


def _animate(stop, usr, state):
    GLOW = "░▒▓█▓▒░"
    GW = len(GLOW)
    is_b = state["post_total"] > 1
    nbcol = state.get("nbcol", C_CYAN)
    TOTAL = 9 if is_b else 8
    PAD = " " * 40
    tick = pos = 0
    direction = 1
    spin_col = _rndcol()
    bar_col = _rndcol()
    sys.stdout.write("\n" * TOTAL)
    sys.stdout.flush()
    while not stop.is_set():
        sys.stdout.write(f"\033[{TOTAL}A")
        loading = state.get("loading", False)
        first = state.get("first_load", True)
        pi = state["post_idx"]
        pt = state["post_total"]
        found = state.get("_found", 0)
        done = state.get("done", False)
        lim = state["limit"]
        if tick % 8 == 0:
            spin_col = _rndcol()
        if tick % 18 == 0:
            bar_col = _rndcol()
        sp = f"{spin_col}{SPINNERS[tick%10]}{C_RESET}"
        if loading and first:
            st_plain = "  initializing browser..."
            st = f"  {C_DIM}initializing browser...{C_RESET}"
        elif lim:
            n = min(found, lim)
            st_plain = f"  collecting  {n:,}/{lim:,}"
            fl = int(10 * n / lim)
            pg = C_GREEN + "▪" * fl + C_RESET + C_DIM + "▫" * (10 - fl) + C_RESET
            st = f"  {sp}  {C_DIM}collecting{C_RESET}  {pg}  {C_BOLD}{C_WHITE}{n:,}{C_RESET}{C_DIM}/{lim:,}{C_RESET}"
        else:
            st_plain = f"  collecting  {found:,} comments found"
            st = f"  {sp}  {C_DIM}collecting{C_RESET}  {nbcol}▸{C_RESET}  {C_BOLD}{C_WHITE}{found:,}{C_RESET} {C_DIM}found{C_RESET}"
        title_plain = (
            f"FB COMMENT SCRAPER  ·  {pi}/{pt}" if is_b else "FACEBOOK COMMENT SCRAPER"
        )
        hk_plain = "  [Q] stop & save early"
        BAR_W = max(len(st_plain) + 2, len(hk_plain) + 2, len(title_plain) + 6, 36)
        bc2 = ["░"] * BAR_W
        for i, ch in enumerate(GLOW):
            ix = pos + i
            if 0 <= ix < BAR_W:
                bc2[ix] = ch
        bar = (
            C_DIM
            + "".join(bc2[:pos])
            + C_RESET
            + bar_col
            + "".join(bc2[pos : pos + GW])
            + C_RESET
            + C_DIM
            + "".join(bc2[pos + GW :])
            + C_RESET
        )
        pad_t = BAR_W + 2 - len(title_plain) - 4
        lp = pad_t // 2
        rp = pad_t - lp
        top_title = f"  {C_FRAME}╔{'═'*lp}  {C_BOLD}{C_WHITE}{title_plain}{C_RESET}{C_FRAME}  {'═'*rp}╗{C_RESET}"
        mid = f"  {C_FRAME}╠{'═'*(BAR_W+2)}╣{C_RESET}"
        bot2 = f"  {C_FRAME}╚{'═'*(BAR_W+2)}╝{C_RESET}"
        hk = f"  {C_DIM}[{C_RESET}{C_YELLOW}Q{C_RESET}{C_DIM}]{C_RESET} {C_DIM}stop & save early{C_RESET}"
        bl = f"\r{PAD}\n"
        if is_b:
            BW = min(BAR_W - 4, 30)
            if done:
                bp = C_GREEN + "▰" * BW + C_RESET
                ps = f"{C_BOLD}{C_GREEN}100%{C_RESET}"
            else:
                raw = (pi - 1) / pt
                fl2 = int(raw * BW)
                pct = int(raw * 100)
                bp = nbcol + "▰" * fl2 + C_RESET + C_DIM + "▱" * (BW - fl2) + C_RESET
                ps = f"{C_DIM}{pct:>3}%{C_RESET}"
            bl = f"\r  {bp}  {ps}{PAD}\n"
        sys.stdout.write(
            f"\r\n\r{top_title}{PAD}\n\r{mid}\n\r  {C_FRAME}║{C_RESET} {bar} {C_FRAME}║{C_RESET}\n\r{bot2}\n\r{st}{PAD}\n"
            + bl
            + f"\r{hk}{PAD}\n"
        )
        sys.stdout.flush()
        pos += direction
        if pos >= BAR_W - GW or pos <= 0:
            direction *= -1
        tick += 1
        time.sleep(0.07)


def _kb(stop, usr):
    try:
        import msvcrt

        while not stop.is_set():
            if msvcrt.kbhit() and msvcrt.getch().lower() == b"q":
                usr.set()
                return
            time.sleep(0.05)
    except Exception:
        pass


def scrape(url, headless, limit=0, browser="edge", profile_dir=None):
    os.system(CLR)
    state = {
        "driver": None,
        "limit": limit,
        "post_idx": 1,
        "post_total": 1,
        "loading": True,
        "first_load": True,
        "url_id": 0,
        "nbcol": _bc(browser),
    }
    stop, usr = threading.Event(), threading.Event()
    anim = threading.Thread(target=_animate, args=(stop, usr, state), daemon=True)
    anim.start()
    threading.Thread(target=_kb, args=(stop, usr), daemon=True).start()
    driver = None
    try:
        try:
            driver = build_driver(headless, browser, profile_dir)
        except Exception as e:
            stop.set()
            anim.join(1)
            os.system(CLR)
            print(f"\n  {C_RED}✗{C_RESET}  Failed to start browser: {e}\n")
            return None, 0, False
        state.update(driver=driver, _found=0, loading=False, first_load=False)
        comments, early = _scrape_url(url, driver, limit, usr, state)
        stop.set()
        anim.join(1)
        os.system(CLR)
        if not comments:
            return None, 0, early
        out = _save(comments)
        return out, len(comments), early
    finally:
        stop.set()
        anim.join(1)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_batch(
    urls, headless, limit=0, browser="edge", out_dir=None, profile_dir=None
):
    os.system(CLR)
    state = {
        "driver": None,
        "limit": limit,
        "post_idx": 1,
        "post_total": len(urls),
        "loading": True,
        "first_load": True,
        "url_id": 0,
        "done": False,
        "nbcol": _bc(browser),
    }

    def _ab():
        box = [None]
        t = threading.Thread(target=lambda: box.__setitem__(0, _tb()), daemon=True)
        t.start()
        return t, box

    def _tb():
        try:
            return build_driver(headless, browser, profile_dir)
        except Exception:
            return None

    stop, usr = threading.Event(), threading.Event()
    anim = threading.Thread(target=_animate, args=(stop, usr, state), daemon=True)
    anim.start()
    threading.Thread(target=_kb, args=(stop, usr), daemon=True).start()
    bt, dbox = _ab()
    bt.join()
    results = []
    for idx, url in enumerate(urls, 1):
        state["post_idx"] = state["url_id"] = idx
        driver = dbox[0]
        if not driver:
            results.append({"file": None, "count": 0})
            if idx < len(urls) and not usr.is_set():
                bt, dbox = _ab()
                bt.join()
            continue
        state.update(_found=0, loading=False, first_load=False, driver=driver)
        nbt, nbox = (
            _ab()
            if not profile_dir and idx < len(urls) and not usr.is_set()
            else (None, None)
        )
        try:
            comments, _ = _scrape_url(url, driver, limit, usr, state)
            out = _save(comments, out_dir) if comments else None
            results.append({"file": str(out) if out else None, "count": len(comments)})
        except Exception:
            results.append({"file": None, "count": 0})
        finally:
            state.update(driver=None, _found=0, loading=True)
            try:
                driver.quit()
            except Exception:
                pass
        if usr.is_set():
            if nbt:
                nbt.join(30)
            try:
                nbox[0].quit() if nbox else None
            except Exception:
                pass
            break
        if nbt:
            nbt.join()
            dbox = nbox
        elif profile_dir and idx < len(urls) and not usr.is_set():
            bt, dbox = _ab()
            bt.join()
    state["done"] = True
    stop.set()
    anim.join(1)
    return results


def _ask_profile(browser, nbcol):
    if not get_profile_path(browser):
        return None
    profile_path = get_profile_path(browser)
    items = [
        _opt("1", "Yes", "use logged-in profile"),
        _opt("2", "No", "anonymous · faster start"),
        _opt_exit("3"),
    ]
    while True:
        print(_box(items, title="LOGGED-IN PROFILE", bc=nbcol))
        print(f"\n  {C_DIM}logged-in avoids comment limits & login walls{C_RESET}")
        a = _ask(lambda v: v in ("1", "2", "3"))
        if a == "3":
            sys.exit(0)
        if a == "2":
            return None
        if a == "1":
            break
    os.system(CLR)
    print(f"\n  {C_BOLD}{nbcol}◈  LOGGED-IN MODE{C_RESET}\n")
    print(
        f"  {C_YELLOW}⚠{C_RESET}  {C_BOLD}Close all {browser.upper()} windows before continuing{C_RESET}  {C_DIM}· cannot run alongside an existing session{C_RESET}\n"
    )
    skip = threading.Event()

    def _w():
        try:
            import msvcrt

            while not skip.is_set():
                if msvcrt.kbhit() and msvcrt.getch() in (b"\r", b"\n"):
                    skip.set()
                    return
                time.sleep(0.05)
        except Exception:
            pass

    threading.Thread(target=_w, daemon=True).start()
    for i in range(5, 0, -1):
        if skip.is_set():
            break
        sys.stdout.write(
            f"\r  {C_DIM}Continuing in {C_RESET}{C_YELLOW}{i}{C_RESET}{C_DIM}s... (Enter to skip){C_RESET}  "
        )
        sys.stdout.flush()
        for _ in range(20):
            if skip.is_set():
                break
            time.sleep(0.05)
    skip.set()
    sys.stdout.write(f"\r{' '*52}\r")
    sys.stdout.flush()
    if is_browser_running(browser):
        print(
            f"\n  {C_RED}✗{C_RESET}  {browser.upper()} is still running. Please close it and try again.\n"
        )
        sys.exit(1)
    return profile_path


def _main_run():
    avail = [
        (c, n) for c, n in [("1", "edge"), ("2", "chrome")] if is_browser_available(n)
    ]
    if not avail:
        print(
            f"\n  {C_RED}✗{C_RESET}  No supported browser found. Install Edge or Chrome first.\n"
        )
        sys.exit(1)
    os.system(CLR)

    def _bi_row(c, n):
        nbcol = _bc(n)
        icon = "🔷" if n == "edge" else "🟢"
        return f"  {C_CYAN}{c}{C_RESET}  {C_DIM}·{C_RESET}  {C_BOLD}{C_WHITE}{n.upper()}{C_RESET}  {nbcol}{icon}{C_RESET}"

    bi = [_bi_row(c, n) for c, n in avail]
    if len(avail) == 1:
        browser = avail[0][1]
        nbcol = _bc(browser)
        bi_sel = [_bi_row(c, n) + f"  {C_GREEN}selected{C_RESET}" for c, n in avail]
        print(_box(bi_sel, title="FACEBOOK COMMENT SCRAPER", bc=C_FRAME))
        time.sleep(1.0)
        os.system(CLR)
    else:
        valid_ch = [c for c, _ in avail]
        print(_box(bi, title="FACEBOOK COMMENT SCRAPER", bc=C_FRAME))
        ch = _ask(lambda v: v in valid_ch)
        browser = next(n for c, n in avail if c == ch)
        os.system(CLR)
    nbcol = _bc(browser)
    mi = [
        _opt("1", "Pop-up", "browser window visible"),
        _opt("2", "Background", "runs silently"),
        _opt_exit("3"),
    ]
    print(
        f"\n  {C_BOLD}{nbcol}◈  {browser.upper()}{C_RESET}  {C_DIM}·{C_RESET}  {C_BOLD}{nbcol}ready{C_RESET}\n"
    )
    print(_box(mi, title="MODE", bc=nbcol))
    m = _ask(lambda v: v in ("1", "2", "3"))
    if m == "3":
        sys.exit(0)
    headless = m == "2"
    mode_lbl = "Background" if headless else "Pop-up"
    os.system(CLR)
    print(
        f"\n  {C_BOLD}{nbcol}◈  {browser.upper()}{C_RESET}  {C_DIM}·{C_RESET}  {C_BOLD}{nbcol}{mode_lbl}{C_RESET}\n"
    )
    profile_dir = _ask_profile(browser, nbcol)
    os.system(CLR)
    sfx = f"  {C_DIM}·{C_RESET}  {C_GREEN}logged-in{C_RESET}" if profile_dir else ""
    print(
        f"\n  {C_BOLD}{nbcol}◈  {browser.upper()}{C_RESET}  {C_DIM}·{C_RESET}  {C_BOLD}{nbcol}{mode_lbl}{C_RESET}{sfx}\n"
    )
    url_items = [
        f"  {C_BOLD}{C_WHITE}paste a Facebook post URL{C_RESET}",
        f"  {C_DIM}.txt · one URL per line{C_RESET}  {nbcol}→ batch{C_RESET}",
    ]
    print(_box(url_items, bc=nbcol))
    print(f"  {C_DIM}Ctrl + C{C_RESET} {C_YELLOW}to exit{C_RESET}")
    if len(sys.argv) > 1:
        raw = re.sub(r"^&\s*", "", sys.argv[1]).strip().strip('"').strip("'")
        txt = Path(raw)
        is_batch = txt.suffix.lower() == ".txt" and txt.exists()
    else:

        def _valid_url(v):
            v = re.sub(r"^&\s*", "", v).strip().strip('"').strip("'")
            p = Path(v)
            return p.suffix.lower() == ".txt" and p.exists() or v.startswith("http")

        raw = re.sub(r"^&\s*", "", _ask(_valid_url)).strip().strip('"').strip("'")
        txt = Path(raw)
        is_batch = txt.suffix.lower() == ".txt" and txt.exists()

    def _valid_num(v):
        return v == "" or v.isdigit()

    if is_batch:
        urls = [
            l.strip()
            for l in txt.read_text(encoding="utf-8").splitlines()
            if l.strip().startswith("http")
        ]
        if not urls:
            print(f"\n  {C_RED}✗{C_RESET}  No valid URLs found in file.\n")
            sys.exit(1)
        print(
            f"\n  {C_DIM}found{C_RESET}  {C_BOLD}{C_WHITE}{len(urls)}{C_RESET}  {C_DIM}URLs  ·  how many comments per post?{C_RESET}"
        )
        print(
            f"  {C_DIM}number or{C_RESET} {C_YELLOW}ENTER{C_RESET} {C_DIM}= all{C_RESET}"
        )
        rl = _ask(_valid_num)
    else:
        urls = [raw]
        print(
            f"\n  {C_DIM}how many comments?  number or{C_RESET} {C_YELLOW}ENTER{C_RESET} {C_DIM}= all{C_RESET}"
        )
        rl = _ask(_valid_num)
    limit = int(rl) if rl else 0
    if is_batch:
        od = Path(".") / "comments"
        od.mkdir(parents=True, exist_ok=True)
        results = scrape_batch(
            urls, headless, limit, browser, str(od), profile_dir=profile_dir
        )
        os.system(CLR)
        _print_batch(results, str(od))
    else:
        try:
            out, count, early = scrape(
                urls[0], headless, limit, browser, profile_dir=profile_dir
            )
            if out:
                _print_result(count, out, early)
            else:
                print(f"\n  {C_DIM}No comments found.{C_RESET}\n")
        except Exception as e:
            print(f"\n  {C_RED}✗{C_RESET}  Error: {e}\n")
            sys.exit(1)


if __name__ == "__main__":
    try:
        _main_run()
    except KeyboardInterrupt:
        sys.exit(0)
