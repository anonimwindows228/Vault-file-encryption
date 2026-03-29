import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
import random
from crypto import encrypt_file, decrypt_file

# Colours
BG = "#10182a"
SURFACE2 = "#1a2744"
SURFACE3 = "#203050"
INSET = "#0d1525"
BORDER_LO = "#080e1a"
BORDER_HI = "#3a5080"
BORDER = "#1e2e4a"
ACCENT_A = "#2060d0"
ACCENT_B = "#4a9aff"
ACCENT_C = "#6ab8ff"
ACCENT_DIM = "#152a5a"
TEXT = "#c8d8f0"
MUTED = "#4e6a90"
MUTED2 = "#2a3e5e"
SUCCESS = "#30c080"
DANGER = "#e04455"
WARN = "#e0952a"
WHITE = "#e8f0ff"

HDR_A = "#1e3060"
HDR_B = "#162448"
HDR_C = "#10182a"

FONT = ("Tahoma", 9)
FONT_SM = ("Tahoma", 8)
FONT_BOLD = ("Tahoma", 9, "bold")
FONT_TITLE = ("Tahoma", 13, "bold")


# Helper functions for UI drawing
def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))


def lerp3(c1, c2, c3, t):
    if t <= 0.5: return lerp_color(c1, c2, t * 2)
    return lerp_color(c2, c3, (t - 0.5) * 2)


def draw_v3(cv, x0, y0, x1, y1, c1, c2, c3):
    h = y1 - y0
    for i in range(h):
        cv.create_line(x0, y0 + i, x1, y0 + i, fill=lerp3(c1, c2, c3, i / h))


def draw_hg(cv, x0, y0, x1, y1, c1, c2):
    w = x1 - x0
    for i in range(w):
        cv.create_line(x0 + i, y0, x0 + i, y1, fill=lerp_color(c1, c2, i / w))


def mkframe(parent, bg=BG, **kw):
    return tk.Frame(parent, bg=bg, **kw)


def mklabel(parent, text="", var=None, color=TEXT, font=FONT, anchor="w", bg=BG, **kw):
    cfg = dict(bg=bg, fg=color, font=font, anchor=anchor)
    if var is not None: return tk.Label(parent, textvariable=var, **cfg, **kw)
    return tk.Label(parent, text=text, **cfg, **kw)


def thin_divider(parent, pady=7):
    tk.Frame(parent, bg=BORDER_LO, height=1).pack(fill="x", pady=(pady, 0))
    tk.Frame(parent, bg=BORDER_HI, height=1).pack(fill="x", pady=(0, pady))


# Widgets
class NavyEntry(tk.Entry):
    def __init__(self, parent, var, show="", **kw):
        super().__init__(parent, textvariable=var, show=show, bg=INSET, fg=TEXT,
                         insertbackground=ACCENT_C, selectbackground=ACCENT_DIM,
                         selectforeground=ACCENT_C, relief="flat", font=FONT,
                         highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=ACCENT_B, bd=0, **kw)
        self.bind("<FocusIn>", lambda e: self.config(highlightbackground=ACCENT_B))
        self.bind("<FocusOut>", lambda e: self.config(highlightbackground=BORDER))


