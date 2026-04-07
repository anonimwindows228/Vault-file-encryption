import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading, os, io, json, zipfile, tempfile, sys, subprocess
from datetime import datetime
import urllib.request

APP_VERSION = "v1.5.1"
_GH_API = "https://api.github.com/repos/anonimwindows228/Vault-file-encryption/releases/latest"
_GH_RELEASES = "https://github.com/anonimwindows228/Vault-file-encryption/releases/latest"


def _check_for_update(callback):

    def _run():
        try:
            req = urllib.request.Request(_GH_API,
                                         headers={"User-Agent": "WinVFE-updater"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").strip()
            if tag and tag != APP_VERSION:
                callback(tag)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()

from crypto import encrypt_file, decrypt_file, safe_output_path, LARGE_FILE_THRESHOLD
from compress import compress_file, decompress_file, available_algorithms, read_metadata
from compress import ALGORITHMS as COMP_ALGORITHMS

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND = True
except ImportError:
    _DND = False
    TkinterDnD = None

def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel)

def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

_HISTORY_FILE = os.path.join(_app_dir(), "vault_history.json")

def append_history(entry: dict):
    history = []
    if os.path.exists(_HISTORY_FILE):
        try:
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(entry)
    try:
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# Colours

BG        = "#10182a"
BG_BOT    = "#10182a"
SURFACE2  = "#1a2744"
SURFACE3  = "#203050"
INSET     = "#0d1525"
BORDER_LO = "#080e1a"
BORDER_HI = "#3a5080"
BORDER    = "#1e2e4a"
ACCENT_A  = "#2060d0"
ACCENT_B  = "#4a9aff"
ACCENT_C  = "#6ab8ff"
ACCENT_DIM= "#152a5a"
TEXT      = "#c8d8f0"
MUTED     = "#4e6a90"
MUTED2    = "#2a3e5e"
SUCCESS   = "#30c080"
DANGER    = "#e04455"
WARN      = "#e0952a"
WHITE     = "#e8f0ff"
HDR_A     = "#1e3060"
HDR_B     = "#162448"
HDR_C     = "#16213a"
DROP_B_IDLE  = "#253a60"
DROP_B_HOV   = "#4a9aff"
DROP_BG_IDLE = "#0d1828"
DROP_BG_HOV  = "#10244a"

FONT       = ("Tahoma", 9)
FONT_SM    = ("Tahoma", 8)
FONT_BOLD  = ("Tahoma", 9, "bold")
FONT_TITLE = ("Tahoma", 13, "bold")

def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))

def lerp3(c1, c2, c3, t):
    return lerp_color(c1,c2,t*2) if t<=0.5 else lerp_color(c2,c3,(t-0.5)*2)

def draw_v3(cv, x0, y0, x1, y1, c1, c2, c3):
    h = y1-y0
    for i in range(h): cv.create_line(x0,y0+i,x1,y0+i,fill=lerp3(c1,c2,c3,i/h))

def draw_hg(cv, x0, y0, x1, y1, c1, c2):
    w = x1-x0
    for i in range(w): cv.create_line(x0+i,y0,x0+i,y1,fill=lerp_color(c1,c2,i/w))

def mkframe(parent, bg=BG, **kw):
    return tk.Frame(parent, bg=bg, **kw)

def mklabel(parent, text="", var=None, color=TEXT, font=FONT, anchor="w", bg=BG, **kw):
    cfg = dict(bg=bg, fg=color, font=font, anchor=anchor)
    return (tk.Label(parent, textvariable=var, **cfg, **kw) if var
            else tk.Label(parent, text=text, **cfg, **kw))

def thin_divider(parent, pady=3):
    tk.Frame(parent, bg=BORDER_LO, height=1).pack(fill="x", pady=(pady,0))
    tk.Frame(parent, bg=BORDER_HI, height=1).pack(fill="x", pady=(0,pady))

def _fmt_size(n):
    if n < 1024:    return f"{n} B"
    if n < 1048576: return f"{n/1024:.1f} KB"
    return f"{n/1048576:.2f} MB"

def _size_delta(src: int, dst: int) -> str:

    pct = (dst - src) / src * 100 if src else 0
    sign = "+" if pct > 0 else ""
    prec = 1 if abs(pct) < 10 else 0
    note = "  (already compressed)" if -1 < pct <= 0 else ""
    return f"{_fmt_size(src)} → {_fmt_size(dst)}  {sign}{pct:.{prec}f}%{note}"

def open_folder(path: str):

    folder = os.path.dirname(os.path.abspath(path))
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])

def _clean_path(raw):
    p = raw.strip()
    return p[1:-1] if p.startswith("{") and p.endswith("}") else p

def _parse_paths(raw: str) -> list[str]:
    paths, i = [], 0
    raw = raw.strip()
    while i < len(raw):
        if raw[i] == "{":
            end = raw.find("}", i)
            if end == -1: break
            paths.append(raw[i+1:end]); i = end + 2
        else:
            end = raw.find(" ", i)
            if end == -1: paths.append(raw[i:]); break
            paths.append(raw[i:end]); i = end + 1
    return [p for p in paths if p and os.path.isfile(p)]

class NavyEntry(tk.Entry):
    def __init__(self, parent, var, show="", **kw):
        super().__init__(parent, textvariable=var, show=show,
                         bg=INSET, fg=TEXT, insertbackground=ACCENT_C,
                         selectbackground=ACCENT_DIM, selectforeground=ACCENT_C,
                         relief="flat", font=FONT, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT_B,
                         bd=0, **kw)
        self.bind("<FocusIn>",  lambda e: self.config(highlightbackground=ACCENT_B))
        self.bind("<FocusOut>", lambda e: self.config(highlightbackground=BORDER))

class GradientButton(tk.Frame):
    def __init__(self, parent, text, command, width=120, height=24,
                 c1=ACCENT_A, c2=ACCENT_B):
        tk.Frame.__init__(self, parent, width=width, height=height,
                          bd=0, highlightthickness=0, bg=BG)
        self.pack_propagate(False)
        self._text, self._command = text, command
        self._c1, self._c2 = c1, c2
        self._bw, self._bh = width, height
        self._hover = self._pressed = False
        self._cv = tk.Canvas(self, width=width, height=height, bd=0,
                             highlightthickness=0, cursor="hand2", bg=BG)
        self._cv.pack(fill="both", expand=True)
        self._cv.bind("<Enter>",           lambda e: self._state(hover=True))
        self._cv.bind("<Leave>",           lambda e: self._state(hover=False, pressed=False))
        self._cv.bind("<ButtonPress-1>",   lambda e: self._state(pressed=True))
        self._cv.bind("<ButtonRelease-1>", lambda e: (self._state(pressed=False), command()))
        self.after(20, self._draw)

    def _state(self, **kw):
        for k, v in kw.items(): setattr(self, f"_{k}", v)
        self._draw()

    def _draw(self):
        cv = self._cv; cv.delete("all")
        w, h = self._bw, self._bh
        c1 = lerp_color(self._c1, WHITE, 0.08 if self._hover else 0)
        c2 = lerp_color(self._c2, WHITE, 0.12 if self._hover else 0)
        if self._pressed:
            c1 = lerp_color(c1, "#000000", 0.18)
            c2 = lerp_color(c2, "#000000", 0.12)
        draw_hg(cv, 0, 0, w, h, c1, c2)
        off = 1 if self._pressed else 0
        cv.create_text(w//2+off, h//2+off, text=self._text,
                       fill=WHITE, font=FONT_BOLD, anchor="center")

class ProgressDialog(tk.Toplevel):

    def __init__(self, parent, title="Working…"):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=BG)
        self.overrideredirect(False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)


        parent.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = 320, 90
        self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")

        self._msg_var = tk.StringVar(value="Starting…")
        tk.Label(self, textvariable=self._msg_var, bg=BG, fg=TEXT,
                 font=FONT, anchor="w").pack(fill="x", padx=16, pady=(14,4))

        from tkinter import ttk
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Vault.Horizontal.TProgressbar",
                        troughcolor=INSET, background=ACCENT_B,
                        bordercolor=BORDER, lightcolor=ACCENT_C, darkcolor=ACCENT_A)
        self._pb = ttk.Progressbar(self, style="Vault.Horizontal.TProgressbar",
                                   orient="horizontal", length=288, mode="determinate",
                                   maximum=100)
        self._pb.pack(padx=16, pady=(0,6))
        self._pb["value"] = 0
        self.grab_set()
        self.update()

    def update_progress(self, val: float, msg: str = ""):
        """val in [0,1]."""
        self._pb["value"] = int(val * 100)
        if msg:
            self._msg_var.set(msg)
        self.update_idletasks()

    def close(self):
        self.grab_release()
        self.destroy()