class GradientButton(tk.Frame):
    def __init__(self, parent, text, command, width=120, height=24, c1=ACCENT_A, c2=ACCENT_B):
        tk.Frame.__init__(self, parent, width=width, height=height, bd=0, highlightthickness=0, bg=BG)
        self.pack_propagate(False)
        self._text, self._command, self._c1, self._c2, self._bw, self._bh = text, command, c1, c2, width, height
        self._hover = self._pressed = False
        self._cv = tk.Canvas(self, width=width, height=height, bd=0, highlightthickness=0, cursor="hand2", bg=BG)
        self._cv.pack(fill="both", expand=True)
        self._cv.bind("<Enter>", lambda e: self._state(hover=True))
        self._cv.bind("<Leave>", lambda e: self._state(hover=False, pressed=False))
        self._cv.bind("<ButtonPress-1>", lambda e: self._state(pressed=True))
        self._cv.bind("<ButtonRelease-1>", lambda e: (self._state(pressed=False), command()))
        self.after(20, self._draw)

    def _state(self, **kw):
        for k, v in kw.items(): setattr(self, f"_{k}", v)
        self._draw()

    def _draw(self):
        cv = self._cv
        cv.delete("all")
        w, h = self._bw, self._bh
        c1 = lerp_color(self._c1, WHITE, 0.08 if self._hover else 0)
        c2 = lerp_color(self._c2, WHITE, 0.12 if self._hover else 0)
        if self._pressed:
            c1, c2 = lerp_color(c1, "#000000", 0.18), lerp_color(c2, "#000000", 0.12)
        draw_hg(cv, 0, 0, w, h, c1, c2)
        off = 1 if self._pressed else 0
        cv.create_text(w // 2 + off, h // 2 + off, text=self._text, fill=WHITE, font=FONT_BOLD, anchor="center")


class SmoothProgressBar(tk.Canvas):
    def __init__(self, parent, variable, height=11, **kw):
        tk.Canvas.__init__(self, parent, height=height, bg=INSET, bd=0, highlightthickness=1,
                           highlightbackground=BORDER_LO, **kw)
        self._var, self._target, self._current = variable, 0.0, 0.0
        self._var.trace_add("write", self._on_var)
        self.bind("<Configure>", lambda e: self._draw())
        self._tick()

    def _on_var(self, *_):
        self._target = min(max(self._var.get(), 0), 1)

    def _tick(self):
        if abs(self._current - self._target) > 0.001:
            self._current += (self._target - self._current) * 0.15
        else:
            self._current = self._target
        self._draw()
        self.after(16, self._tick)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2: return
        fw = int(w * self._current)
        if fw > 1: draw_hg(self, 0, 0, fw, h, ACCENT_A, ACCENT_C)
        pct = int(self._current * 100)
        if pct > 0:
            tx = fw - 4 if fw > 30 else fw + 18
            self.create_text(tx, h // 2, text=f"{pct}%", fill=WHITE if self._current > 0.55 else MUTED,
                             font=("Tahoma", 7), anchor="e")


class CipherStream(tk.Canvas):
    CHARS, COLS, ROWS = "TG@:Zabroshka", 64, 2

    def __init__(self, parent, **kw):
        tk.Canvas.__init__(self, parent, bg=INSET, bd=0, highlightthickness=0, height=34, **kw)
        self._cells = [[random.choice(self.CHARS) for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self._bright = set(random.sample([(r, c) for r in range(self.ROWS) for c in range(self.COLS)], 16))
        self.after(60, self._draw)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10: return
        cw, ch = w / self.COLS, (h - 4) / self.ROWS
        for r in range(self.ROWS):
            for c in range(self.COLS):
                bright = (r, c) in self._bright
                col = lerp_color(MUTED2, ACCENT_B, 0.85) if bright else MUTED2
                self.create_text(c * cw + cw / 2, 4 + r * ch + ch / 2, text=self._cells[r][c], fill=col,
                                 font=("Courier New", 7 + bright, "bold" if bright else "normal"), anchor="center")


# Panel
class WizardPanel(tk.Frame):
    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent, bg=BG, padx=20, pady=20)
        self.app = app
        self.steps = [
            ("Welcome to Vault", "This wizard will explain how to protect your files.\nPress 'Next' to start.\n Not even the FBI can read your files."),
            ("Step 1: Encryption",
             "Encryption scrambles your file into a '.vault' file.\nOnly someone with your passphrase can open it."),
            ("Step 2: Selection", "Click 'Encrypt' at the top, select a file, and\nenter a strong password."),
            ("Step 3: Decryption",
             "To get your file back, go to 'Decrypt',\nselect the .vault file and enter the same password."),
            ("Ready!", "You are now ready to secure your data.\n If you would like to change file name, do it before encryption!!")
        ]
        self.cur_step = 0
        self._build()

    def _build(self):
        self.title_lbl = mklabel(self, text="", font=FONT_TITLE, color=ACCENT_C)
        self.title_lbl.pack(anchor="w", pady=(0, 10))
        self.desc_lbl = mklabel(self, text="", font=FONT, color=TEXT)
        self.desc_lbl.pack(anchor="w", pady=(0, 30))

        btn_row = mkframe(self)
        btn_row.pack(fill="x")
        self.next_btn = GradientButton(btn_row, "Next Step", self._next_step, width=100)
        self.next_btn.pack(side="left")
        self._update_ui()

    def _next_step(self):
        self.cur_step = (self.cur_step + 1) % len(self.steps)
        self._update_ui()
        if self.cur_step == 0:
            messagebox.showinfo("Vault Wizard", "Tutorial finished!")

    def _update_ui(self):
        title, desc = self.steps[self.cur_step]
        self.title_lbl.config(text=title)
        self.desc_lbl.config(text=desc)


# Info Panel
class InfoPanel(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent, bg=BG, padx=20, pady=20)
        mklabel(self, text="Vault encryption software", font=FONT_TITLE, color=ACCENT_C).pack(anchor="w", pady=(0, 10))
        mklabel(self,
                text="Version: 1.0.0\nAlgorithm: AES-256-GCM\nLanguage: Python 3.10\nLibrary: Tkinter / Cryptography\n Version released: 29.03.2026\n Developed by L.T.R.\n Support: https://www.donationalerts.com/r/ltrsociety\n If you would like to change file name, do it before encryption!!",
                color=MUTED).pack(anchor="w")


# Panel logic
class VaultPanel(tk.Frame):
    def __init__(self, parent, mode, app):
        tk.Frame.__init__(self, parent, bg=BG, padx=18, pady=10)
        self.mode, self.app, self.full_path = mode, app, None
        self.file_var, self.pw_var = tk.StringVar(value="No file selected"), tk.StringVar()
        self.status_var, self.progress_var = tk.StringVar(value=""), tk.DoubleVar(value=0.0)
        self._show_pw = False
        self._build()

    def _row_label(self, text):
        mklabel(self, text=text, color=MUTED, font=FONT_SM).pack(anchor="w", pady=(0, 3))

    def _build(self):
        is_enc = self.mode == "enc"
        self._row_label("Input file:" if is_enc else "Encrypted file:")
        file_row = mkframe(self)
        file_row.pack(fill="x")
        path_bg = tk.Frame(file_row, bg=INSET, highlightthickness=1, highlightbackground=BORDER)
        path_bg.pack(side="left", fill="x", expand=True, ipady=3)
        self._file_lbl = mklabel(path_bg, var=self.file_var, color=MUTED, font=FONT_SM, bg=INSET)
        self._file_lbl.pack(side="left", padx=(6, 4))
        tk.Button(file_row, text="Browse…", bg=SURFACE2, fg=TEXT, font=FONT_SM, relief="flat", bd=0, cursor="hand2",
                  padx=8, pady=3, highlightthickness=1, highlightbackground=BORDER, command=self._pick_file).pack(
            side="left", padx=(4, 0))
        thin_divider(self, pady=7)
        self._row_label("Passphrase:")
        pw_row = mkframe(self)
        pw_row.pack(fill="x")
        self.pw_entry = NavyEntry(pw_row, self.pw_var, show="*", width=26)
        self.pw_entry.pack(side="left", ipady=4)
        self._show_btn = tk.Button(pw_row, text="Show", bg=BG, fg=MUTED2, font=FONT_SM, relief="flat", bd=0,
                                   cursor="hand2", padx=6, command=self._toggle_pw)
        self._show_btn.pack(side="left", padx=(6, 0))
        thin_divider(self, pady=7)
        hdr_row = mkframe(self)
        hdr_row.pack(fill="x", pady=(0, 4))
        mklabel(hdr_row, text="Progress:", color=MUTED, font=FONT_SM).pack(side="left")
        self._status_lbl = mklabel(hdr_row, var=self.status_var, color=MUTED, font=FONT_SM)
        self._status_lbl.pack(side="right")
        self.pbar = SmoothProgressBar(self, self.progress_var, height=11)
        self.pbar.pack(fill="x")
        thin_divider(self, pady=7)
        btn_row = mkframe(self)
        btn_row.pack(fill="x")
        btn_text = "Encrypt File" if is_enc else "Decrypt File"
        GradientButton(btn_row, btn_text, self._on_action, width=112, height=23).pack(side="left")
        self._result_lbl = mklabel(btn_row, text="", color=SUCCESS, font=FONT_SM)
        self._result_lbl.pack(side="left", padx=(12, 0))

    def _pick_file(self):
        path = filedialog.askopenfilename() if self.mode == "enc" else filedialog.askopenfilename(
            filetypes=[("Vault files", "*.vault"), ("All files", "*.*")])
        if not path: return
        self.full_path = path
        name = os.path.basename(path)
        self.file_var.set(name if len(name) <= 42 else name[:20] + "…" + name[-19:])
        self._file_lbl.config(fg=TEXT);
        self._reset()

    def _toggle_pw(self):
        self._show_pw = not self._show_pw
        self.pw_entry.config(show="" if self._show_pw else "*")
        self._show_btn.config(text="Hide" if self._show_pw else "Show")

    def _reset(self):
        self.status_var.set("");
        self._status_lbl.config(fg=MUTED);
        self._result_lbl.config(text="");
        self.progress_var.set(0.0)

    def _set_status(self, msg, color=MUTED):
        self.status_var.set(msg);
        self._status_lbl.config(fg=color)

    def _progress_cb(self, val, msg=""):
        self.progress_var.set(val);
        self._set_status(msg)

    def _on_action(self):
        if not self.full_path or not self.pw_var.get(): return
        self._reset();
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            if self.mode == "enc":
                out = self.full_path + ".vault"
                encrypt_file(self.full_path, out, self.pw_var.get(), progress=self._progress_cb)
            else:
                out = self.full_path.removesuffix(".vault")
                decrypt_file(self.full_path, out, self.pw_var.get(), progress=self._progress_cb)
            self._result_lbl.config(text=f"→ {os.path.basename(out)[:31]}", fg=SUCCESS)
            self._set_status("Done", SUCCESS)
        except Exception as e:
            self._set_status(str(e), DANGER);
            self.progress_var.set(0.0)


# Main
class VaultApp(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("Vault — File Encryption")
        self.geometry("520x380")  # Kept original window size
        self.resizable(False, False)
        self.configure(bg=BG)

        # Load and resize
        self.ico_imgs = []
        for f in ["ico1.png", "ico2.png", "ico3.png", "ico4.png"]:
            img = Image.open(f).resize((22, 22), Image.LANCZOS)
            self.ico_imgs.append(ImageTk.PhotoImage(img))

        # Logo
        logo_raw = Image.open("ico1.png").resize((28, 28), Image.LANCZOS)
        self.logo_img = ImageTk.PhotoImage(logo_raw)

        self._active = 0
        self._build()

    def _build(self):
        self._hdr = tk.Canvas(self, height=56, bd=0, highlightthickness=0, bg=HDR_C)
        self._hdr.pack(fill="x")
        self._hdr.bind("<Configure>", self._draw_header)

        tk.Frame(self, bg=BORDER_LO, height=1).pack(fill="x")
        tk.Frame(self, bg=BORDER_HI, height=1).pack(fill="x")

        container = mkframe(self)
        container.pack(fill="both", expand=True)

        self._panels = [
            VaultPanel(container, "enc", self),
            VaultPanel(container, "dec", self),
            WizardPanel(container, self),
            InfoPanel(container)
        ]

        tk.Frame(self, bg=BORDER_LO, height=1).pack(fill="x")
        CipherStream(self).pack(fill="x")
        self._switch(0)

    def _draw_header(self, event=None):
        cv = self._hdr
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        draw_v3(cv, 0, 0, w, h, HDR_A, HDR_B, HDR_C)

        # Logo and Title
        cv.create_image(22, h // 2, image=self.logo_img)
        tx = 45
        cv.create_text(tx, h // 2 - 7, text="Vault", fill=WHITE, font=FONT_TITLE, anchor="w")
        cv.create_text(tx, h // 2 + 8, text="AES-256-GCM Secure", fill=MUTED, font=FONT_SM, anchor="w")

        # Tab Navigation
        tabs = ["Encrypt", "Decrypt", "Wizard", "Info"]
        btn_w = 72
        bx_start = w - 12 - len(tabs) * (btn_w + 4)

        for i, lbl in enumerate(tabs):
            active = (self._active == i)
            bx, by0, by1 = bx_start + i * (btn_w + 4), 5, 5 + (h - 10)

            bg_c = lerp_color(HDR_B, ACCENT_A, 0.30) if active else lerp_color(HDR_B, HDR_C, 0.50)
            bo_c = lerp_color(BORDER_HI, ACCENT_B, 0.55) if active else lerp_color(BORDER_HI, HDR_B, 0.30)

            cv.create_rectangle(bx, by0, bx + btn_w, by1, fill=bg_c, outline=bo_c)

            # Icon
            cv.create_image(bx + btn_w // 2, by0 + 13, image=self.ico_imgs[i])

            # label
            cv.create_text(bx + btn_w // 2, by1 - 7, text=lbl,
                           fill=WHITE if active else MUTED, font=FONT_SM, anchor="center")

            tag = f"_tab{i}"
            cv.create_rectangle(bx, by0, bx + btn_w, by1, fill="", outline="", tags=tag)
            cv.tag_bind(tag, "<ButtonRelease-1>", lambda e, ix=i: self._switch(ix))

    def _switch(self, idx):
        self._active = idx
        for i, panel in enumerate(self._panels):
            if i == idx:
                panel.pack(fill="both", expand=True)
            else:
                panel.pack_forget()
        self._draw_header()


if __name__ == "__main__":
    VaultApp().mainloop()