class DropZone(tk.Frame):

    def __init__(self, parent, on_file_cb, mode="any", multi=False, on_clear_cb=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cb       = on_file_cb
        self._clear_cb = on_clear_cb
        self._mode     = mode
        self._multi    = multi
        self._paths: list[str] = []
        self._build()
        if _DND: self._register_dnd()

    def _build(self):
        self._zone = tk.Frame(self, bg=DROP_BG_IDLE,
                              highlightthickness=1, highlightbackground=DROP_B_IDLE)
        self._zone.pack(fill="x")
        inner = mkframe(self._zone, bg=DROP_BG_IDLE)
        inner.pack(fill="x", padx=6, pady=4)
        left = mkframe(inner, bg=DROP_BG_IDLE)
        left.pack(side="left", fill="x", expand=True)
        self._icon_lbl = tk.Label(left, text="v", bg=DROP_BG_IDLE, fg=MUTED2, font=("Tahoma",13))
        self._icon_lbl.pack(side="left", padx=(2,6))
        col = mkframe(left, bg=DROP_BG_IDLE)
        col.pack(side="left", fill="x", expand=True)
        primary = ("Drop file(s) here" if (_DND and self._multi) else
                   "Drop file here"    if _DND else "Select a file")
        self._main_lbl = tk.Label(col, text=primary, bg=DROP_BG_IDLE,
                                  fg=TEXT, font=FONT_BOLD, anchor="w")
        self._main_lbl.pack(anchor="w")
        sub = "or click Browse →" if _DND else "Use the Browse button →"
        self._sub_lbl = tk.Label(col, text=sub, bg=DROP_BG_IDLE,
                                 fg=MUTED, font=FONT_SM, anchor="w")
        self._sub_lbl.pack(anchor="w")
        tk.Button(inner, text="Browse…", bg=SURFACE3, fg=TEXT, font=FONT_SM,
                  relief="flat", bd=0, cursor="hand2", padx=8, pady=4,
                  highlightthickness=1, highlightbackground=BORDER_HI,
                  activebackground=ACCENT_A, activeforeground=WHITE,
                  command=self._browse).pack(side="right", padx=(6,2))
        self._chip_frame = tk.Frame(self, bg=BG, height=72)

    def _browse(self):
        filters = {
            "vault": [("Vault files","*.vault"),("All files","*.*")],
            "vz":    [("VZ / ZIP / 7z archives","*.vz *.zip *.7z"),("All files","*.*")],
        }
        ft = filters.get(self._mode, [("All files","*.*")])
        if self._multi:
            result = filedialog.askopenfilenames(filetypes=ft)
            if result:
                new = [p for p in result if p not in self._paths]
                self._cb(self._paths + new)
        else:
            path = filedialog.askopenfilename(filetypes=ft)
            if path: self._cb(path)

    def _register_dnd(self):
        targets = [self, self._zone]
        for child in self._zone.winfo_children():
            targets.append(child)
            for sub in child.winfo_children(): targets.append(sub)
        for w in targets:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<DropEnter>>", self._on_enter)
                w.dnd_bind("<<DropLeave>>", self._on_leave)
                w.dnd_bind("<<Drop>>",      self._on_drop)
            except Exception: pass

    def _on_enter(self, event=None):
        self._zone.config(highlightbackground=DROP_B_HOV, bg=DROP_BG_HOV)
        for w in (self._icon_lbl, self._main_lbl, self._sub_lbl):
            w.config(bg=DROP_BG_HOV)
        self._icon_lbl.config(fg=ACCENT_B)
        return event.action if event else None

    def _on_leave(self, event=None):
        self._zone.config(highlightbackground=DROP_B_IDLE, bg=DROP_BG_IDLE)
        for w in (self._icon_lbl, self._main_lbl, self._sub_lbl):
            w.config(bg=DROP_BG_IDLE)
        self._icon_lbl.config(fg=MUTED2)

    def _on_drop(self, event):
        self._on_leave()
        if self._multi:
            paths = _parse_paths(event.data)
            if paths:
                new = [p for p in paths if p not in self._paths]
                self._cb(self._paths + new)
            else:
                messagebox.showerror("Drop Error", "No valid files found.")
        else:
            path = _clean_path(event.data)
            if os.path.isfile(path): self._cb(path)
            else: messagebox.showerror("Drop Error", f"Not a valid file:\n{path}")

    def set_file(self, name: str):
        display = name if len(name) <= 42 else name[:19] + "…" + name[-19:]
        self._main_lbl.config(text=display, fg=ACCENT_C)
        self._sub_lbl.config(text="")
        self._icon_lbl.config(fg=ACCENT_B)
        self._hide_chips()

    def set_files(self, paths: list[str]):
        self._paths = paths
        if not paths: return
        if len(paths) == 1:
            name = os.path.basename(paths[0])
            display = name if len(name) <= 38 else name[:17] + "…" + name[-17:]
            self._main_lbl.config(text=display, fg=ACCENT_C)
            self._sub_lbl.config(text="")
            self._icon_lbl.config(fg=ACCENT_B)
            if self._multi: self._show_chips(paths)
            else:           self._hide_chips()
        else:
            self._main_lbl.config(text=f"{len(paths)} files selected", fg=ACCENT_C)
            self._sub_lbl.config(text="")
            self._icon_lbl.config(fg=ACCENT_B)
            self._show_chips(paths)

    def _clear(self):
        self._paths = []
        primary = ("Drop file(s) here" if (_DND and self._multi) else
                   "Drop file here"    if _DND else "Select a file")
        self._main_lbl.config(text=primary, fg=TEXT)
        sub = "or click Browse →" if _DND else "Use the Browse button →"
        self._sub_lbl.config(text=sub, fg=MUTED)
        self._icon_lbl.config(fg=MUTED2)
        self._hide_chips()
        if self._clear_cb: self._clear_cb()

    def _hide_chips(self):
        self._chip_frame.pack_forget()
        for w in self._chip_frame.winfo_children(): w.destroy()

    def _show_chips(self, paths: list[str]):
        for w in self._chip_frame.winfo_children(): w.destroy()
        hdr = mkframe(self._chip_frame)
        hdr.pack(fill="x", pady=(3,2))
        tk.Label(hdr, text=f"  {len(paths)} files:", bg=BG,
                 fg=MUTED, font=FONT_SM).pack(side="left")
        tk.Button(hdr, text="✕ Clear", bg=BG, fg=DANGER, font=FONT_SM,
                  relief="flat", bd=0, cursor="hand2", padx=6,
                  activebackground=BG, activeforeground=DANGER,
                  command=self._clear).pack(side="right")
        MAX_VIS = 6
        box = tk.Frame(self._chip_frame, bg=INSET, height=46,
                       highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="x"); box.pack_propagate(False)
        inner = tk.Frame(box, bg=INSET)
        inner.place(x=4, y=3)
        shown = paths[:MAX_VIS]
        for i, p in enumerate(shown):
            name  = os.path.basename(p)
            short = name if len(name) <= 20 else name[:9] + "…" + name[-8:]
            col_i, row_i = i % 2, i // 2
            tk.Label(inner, text=f"  {short}  ", bg=SURFACE2, fg=TEXT,
                     font=FONT_SM, relief="flat",
                     highlightthickness=1, highlightbackground=BORDER_HI
                     ).grid(row=row_i, column=col_i,
                            padx=(0,5) if col_i==0 else (4,0), pady=(0,2), sticky="w")
        remaining = len(paths) - MAX_VIS
        if remaining > 0:
            ri, ci = len(shown)//2, len(shown)%2
            tk.Label(inner, text=f"  +{remaining} more…", bg=INSET,
                     fg=MUTED, font=FONT_SM).grid(row=ri, column=ci, sticky="w")
        self._chip_frame.pack(fill="x")

def _make_pw_row(parent, pw_var, label="Password:"):
    mklabel(parent, text=label, color=MUTED, font=FONT_SM).pack(anchor="w", pady=(0,2))
    row = mkframe(parent); row.pack(fill="x")
    entry = NavyEntry(row, pw_var, show="*", width=24)
    entry.pack(side="left", ipady=3)
    show_btn = tk.Button(row, text="Show", bg=BG, fg=MUTED2, font=FONT_SM,
                         relief="flat", bd=0, cursor="hand2", padx=6)
    show_btn.pack(side="left", padx=(6,0))
    _show = [False]
    def toggle():
        _show[0] = not _show[0]
        entry.config(show="" if _show[0] else "*")
        show_btn.config(text="Hide" if _show[0] else "Show")
    show_btn.config(command=toggle)
    return entry

# Algorithm

class _AlgoSelector(tk.Frame):
    def __init__(self, parent, variable, algorithms, colors, hints,
                 label="Algorithm:", btn_w=100, available=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._var    = variable
        self._algos  = algorithms
        self._colors = colors
        self._hints  = hints
        self._avail  = available or algorithms
        self._bw     = btn_w
        self._btns   = {}
        mklabel(self, text=label, color=MUTED, font=FONT_SM).pack(anchor="w", pady=(0,3))
        row = mkframe(self); row.pack(anchor="w")
        for algo in algorithms:
            cv = tk.Canvas(row, width=btn_w, height=21, bd=0,
                           highlightthickness=0, bg=BG,
                           cursor="hand2" if algo in self._avail else "arrow")
            cv.pack(side="left", padx=(0,4))
            cv._hovering = False
            if algo in self._avail:
                cv.bind("<ButtonRelease-1>", lambda e, a=algo: self._var.set(a))
                cv.bind("<Enter>",  lambda e, a=algo: self._hover(a, True))
                cv.bind("<Leave>",  lambda e, a=algo: self._hover(a, False))
            self._btns[algo] = cv
        self._hint = mklabel(self, text="", color=MUTED, font=FONT_SM)
        self._hint.pack(anchor="w", pady=(2,0))
        self._var.trace_add("write", lambda *_: self._redraw_all())
        self._redraw_all()

    def _hover(self, algo, state):
        self._btns[algo]._hovering = state; self._redraw(algo)

    def _redraw_all(self):
        for a in self._algos: self._redraw(a)
        self._hint.config(text=self._hints.get(self._var.get(), ""))

    def _redraw(self, algo):
        cv = self._btns[algo]; cv.delete("all")
        sel   = self._var.get() == algo
        hov   = getattr(cv, "_hovering", False)
        avail = algo in self._avail
        w, h  = self._bw, 21
        c1, c2 = self._colors.get(algo, (ACCENT_A, ACCENT_B))
        if not avail:
            cv.create_rectangle(0,0,w-1,h-1, fill=INSET, outline=BORDER_LO)
            cv.create_text(w//2,h//2, text=algo, fill=MUTED2, font=FONT_SM, anchor="center")
            return
        if sel:
            draw_hg(cv,0,0,w,h, lerp_color(c1,"#000000",0.4), lerp_color(c2,"#000000",0.3))
            cv.create_rectangle(0,0,w-1,h-1, fill="", outline=c2)
        elif hov:
            draw_hg(cv,0,0,w,h, lerp_color(SURFACE2,"#000000",0.1), SURFACE3)
            cv.create_rectangle(0,0,w-1,h-1, fill="", outline=lerp_color(BORDER_HI,c2,0.4))
        else:
            cv.create_rectangle(0,0,w-1,h-1, fill=SURFACE2, outline=BORDER)
        if hasattr(self, "_show_dot") and self._show_dot:
            cv.create_oval(5,6,13,14, fill=c2 if sel else MUTED2, outline="")
            if sel: cv.create_oval(8,9,10,11, fill=WHITE, outline="")
            cv.create_text(18,h//2, text=algo,
                           fill=WHITE if sel else MUTED,
                           font=FONT_BOLD if sel else FONT_SM, anchor="w")
        else:
            cv.create_text(w//2,h//2, text=algo,
                           fill=WHITE if sel else MUTED,
                           font=FONT_BOLD if sel else FONT_SM, anchor="center")


class AlgoSelector(_AlgoSelector):
    _ENC = ["AES-256-GCM", "Blowfish-CBC"]
    _COL = {"AES-256-GCM": (ACCENT_A, ACCENT_B), "Blowfish-CBC": ("#6a30b0","#b060ff")}
    _HNT = {"AES-256-GCM": "128-bit blocks, 256-bit key",
             "Blowfish-CBC": "64-bit blocks, 128-bit key"}
    def __init__(self, parent, variable, **kw):
        super().__init__(parent, variable, self._ENC, self._COL, self._HNT,
                         label="Algorithm:", btn_w=138, **kw)
        self._show_dot = True


class CompAlgoSelector(_AlgoSelector):
    _COL = {"zip": (ACCENT_A, ACCENT_B), "7z": ("#1a6030","#30c060")}
    _HNT = {"zip": "Standard ZIP archive, widely compatible",
             "7z":  "High compression ratio via LZMA/XZ"}
    def __init__(self, parent, variable, **kw):
        super().__init__(parent, variable, COMP_ALGORITHMS, self._COL, self._HNT,
                         label="Compression:", btn_w=80,
                         available=available_algorithms(), **kw)
        self._show_dot = False

class BasePanel(tk.Frame):

    def __init__(self, parent, drop_mode="any", multi=False):
        tk.Frame.__init__(self, parent, bg=BG_BOT)
        self.full_path  = None
        self.full_paths: list[str] = []
        self._last_output: str | None = None

        self._bottom_bar = tk.Frame(self, bg=BG)
        self._bottom_bar.pack(side="bottom", fill="x")
        self._bb_inner = tk.Frame(self._bottom_bar, bg=BG)
        self._bb_inner.pack(fill="x", padx=16, pady=(6, 10))

        self._vsb = tk.Scrollbar(self, orient="vertical",
                                 bg=SURFACE2, troughcolor=INSET,
                                 width=8, relief="flat", bd=0)
        self._canvas = tk.Canvas(self, bd=0, highlightthickness=0, bg=BG)
        self._canvas.configure(yscrollcommand=self._vsb.set)
        self._vsb.configure(command=self._canvas.yview)
        self._vsb.pack(side="right", fill="y"); self._vsb.pack_forget()
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner  = tk.Frame(self._canvas, bg=BG, padx=16, pady=10)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",  self._on_inner_change)
        self._canvas.bind("<Configure>", self._on_canvas_change)
        self._canvas.bind("<Enter>", lambda e: self._canvas.focus_set())
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        self._dropzone = DropZone(self._inner, on_file_cb=self._set_path,
                                  mode=drop_mode, multi=multi,
                                  on_clear_cb=self._on_clear)
        self._dropzone.pack(fill="x")

# Scroll

    def _on_inner_change(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._update_scrollbar()

    def _on_canvas_change(self, event=None):
        w = event.width if event else self._canvas.winfo_width()
        self._canvas.itemconfig(self._win_id, width=w)
        self._update_scrollbar()

    def _update_scrollbar(self):
        self.update_idletasks()
        if self._inner.winfo_reqheight() > self._canvas.winfo_height():
            self._vsb.pack(side="right", fill="y", before=self._canvas)
        else:
            self._vsb.pack_forget()

    def _on_mousewheel(self, event):
        x, y = event.x_root, event.y_root
        px, py = self.winfo_rootx(), self.winfo_rooty()
        if px <= x <= px+self.winfo_width() and py <= y <= py+self.winfo_height():
            self._canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _build_action_row(self, label, command):
        row = tk.Frame(self._bb_inner, bg=BG)
        row.pack(fill="x", pady=(6, 0))
        GradientButton(row, label, command, width=112, height=23).pack(side="left")
        self._result_lbl = mklabel(row, text="", color=SUCCESS, font=FONT_SM, bg=BG)
        self._result_lbl.pack(side="left", padx=(10, 0))

        self._folder_btn = tk.Label(row, text="📂 Open folder", bg=BG, fg=ACCENT_B,
                                    font=FONT_SM, cursor="hand2")
        self._folder_btn.bind("<ButtonRelease-1>", self._open_output_folder)

    def _open_output_folder(self, _=None):
        if self._last_output:
            open_folder(self._last_output)

    def _set_path(self, path_or_paths):
        paths = (list(path_or_paths) if isinstance(path_or_paths, (list, tuple))
                 else [path_or_paths] if path_or_paths else [])
        paths = [p for p in paths if os.path.isfile(p)]
        if not paths: return
        self.full_paths = paths
        self.full_path  = paths[0]
        self._dropzone.set_files(paths)
        self._on_path_set(paths)
        self._reset()

    def _on_path_set(self, paths: list[str]): pass

    def _on_clear(self):
        self.full_path  = None
        self.full_paths = []
        self._dropzone._paths = []
        self._reset()

    def _reset(self):
        self._result_lbl.config(text="")
        self._folder_btn.pack_forget()
        self._last_output = None

    # Progress bar
    def _show_progress(self, title="Working…"):
        self._pdlg = ProgressDialog(self.winfo_toplevel(), title)

    def _progress_cb(self, val: float, msg: str = ""):
        if hasattr(self, "_pdlg") and self._pdlg.winfo_exists():
            self._pdlg.after(0, lambda: self._pdlg.update_progress(val, msg))

    def _close_progress(self):
        if hasattr(self, "_pdlg"):
            try: self._pdlg.close()
            except Exception: pass

# UI

    def _ui(self, fn, *args, **kwargs):
        self.after(0, lambda: fn(*args, **kwargs))

    def _finish_success(self, output_path: str, label: str):

        self._last_output = output_path
        def _do():
            self._result_lbl.config(text=label, fg=SUCCESS)
            self._folder_btn.pack(side="left", padx=(8, 0))
        self._ui(_do)

    def _finish_error(self, msg: str):
        def _do():
            self._result_lbl.config(text=msg, fg=DANGER)
            self._folder_btn.pack_forget()
        self._ui(_do)

# Encrypt / Decrypt

class VaultPanel(BasePanel):
    def __init__(self, parent, mode, app):
        is_enc = (mode == "enc")
        super().__init__(parent, drop_mode="vault" if not is_enc else "any", multi=is_enc)
        self.mode = mode
        self.pw_var   = tk.StringVar()
        self.algo_var = tk.StringVar(value="AES-256-GCM")

        AlgoSelector(self._inner, self.algo_var).pack(fill="x")
        _make_pw_row(self._inner, self.pw_var)
        self._build_action_row(
            "Encrypt File(s)" if is_enc else "Decrypt File",
            self._on_action)

    def _on_action(self):
        if not self.full_path:
            messagebox.showwarning("No File", "Please select a file first."); return
        if not self.pw_var.get():
            messagebox.showwarning("No Password", "Please enter a password."); return
        self._reset()
        self._show_progress("Encrypting…" if self.mode == "enc" else "Decrypting…")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            algo    = self.algo_var.get()
            paths   = self.full_paths
            out_dir = os.path.dirname(paths[0]) or "."

            if self.mode == "enc":
                ts  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                out = safe_output_path(os.path.join(out_dir, f"{ts}.vault"))
                if len(paths) > 1:
                    arc_name = f"archive_{ts}.zip"
                    tmp_arc  = os.path.join(tempfile.gettempdir(), arc_name)
                    try:
                        self._progress_cb(0.05, "Creating archive…")
                        with zipfile.ZipFile(tmp_arc, "w", zipfile.ZIP_DEFLATED,
                                             compresslevel=9) as zf:
                            for i, p in enumerate(paths):
                                self._progress_cb(0.05 + 0.50 * i / len(paths),
                                                  f"Adding {os.path.basename(p)}…")
                                zf.write(p, os.path.basename(p))
                        self._progress_cb(0.55, "Encrypting…")
                        encrypt_file(tmp_arc, out, self.pw_var.get(),
                                     progress=lambda v, m: self._progress_cb(0.55 + v*0.45, m),
                                     algorithm=algo)
                    finally:
                        try:
                            if os.path.exists(tmp_arc): os.unlink(tmp_arc)
                        except OSError: pass
                    tag  = f"[{algo}] " if algo != "AES-256-GCM" else ""
                    label = f"{tag}→ {os.path.basename(out)}  ({len(paths)} files)"
                    append_history({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "original_name": arc_name, "vault_name": os.path.basename(out),
                                    "vault_path": out, "vault_size": os.path.getsize(out),
                                    "algorithm": algo})
                else:
                    src_size = os.path.getsize(paths[0])
                    encrypt_file(paths[0], out, self.pw_var.get(),
                                 progress=self._progress_cb, algorithm=algo)
                    dst_size = os.path.getsize(out)
                    tag  = f"[{algo}] " if algo != "AES-256-GCM" else ""
                    label = f"{tag}→ {os.path.basename(out)}  ({_size_delta(src_size, dst_size)})"
                    append_history({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "original_name": os.path.basename(paths[0]),
                                    "original_size": src_size, "vault_name": os.path.basename(out),
                                    "vault_path": out, "vault_size": dst_size, "algorithm": algo})
                self._ui(self._close_progress)
                self._finish_success(out, label)
            else:
                src_size = os.path.getsize(paths[0])
                out = decrypt_file(paths[0], out_dir, self.pw_var.get(),
                                   progress=self._progress_cb, algorithm=algo)
                dst_size = os.path.getsize(out)
                label = f"→ {os.path.basename(out)}  ({_size_delta(src_size, dst_size)})"
                self._ui(self._close_progress)
                self._finish_success(out, label)
        except Exception as exc:
            self._ui(self._close_progress)
            self._finish_error(str(exc))

class CompressPanel(BasePanel):
    def __init__(self, parent, app):
        super().__init__(parent, multi=True)
        self.pw_var   = tk.StringVar()
        self.algo_var = tk.StringVar(value=available_algorithms()[0])

        CompAlgoSelector(self._inner, self.algo_var).pack(fill="x")

        self._pw_frame = mkframe(self._inner); self._pw_frame.pack(fill="x")
        _make_pw_row(self._pw_frame, self.pw_var, "ZIP Password (optional):")
        self.algo_var.trace_add("write", self._on_algo_change)

        self._build_action_row("Compress File(s)", self._on_action)
        self._on_algo_change()

    def _on_algo_change(self, *_):

        if self.algo_var.get() == "zip":
            self._pw_frame.pack(fill="x")
        else:
            self._pw_frame.pack_forget()
            self.pw_var.set("")

    def _on_action(self):
        if not self.full_path:
            messagebox.showwarning("No File", "Please select a file first."); return
        self._reset()
        self._show_progress("Compressing…")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            paths   = self.full_paths
            out_dir = os.path.dirname(paths[0]) or "."
            algo    = self.algo_var.get()
            pw      = self.pw_var.get()
            ext     = ".zip" if algo == "zip" else ".7z"

            # Measure total input size for delta
            src_size = sum(os.path.getsize(p) for p in paths)

            if len(paths) > 1:
                ts  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                out = safe_output_path(os.path.join(out_dir, f"archive_{ts}{ext}"))
                if algo == "zip":
                    if pw:
                        try:
                            import pyzipper
                            self._progress_cb(0.10, "Creating encrypted ZIP…")
                            with pyzipper.AESZipFile(out, "w",
                                                     compression=pyzipper.ZIP_DEFLATED,
                                                     encryption=pyzipper.WZ_AES) as zf:
                                zf.setpassword(pw.encode("utf-8"))
                                for i, p in enumerate(paths):
                                    self._progress_cb(0.10 + 0.85 * i / len(paths),
                                                      f"Adding {os.path.basename(p)}…")
                                    zf.write(p, os.path.basename(p))
                        except ImportError:
                            raise RuntimeError(
                                "AES-encrypted ZIP requires pyzipper.\n"
                                "Run:  pip install pyzipper")
                    else:
                        self._progress_cb(0.10, "Creating ZIP archive…")
                        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED,
                                             compresslevel=9) as zf:
                            for i, p in enumerate(paths):
                                self._progress_cb(0.10 + 0.85 * i / len(paths),
                                                  f"Adding {os.path.basename(p)}…")
                                zf.write(p, os.path.basename(p))
                    self._progress_cb(1.00, "Done.")
                else:
                    tmp_zip = ""
                    try:
                        fd, tmp_zip = tempfile.mkstemp(suffix=".zip")
                        os.close(fd)
                        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_STORED) as zf:
                            for p in paths: zf.write(p, os.path.basename(p))
                        compress_file(tmp_zip, out, algorithm=algo,
                                      progress=self._progress_cb)
                    finally:
                        try:
                            if tmp_zip and os.path.exists(tmp_zip): os.unlink(tmp_zip)
                        except OSError: pass

                dst_size = os.path.getsize(out)
                label = f"→ {os.path.basename(out)}  ({len(paths)} files, {_size_delta(src_size, dst_size)})"
            else:
                stem = os.path.splitext(os.path.basename(paths[0]))[0]
                out  = safe_output_path(os.path.join(out_dir, f"{stem}{ext}"))
                compress_file(paths[0], out, algorithm=algo,
                              password=pw, progress=self._progress_cb)
                dst_size = os.path.getsize(out)
                label = f"→ {os.path.basename(out)}  ({_size_delta(src_size, dst_size)})"

            self._ui(self._close_progress)
            self._finish_success(out, label)
        except Exception as exc:
            self._ui(self._close_progress)
            self._finish_error(str(exc))


# Decompress
class DecompressPanel(BasePanel):
    def __init__(self, parent, app):
        super().__init__(parent, drop_mode="vz")
        self.pw_var         = tk.StringVar()
        self.to_folder_var  = tk.BooleanVar(value=False)

        self._meta_lbl = mklabel(self._inner, text="", color=MUTED, font=FONT_SM)
        self._meta_lbl.pack(anchor="w")
        _make_pw_row(self._inner, self.pw_var, "Password (if encrypted):")

        # "Decompress to folder" tick
        row = mkframe(self._inner); row.pack(anchor="w", pady=(6, 0))
        tk.Checkbutton(row, variable=self.to_folder_var,
                       bg=BG, fg=TEXT, selectcolor=INSET, activebackground=BG,
                       activeforeground=ACCENT_C, font=FONT,
                       highlightthickness=0, bd=0,
                       text="Decompress into folder").pack(side="left")
        mklabel(row, text="  (creates <name>/ next to archive)",
                color=MUTED, font=FONT_SM).pack(side="left")

        self._build_action_row("Decompress File", self._on_action)

    def _on_path_set(self, paths: list[str]):
        try:
            meta  = read_metadata(paths[0])
            parts = []
            if "original_name" in meta: parts.append(meta["original_name"])
            if "original_size" in meta: parts.append(_fmt_size(meta["original_size"]))
            if "algorithm"     in meta: parts.append(meta["algorithm"])
            if meta.get("encrypted"):   parts.append("encrypted")
            if meta.get("note"):        parts.append(f'note: {meta["note"]}')
            self._meta_lbl.config(text="  " + "  ·  ".join(parts) if parts else "")
        except Exception:
            self._meta_lbl.config(text="")

    def _on_action(self):
        if not self.full_path:
            messagebox.showwarning("No File", "Please select a file first."); return
        self._reset()
        self._show_progress("Decompressing…")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            src_size   = os.path.getsize(self.full_path)
            archive_dir = os.path.dirname(self.full_path) or "."

            if self.to_folder_var.get():

                stem = os.path.splitext(os.path.basename(self.full_path))[0]
                out_dir = safe_output_path(os.path.join(archive_dir, stem))
                os.makedirs(out_dir, exist_ok=True)
            else:
                out_dir = archive_dir

            out, _ = decompress_file(self.full_path, out_dir,
                                     password=self.pw_var.get(),
                                     progress=self._progress_cb)
            dst_size = os.path.getsize(out)
            label = f"→ {os.path.relpath(out, archive_dir)}  ({_size_delta(src_size, dst_size)})"
            self._ui(self._close_progress)
            self._finish_success(out, label)
        except Exception as exc:
            self._ui(self._close_progress)
            self._finish_error(str(exc))


# About
class WizardPanel(tk.Frame):
    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent, bg=BG)
        body = tk.Frame(self, bg=BG, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        mklabel(body, text="WinVFE (Vault)", font=FONT_TITLE, color=ACCENT_C).pack(anchor="w")
        mklabel(body,
                text="A local file encryption and compression utility.\n"
                     "All processing happens on your machine, nothing leaves your disk.",
                color=TEXT, font=FONT_SM).pack(anchor="w", pady=(4, 10))

        thin_divider(body, pady=6)

        rows = [
            ("Encryption",      "AES-256-GCM; Blowfish-CBC"),
            ("Compression",     "ZIP (AES password), 7z / LZMA"),
            ("Built with",      "Python 3.11; Tkinter"),
            ("Version",         f"{APP_VERSION}  (06.04.2026)"),
            ("GitHub",          "github.com/anonimwindows228/Vault-file-encryption"),
            ("Website",          "https://github.com/ltrsoc"),
            ("Donate",          "donationalerts.com/r/ltrsociety"),
            ("Contact",         "maximstepnov@proton.me"),
        ]
        for label, value in rows:
            row = mkframe(body); row.pack(anchor="w", fill="x", pady=2)
            mklabel(row, text=f"{label}:", color=MUTED, font=FONT_SM, width=13).pack(side="left")
            mklabel(row, text=value,       color=TEXT,  font=FONT_SM).pack(side="left")


# App shell
_AppBase = TkinterDnD.Tk if _DND else tk.Tk

TABS  = ["Encrypt", "Decrypt", "Compress", "Decompress", "Wizard"]
ICONS = ["ico1.png", "ico2.png", "ico5.png", "ico6.png", "ico3.png"]


class VaultApp(_AppBase):
    def __init__(self, startup_tab: int | None = None,
                 startup_file: str | None = None):
        super().__init__()
        self.title(f"WinVFE {APP_VERSION}")
        self.geometry("520x420")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.ico_imgs = []
        for f in ICONS:
            img = Image.open(resource_path(f)).resize((20,20), Image.LANCZOS)
            self.ico_imgs.append(ImageTk.PhotoImage(img))
        logo_raw = Image.open(resource_path("ico1.png")).resize((26,26), Image.LANCZOS)
        self.logo_img = ImageTk.PhotoImage(logo_raw)

        self._active = 0
        self._build()

        if startup_tab is not None:
            self._switch(startup_tab)
        if startup_file and os.path.isfile(startup_file):
            target_tab = startup_tab if startup_tab is not None else 0
            panel = self._panels[target_tab]
            self.after(100, lambda: panel._set_path(startup_file))

        self.after(800, self._start_update_check)

    def _start_update_check(self):
        _check_for_update(self._on_update_found)

    def _on_update_found(self, latest_tag: str):

        self.after(0, lambda: self._show_update_popup(latest_tag))

    def _show_update_popup(self, latest_tag: str):
        dlg = tk.Toplevel(self)
        dlg.title("Update available")
        dlg.resizable(False, False)
        dlg.configure(bg=BG)
        dlg.grab_set()
        # Center
        self.update_idletasks()
        w, h = 340, 130
        dlg.geometry(f"{w}x{h}+{self.winfo_rootx()+(self.winfo_width()-w)//2}"
                     f"+{self.winfo_rooty()+(self.winfo_height()-h)//2}")

        body = tk.Frame(dlg, bg=BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        mklabel(body, text="A new version is available!", color=ACCENT_C,
                font=FONT_BOLD).pack(anchor="w")
        mklabel(body, text=f"  Current:  {APP_VERSION}",  color=MUTED,  font=FONT_SM).pack(anchor="w", pady=(6,0))
        mklabel(body, text=f"  Latest:    {latest_tag}",  color=SUCCESS, font=FONT_SM).pack(anchor="w")

        btn_row = mkframe(body); btn_row.pack(fill="x", pady=(12,0))
        def _open():
            import webbrowser
            webbrowser.open(_GH_RELEASES)
            dlg.destroy()
        GradientButton(btn_row, "Download", _open, width=90, height=22).pack(side="left")
        tk.Button(btn_row, text="Dismiss", bg=SURFACE2, fg=MUTED, font=FONT_SM,
                  relief="flat", bd=0, cursor="hand2", padx=10,
                  activebackground=SURFACE3, activeforeground=TEXT,
                  command=dlg.destroy).pack(side="left", padx=(8,0))

    def _build(self):
        self._hdr = tk.Canvas(self, height=52, bd=0, highlightthickness=0, bg=HDR_C)
        self._hdr.pack(fill="x")
        self._hdr.bind("<Configure>", self._draw_header)
        tk.Frame(self, bg=BORDER_HI, height=1).pack(fill="x")

        container = mkframe(self)
        container.pack(fill="both", expand=True)

        self._panels = [
            VaultPanel(container, "enc", self),
            VaultPanel(container, "dec", self),
            CompressPanel(container, self),
            DecompressPanel(container, self),
            WizardPanel(container, self),
        ]

        self._switch(0)

    def _draw_header(self, event=None):
        cv = self._hdr; cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 2: return
        draw_v3(cv, 0, 0, w, h, HDR_A, HDR_B, HDR_C)
        cv.create_image(20, h//2, image=self.logo_img)
        cv.create_text(40, h//2 - 6, text="WinVFE", fill=WHITE, font=FONT_TITLE, anchor="w")
        cv.create_text(40, h//2 + 7, text=f"File utility {APP_VERSION}",
                       fill=MUTED, font=FONT_SM, anchor="w")

        btn_w    = 62
        bx_start = w - 8 - len(TABS) * (btn_w + 3)
        for i, lbl in enumerate(TABS):
            active = (self._active == i)
            bx  = bx_start + i * (btn_w + 3)
            by0, by1 = 4, h - 4
            bg_c = lerp_color(HDR_B, ACCENT_A, 0.30) if active \
                   else lerp_color(HDR_B, HDR_C, 0.50)
            bo_c = lerp_color(BORDER_HI, ACCENT_B, 0.55) if active \
                   else lerp_color(BORDER_HI, HDR_B, 0.30)
            cv.create_rectangle(bx, by0, bx+btn_w, by1, fill=bg_c, outline=bo_c)
            cv.create_image(bx+btn_w//2, by0+11, image=self.ico_imgs[i])
            cv.create_text(bx+btn_w//2, by1-7, text=lbl,
                           fill=WHITE if active else MUTED,
                           font=FONT_SM, anchor="center")
            tag = f"_tab{i}"
            cv.create_rectangle(bx, by0, bx+btn_w, by1, fill="", outline="", tags=tag)
            cv.tag_bind(tag, "<ButtonRelease-1>", lambda e, ix=i: self._switch(ix))

    def _switch(self, idx):
        self._active = idx
        for i, p in enumerate(self._panels):
            if i == idx: p.pack(fill="both", expand=True)
            else:        p.pack_forget()
        self._draw_header()
