import os, sys, json, re, subprocess, shutil, zipfile, threading, datetime, hashlib, logging, time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, colorchooser
from pathlib import Path
from queue import Queue, Empty

# =============================
# ЛОГИРОВАНИЕ
# =============================
LOG_FILE = Path.home() / ".my_explorer.log"
logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
log = logging.getLogger("explorer")

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = (not IS_WIN and not IS_MAC)
FONT = "Segoe UI" if IS_WIN else ("Helvetica Neue" if IS_MAC else "DejaVu Sans")

def hex_to_rgb(h):
    h = str(h).lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def rgb_to_hex(r): return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in r)
def _clamp(v): return max(0, min(255, int(round(v))))
def mix(c1, c2, t):
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex(tuple(_clamp(a[i] + (b[i]-a[i])*t) for i in range(3)))
def shade(c, percent):
    return mix(c, "#000000" if percent < 0 else "#ffffff", abs(percent)/100.0)

# =============================
# ТЕМЫ
# =============================
THEMES = {
 "blue": {"BG":"#EAF6FF","PANEL":"#D7EDFF","TOOLBAR":"#C7E6FF","BUTTON":"#A7D8FF","BUTTON_HOVER":"#86C8FF","BUTTON_PRESSED":"#63B4FF",
          "ACCENT":"#2E90FF","ACCENT_HOVER":"#1D7CEA","ACCENT_PRESSED":"#1468CF","TEXT":"#083A5D","LIST_BG":"#FBFEFF","SELECT_BG":"#C9E8FF",
          "BORDER":"#9FD6FF","MUTED":"#4a7ba6","ENTRY_BG":"#FFFFFF","ENTRY_FG":"#083A5D","LIST_FG":"#123249","FOLDER_FG":"#0B67B2",
          "FILE_FG":"#173245","MENU_BG":"#F4FBFF","MENU_FG":"#083A5D","PREVIEW_BG":"#F7FBFF","BREADCRUMB":"#C7E6FF"},
 "dark": {"BG":"#1E1E1E","PANEL":"#2A2A2A","TOOLBAR":"#333333","BUTTON":"#3D3D3D","BUTTON_HOVER":"#4A4A4A","BUTTON_PRESSED":"#555555",
          "ACCENT":"#2E90FF","ACCENT_HOVER":"#1D7CEA","ACCENT_PRESSED":"#1468CF","TEXT":"#E6E6E6","LIST_BG":"#252525","SELECT_BG":"#3A3A3A",
          "BORDER":"#444444","MUTED":"#9A9A9A","ENTRY_BG":"#3C3C3C","ENTRY_FG":"#E6E6E6","LIST_FG":"#DDDDDD","FOLDER_FG":"#6DB3F2",
          "FILE_FG":"#DDDDDD","MENU_BG":"#2A2A2A","MENU_FG":"#E6E6E6","PREVIEW_BG":"#1A1A1A","BREADCRUMB":"#2A2A2A"},
 "yellow": {"BG":"#FFF8E1","PANEL":"#FFECB3","TOOLBAR":"#FFE082","BUTTON":"#FFD54F","BUTTON_HOVER":"#FFCA28","BUTTON_PRESSED":"#FFB300",
            "ACCENT":"#FFA000","ACCENT_HOVER":"#FF8F00","ACCENT_PRESSED":"#FF6F00","TEXT":"#5D4037","LIST_BG":"#FFFDE7","SELECT_BG":"#FFF59D",
            "BORDER":"#FFD54F","MUTED":"#8D6E63","ENTRY_BG":"#FFFFFF","ENTRY_FG":"#5D4037","LIST_FG":"#4E342E","FOLDER_FG":"#E65100",
            "FILE_FG":"#4E342E","MENU_BG":"#FFFDE7","MENU_FG":"#5D4037","PREVIEW_BG":"#FFFEF7","BREADCRUMB":"#FFE082"},
}
THEME_LABELS = {"blue": "голубая", "dark": "тёмная", "yellow": "жёлтая", "custom": "своя"}
THEME_FILE = Path.home() / ".my_explorer_theme"

def derive_custom(base):
    BG, PANEL, ACCENT, TEXT = base["BG"], base["PANEL"], base["ACCENT"], base["TEXT"]
    return {"BG":BG,"PANEL":PANEL,"TOOLBAR":shade(PANEL,8),"BUTTON":mix(ACCENT,"#ffffff",0.62),
            "BUTTON_HOVER":mix(ACCENT,"#ffffff",0.45),"BUTTON_PRESSED":mix(ACCENT,"#ffffff",0.28),
            "ACCENT":ACCENT,"ACCENT_HOVER":shade(ACCENT,-12),"ACCENT_PRESSED":shade(ACCENT,-22),
            "TEXT":TEXT,"LIST_BG":mix(BG,"#ffffff",0.55),"SELECT_BG":mix(ACCENT,"#ffffff",0.72),
            "BORDER":mix(ACCENT,"#ffffff",0.5),"MUTED":mix(TEXT,BG,0.45),"ENTRY_BG":mix(BG,"#ffffff",0.8),
            "ENTRY_FG":TEXT,"LIST_FG":TEXT,"FOLDER_FG":shade(ACCENT,-15),"FILE_FG":TEXT,
            "MENU_BG":mix(BG,"#ffffff",0.55),"MENU_FG":TEXT,"PREVIEW_BG":mix(BG,"#ffffff",0.6),"BREADCRUMB":PANEL}

def apply_colors(d):
    for k, v in d.items(): globals()[k] = v

def load_theme():
    try: data = json.loads(THEME_FILE.read_text())
    except Exception: data = {"name": "blue"}
    name = data.get("name", "blue")
    if name == "custom":
        base = data.get("base") or {}
        if all(k in base for k in ("BG","PANEL","ACCENT","TEXT")):
            apply_colors(derive_custom(base)); return "custom", base
        name = "blue"
    apply_colors(THEMES.get(name, THEMES["blue"]))
    return name, None

CURRENT_THEME, CUSTOM_BASE = load_theme()

def save_theme(name, base=None):
    try: THEME_FILE.write_text(json.dumps({"name": name, "base": base}))
    except Exception: pass

# =============================
# КОНФИГУРАЦИЯ
# =============================
CONFIG_FILE = Path.home() / ".my_explorer_config.json"
CONFIG_VERSION = 2
DEFAULT_CONFIG = {
    "version": CONFIG_VERSION,
    "show_hidden": False,
    "deep_search": False,
    "auto_size_folders": True,
    "confirm_delete": True,
    "open_zip_after": False,
    "rounded_rows": False,
    "show_preview": False,
    "last_window": {"width": 1450, "height": 760, "x": None, "y": None},
    "tabs": [{"left": None, "right": None, "single": False}],
    "active_tab": 0,
    "ctx_menu": False,
    "default_verb": False,
}

def migrate_config(cfg):
    if cfg.get("version", 1) == 1:
        for k in ("rounded_rows","show_preview","last_window","tabs","active_tab"):
            cfg.setdefault(k, DEFAULT_CONFIG[k])
        cfg["version"] = 2
    return cfg

def load_config():
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        if cfg.get("version", 1) < CONFIG_VERSION: cfg = migrate_config(cfg)
        return {**DEFAULT_CONFIG, **cfg}
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    try: CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    except Exception as e: log.warning("config save failed: %s", e)

CFG = load_config()

START_PATH = None
if len(sys.argv) > 1:
    _p = Path(sys.argv[1])
    if _p.is_dir(): START_PATH = _p

def app_command_for(arg="%1"):
    if getattr(sys, "frozen", False): return f'"{sys.executable}" "{arg}"'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}" "{arg}"'

def restart_app(extra_arg=None):
    cmd = [sys.executable]
    if not getattr(sys, "frozen", False): cmd.append(os.path.abspath(__file__))
    if extra_arg: cmd.append(str(extra_arg))
    subprocess.Popen(cmd)

def register_context_menu():
    if not IS_WIN: return False
    try:
        import winreg
        for cls, arg in (("Directory","%1"),("Drive","%1"),("Directory\\Background","%V")):
            base = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{cls}\\shell\\MyExplorer")
            winreg.SetValueEx(base, "", 0, winreg.REG_SZ, "Открыть в Моём Проводнике")
            ck = winreg.CreateKey(base, "command")
            winreg.SetValueEx(ck, "", 0, winreg.REG_SZ, app_command_for(arg))
            winreg.CloseKey(ck); winreg.CloseKey(base)
        return True
    except Exception: log.exception("ctx"); return False

def unregister_context_menu():
    if not IS_WIN: return False
    try:
        import winreg
        for cls in ("Directory","Drive","Directory\\Background"):
            try: winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{cls}\\shell\\MyExplorer\\command")
            except Exception: pass
            try: winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{cls}\\shell\\MyExplorer")
            except Exception: pass
        return True
    except Exception: return False

def set_default_folder_verb(enable):
    if not IS_WIN: return False
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\Directory\\shell")
        cfg = load_config()
        if enable:
            try:
                orig, _, _ = winreg.QueryValueEx(key, ""); cfg["orig_dir_shell"] = orig
            except FileNotFoundError: cfg["orig_dir_shell"] = None
            save_config(cfg); winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "MyExplorer")
        else:
            orig = cfg.get("orig_dir_shell")
            if orig: winreg.SetValueEx(key, "", 0, winreg.REG_SZ, orig)
            else:
                try: winreg.DeleteValue(key, "")
                except Exception: pass
        winreg.CloseKey(key); return True
    except Exception: return False

def linux_set_default():
    if not IS_LINUX: return False
    try:
        apps = Path.home()/".local"/"share"/"applications"; apps.mkdir(parents=True, exist_ok=True)
        d = apps/"myexplorer.desktop"
        exe = sys.executable if getattr(sys,"frozen",False) else f"{sys.executable} {os.path.abspath(__file__)}"
        d.write_text(f"[Desktop Entry]\nType=Application\nName=My Explorer\nExec={exe} %U\nTerminal=false\nCategories=System;FileTools;FileManager;\n")
        subprocess.run(["xdg-mime","default","myexplorer.desktop","inode/directory"], check=False)
        return True
    except Exception: return False

# =============================
# РАСШИРЕНИЯ
# =============================
IMAGE_EXTS = {".png",".jpg",".jpeg",".gif",".bmp",".webp",".ico",".tif",".tiff"}
AUDIO_EXTS = {".mp3",".wav",".flac",".aac",".ogg",".m4a",".wma",".opus"}
VIDEO_EXTS = {".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm",".m4v",".mpg",".mpeg"}
ARCHIVE_EXTS = {".zip",".rar",".7z",".tar",".gz",".bz2",".xz",".iso"}
EXEC_EXTS = {".exe",".msi",".bat",".cmd",".ps1",".appx",".sh"}
DOCUMENT_EXTS = {".doc",".docx",".odt",".rtf",".txt",".xlsx",".xls",".csv",".ppt",".pptx"}
TEXT_PREVIEW_EXTS = {".txt",".md",".log",".json",".xml",".yaml",".yml",".ini",".cfg",".conf",".py",".js",".ts",".html",".css",".c",".cpp",".h",".java",".php",".sh",".bat",".cmd",".ps1"}
PDF_EXTS = {".pdf"}
CODE_EXTS = {".py",".js",".html",".css",".json",".xml",".c",".cpp",".cs",".java",".php",".sh"}

# =============================
# АНИМАЦИИ
# =============================
def fade_window(win, duration=280, steps=16):
    try:
        win.attributes("-alpha", 0.0)
        def step(i):
            win.attributes("-alpha", min(1.0, (i+1)/steps))
            if i+1 < steps: win.after(int(duration/steps), lambda: step(i+1))
        win.after(0, lambda: step(0))
    except Exception: pass

def animate_widget_color(widget, to, attr="bg", steps=10, duration=180):
    try: c = hex_to_rgb(widget.cget(attr)); t = hex_to_rgb(to)
    except Exception: widget.configure(**{attr: to}); return
    def step(i):
        f = (i+1)/steps
        widget.configure(**{attr: rgb_to_hex(tuple(c[k]+(t[k]-c[k])*f for k in range(3)))})
        if i+1 < steps: widget.after(int(duration/steps), lambda: step(i+1))
    step(0)

# =============================
# КНОПКА
# =============================
class ModernButton(tk.Canvas):
    def __init__(self, master, text, command=None, accent=False, height=32, padx=16, radius=9, **kw):
        bg = master.cget("bg")
        self.text = text; self.command = command; self.pad = padx; self.enabled = True
        self.fgcol = "white" if accent else TEXT
        self.base = hex_to_rgb(ACCENT if accent else BUTTON)
        self.hover = hex_to_rgb(ACCENT_HOVER if accent else BUTTON_HOVER)
        self.press = hex_to_rgb(ACCENT_PRESSED if accent else BUTTON_PRESSED)
        self.cur = list(self.base); self.tgt = list(self.base); self._anim = None
        f = tkfont.Font(family=FONT, size=9, weight="bold")
        w = int(f.measure(text)) + padx*2
        super().__init__(master, width=w, height=height, bg=bg, highlightthickness=0, bd=0, cursor="hand2", **kw)
        self.w = w; self.h = height; self.r = radius
        self._shapes = []; self._txt = None
        self._draw()
        self.bind("<Enter>", lambda e: self._go(self.hover))
        self.bind("<Leave>", lambda e: self._go(self.base))
        self.bind("<ButtonPress-1>", lambda e: (self._go(self.press), self.coords(self._txt, self.w/2, self.h/2+1)))
        self.bind("<ButtonRelease-1>", self._release)
    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        if not enabled: self._go(self.base)
    def set_text(self, t):
        self.text = t
        f = tkfont.Font(family=FONT, size=9, weight="bold")
        self.w = int(f.measure(t)) + self.pad*2
        self.configure(width=self.w); self._draw()
    def _draw(self):
        self.delete("all"); self._shapes = []
        x0, y0, x1, y1, r = 0, 0, self.w, self.h, self.r
        col = rgb_to_hex(self.cur)
        self._shapes.append(self.create_rectangle(x0+r, y0, x1-r, y1, fill=col, outline=""))
        self._shapes.append(self.create_rectangle(x0, y0+r, x1, y1-r, fill=col, outline=""))
        for cx, cy in ((x0,y0),(x1-2*r,y0),(x0,y1-2*r),(x1-2*r,y1-2*r)):
            self._shapes.append(self.create_oval(cx, cy, cx+2*r, cy+2*r, fill=col, outline=""))
        self._txt = self.create_text(self.w/2, self.h/2, text=self.text, fill=self.fgcol, font=(FONT, 9, "bold"))
    def _go(self, rgb):
        self.tgt = list(rgb)
        if self._anim is None: self._tick()
    def _tick(self):
        done = True
        for i in range(3):
            d = self.tgt[i] - self.cur[i]
            if abs(d) > 0.5: self.cur[i] += d*0.35; done = False
            else: self.cur[i] = self.tgt[i]
        col = rgb_to_hex(self.cur)
        for s in self._shapes: self.itemconfigure(s, fill=col)
        if not done: self._anim = self.after(16, self._tick)
        else: self._anim = None
    def _release(self, e):
        self.coords(self._txt, self.w/2, self.h/2)
        if 0 <= e.x <= self.w and 0 <= e.y <= self.h:
            self._go(self.hover)
            if self.command and self.enabled: self.command()
        else: self._go(self.base)

# =============================
# ДИАЛОГИ
# =============================
def ask_text(parent, title, label, initial=""):
    dialog = tk.Toplevel(parent); dialog.title(title); dialog.configure(bg=BG)
    dialog.resizable(False, False); dialog.transient(parent); dialog.grab_set()
    w, h = 460, 190; parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width()-w)//2
    y = parent.winfo_rooty() + (parent.winfo_height()-h)//2
    dialog.geometry(f"{w}x{h}+{max(x,0)}+{max(y,0)}")
    fade_window(dialog)
    result = None
    tk.Label(dialog, text=label, bg=BG, fg=TEXT, font=(FONT,10,"bold")).pack(pady=(18,6), padx=20, anchor="w")
    entry = tk.Entry(dialog, font=(FONT,11), bg=ENTRY_BG, fg=ENTRY_FG, relief="solid", bd=1, highlightthickness=0)
    entry.pack(fill="x", padx=20, ipady=6); entry.insert(0, initial); entry.select_range(0, tk.END); entry.focus()
    def ok(e=None):
        nonlocal result; result = entry.get().strip(); dialog.destroy()
    entry.bind("<Return>", ok); dialog.bind("<Escape>", lambda e: dialog.destroy())
    b = tk.Frame(dialog, bg=BG); b.pack(pady=18)
    ModernButton(b, text="OK", command=ok, accent=True).pack(side="left", padx=6)
    ModernButton(b, text="Отмена", command=dialog.destroy).pack(side="left", padx=6)
    parent.wait_window(dialog); return result

def report_error(title, message, exc=None):
    log.exception("%s: %s", title, message)
    messagebox.showerror(title, f"{message}\n\n{exc}" if exc else message)

class ConflictDialog:
    def __init__(self, parent, src, dst):
        self.result = None; self.all = False
        self.dialog = tk.Toplevel(parent); self.dialog.title("Файл уже существует"); self.dialog.configure(bg=BG)
        self.dialog.resizable(False, False); self.dialog.transient(parent); self.dialog.grab_set()
        fade_window(self.dialog)
        tk.Label(self.dialog, text="Конфликт имён", bg=BG, fg=TEXT, font=(FONT,13,"bold")).pack(pady=(14,4), padx=18, anchor="w")
        info = tk.Frame(self.dialog, bg=BG); info.pack(fill="x", padx=18, pady=6)
        tk.Label(info, text="Исходный:", bg=BG, fg=MUTED, font=(FONT,9)).grid(row=0, column=0, sticky="w")
        tk.Label(info, text=str(src), bg=BG, fg=TEXT, font=(FONT,9), wraplength=400, justify="left").grid(row=0, column=1, sticky="w", padx=6)
        tk.Label(info, text="Существует:", bg=BG, fg=MUTED, font=(FONT,9)).grid(row=1, column=0, sticky="w")
        tk.Label(info, text=str(dst), bg=BG, fg=TEXT, font=(FONT,9), wraplength=400, justify="left").grid(row=1, column=1, sticky="w", padx=6)
        tk.Label(self.dialog, text="Что сделать?", bg=BG, fg=TEXT, font=(FONT,10,"bold")).pack(anchor="w", padx=18, pady=(10,4))
        btns = tk.Frame(self.dialog, bg=BG); btns.pack(fill="x", padx=18, pady=(0,10))
        ModernButton(btns, text="Заменить", command=lambda: self._done("replace")).pack(side="left", padx=3)
        ModernButton(btns, text="Пропустить", command=lambda: self._done("skip")).pack(side="left", padx=3)
        ModernButton(btns, text="Переименовать", command=lambda: self._done("rename")).pack(side="left", padx=3)
        ModernButton(btns, text="Отмена", command=lambda: self._done("cancel")).pack(side="left", padx=3)
        self.all_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.dialog, text="Применить ко всем", variable=self.all_var, bg=BG, fg=TEXT,
                       selectcolor=ENTRY_BG, activebackground=BG, font=(FONT,9)).pack(padx=18, anchor="w", pady=(0,10))
        self.dialog.wait_window(); self.all = self.all_var.get()
    def _done(self, r):
        self.result = r; self.all = self.all_var.get()
        self.dialog.destroy()

def ask_conflict(parent, src, dst):
    dlg = ConflictDialog(parent, src, dst)
    return dlg.result, dlg.all

class ProgressDialog:
    def __init__(self, parent, title, cancelable=True):
        self.dialog = tk.Toplevel(parent); self.dialog.title(title); self.dialog.configure(bg=BG)
        self.dialog.resizable(False, False); self.dialog.transient(parent)
        fade_window(self.dialog)
        w, h = 520, 180
        x = parent.winfo_rootx() + (parent.winfo_width()-w)//2
        y = parent.winfo_rooty() + (parent.winfo_height()-h)//2
        self.dialog.geometry(f"{w}x{h}+{max(x,0)}+{max(y,0)}")
        tk.Label(self.dialog, text=title, bg=BG, fg=TEXT, font=(FONT,11,"bold")).pack(pady=(14,4), padx=18, anchor="w")
        self.file_label = tk.Label(self.dialog, text="", bg=BG, fg=MUTED, font=(FONT,9), anchor="w")
        self.file_label.pack(fill="x", padx=18)
        self.progress = ttk.Progressbar(self.dialog, length=480, mode="determinate")
        self.progress.pack(pady=10, padx=18)
        self.status = tk.Label(self.dialog, text="", bg=BG, fg=TEXT, font=(FONT,9))
        self.status.pack(anchor="w", padx=18)
        self.cancelled = threading.Event(); self.cancelable = cancelable
        bf = tk.Frame(self.dialog, bg=BG); bf.pack(pady=10)
        self.cancel_btn = ModernButton(bf, text="Отмена", command=self._cancel)
        if cancelable: self.cancel_btn.pack(side="left", padx=6)
        ModernButton(bf, text="Свернуть", command=self.dialog.iconify).pack(side="left", padx=6)
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)
        self._closed = False
    def _cancel(self):
        if self.cancelable: self.cancelled.set()
        self.cancel_btn.set_enabled(False); self.cancel_btn.set_text("Отменяем...")
    def set_total(self, total):
        self.progress["maximum"] = max(1, total); self.progress["value"] = 0
    def update(self, value, current_file="", status=""):
        if self._closed: return
        self.dialog.after(0, lambda: self._update_ui(value, current_file, status))
    def _update_ui(self, value, current_file, status):
        if self._closed: return
        try:
            self.progress["value"] = value
            self.file_label.config(text=current_file); self.status.config(text=status)
        except Exception: pass
    def close(self):
        self._closed = True
        try: self.dialog.destroy()
        except Exception: pass

# =============================
# УТИЛИТЫ
# =============================
def is_valid_filename(name):
    if not name or name in (".",".."): return False
    return not any(c in r'\/:*?"<>|' for c in name)

def get_icon(path):
    try:
        if path.is_dir(): return "📁"
        e = path.suffix.lower()
        if e in IMAGE_EXTS: return "🖼"
        if e in AUDIO_EXTS: return "🎵"
        if e in VIDEO_EXTS: return "🎬"
        if e in ARCHIVE_EXTS: return "📦"
        if e in EXEC_EXTS: return "⚙"
        if e in PDF_EXTS: return "📕"
        if e in DOCUMENT_EXTS: return "📝"
        if e in CODE_EXTS: return "🧩"
        return "📄"
    except Exception: return "📄"

def human_size(size):
    size = float(size)
    for u in ["Б","КБ","МБ","ГБ","ТБ"]:
        if size < 1024 or u == "ТБ":
            return f"{int(size)} {u}" if u == "Б" else f"{size:.1f} {u}"
        size /= 1024

def natural_key(name):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", name)]

def get_drives():
    if IS_WIN:
        try:
            import ctypes; b = ctypes.windll.kernel32.GetLogicalDrives(); d = []
            for i in range(26):
                if b & (1 << i): d.append(f"{chr(ord('A')+i)}:\\")
            return d
        except Exception: return ["C:\\"]
    elif IS_MAC:
        try:
            vols = [str(p) for p in Path("/Volumes").iterdir()]
            return vols if vols else ["/"]
        except Exception: return ["/"]
    else:
        roots = ["/"]
        for base in ("/media","/mnt"):
            try:
                for p in Path(base).iterdir(): roots.append(str(p))
            except Exception: pass
        return roots

def _first_existing(candidates):
    for c in candidates:
        try:
            p = Path(c)
            if p.exists(): return p
        except Exception: pass
    return None

def get_user_folders():
    home = Path.home(); out = []
    for label, icon, names in [("Рабочий стол","🖥",["Desktop","Рабочий стол"]),
                               ("Документы","📄",["Documents","Документы"]),
                               ("Загрузки","⬇",["Downloads","Загрузки"]),
                               ("Изображения","🖼",["Pictures","Изображения"]),
                               ("Музыка","🎵",["Music","Музыка"]),
                               ("Видео","🎬",["Videos","Видео"])]:
        p = _first_existing([home/n for n in names])
        if p: out.append((label, icon, p))
    return out

def get_quick_links():
    items = []
    for label, icon, p in get_user_folders(): items.append((label, p))
    if IS_WIN:
        windir = Path(os.environ.get("WINDIR","C:\\Windows"))
        items += [("Папка Windows",windir),("System32",windir/"System32"),("Sysnative",windir/"Sysnative"),
                  ("SysWOW64",windir/"SysWOW64"),("Program Files",Path(os.environ.get("ProgramFiles","C:\\Program Files"))),
                  ("Program Files (x86)",Path(os.environ.get("ProgramFiles(x86)","C:\\Program Files (x86)"))),
                  ("ProgramData",Path(os.environ.get("ProgramData","C:\\ProgramData")))]
    return [(n, p) for n, p in items if p and p.exists()]

def open_file(path):
    try:
        if IS_WIN: os.startfile(str(path))
        elif IS_MAC: subprocess.Popen(["open", str(path)])
        else: subprocess.Popen(["xdg-open", str(path)])
    except Exception as e: report_error("Открыть файл", str(path), e)

def open_notepad(path):
    try:
        if IS_WIN: subprocess.Popen(["notepad.exe", str(path)])
        elif IS_MAC: subprocess.Popen(["open","-a","TextEdit",str(path)])
        else:
            ed = None
            for t in (os.environ.get("EDITOR"),"gedit","kate","xed","mousepad"):
                if t and shutil.which(t): ed = t; break
            if ed: subprocess.Popen([ed, str(path)])
            else: subprocess.Popen(["xdg-open", str(path)])
    except Exception as e: report_error("Редактор", "", e)

def is_inside(child, parent):
    try: child.resolve().relative_to(parent.resolve()); return True
    except ValueError: return False

def is_hidden(path):
    try:
        if path.name.startswith("."): return True
        if IS_WIN:
            import stat as sm
            return bool(path.stat().st_file_attributes & sm.FILE_ATTRIBUTE_HIDDEN)
    except Exception: pass
    return False

def get_unique_destination(dest):
    if not dest.exists(): return dest
    base = dest.stem if dest.is_file() else dest.name
    ext = dest.suffix if dest.is_file() else ""
    c = 1
    while True:
        nd = dest.parent / f"{base} ({c}){ext}"
        if not nd.exists(): return nd
        c += 1

def is_admin():
    try:
        if IS_WIN:
            import ctypes; return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception: return False

def relaunch_as_admin():
    if not IS_WIN: return False
    try:
        import ctypes
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                                f'"{os.path.abspath(sys.argv[0])}"', None, 1)
        return r > 32
    except Exception: return False

def send_to_recycle_bin(path):
    try:
        if IS_WIN:
            import ctypes
            from ctypes import wintypes
            class S(ctypes.Structure):
                _fields_=[("hwnd",wintypes.HWND),("wFunc",wintypes.UINT),("pFrom",ctypes.c_void_p),
                          ("pTo",ctypes.c_void_p),("fFlags",ctypes.c_ushort),("fAnyOperationsAborted",wintypes.BOOL),
                          ("hNameMappings",ctypes.c_void_p),("lpszProgressTitle",wintypes.LPCWSTR)]
            buf = ctypes.create_unicode_buffer(str(path)+"\0")
            op = S(); op.hwnd=None; op.wFunc=3; op.pFrom=ctypes.cast(buf, ctypes.c_void_p); op.pTo=None
            op.fFlags = 0x0040|0x0010|0x0004|0x0400
            op.fAnyOperationsAborted = False; op.hNameMappings=None; op.lpszProgressTitle=None
            return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0
        elif IS_MAC:
            trash = Path.home()/".Trash"; trash.mkdir(exist_ok=True)
            dest = get_unique_destination(trash / Path(path).name)
            shutil.move(str(path), str(dest)); return True
        else:
            for cmd in (["gio","trash",str(path)], ["trash-put",str(path)]):
                if shutil.which(cmd[0]):
                    subprocess.run(cmd, check=True); return True
            return False
    except Exception: return False

def delete_path(path):
    if send_to_recycle_bin(path): return
    if path.is_symlink(): path.unlink()
    elif path.is_dir(): shutil.rmtree(path)
    else: path.unlink()

def partial_hash(path, size=65536):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f: h.update(f.read(size))
    except Exception: return None
    return h.hexdigest()

def full_hash(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(131072), b""): h.update(chunk)
    except Exception: return None
    return h.hexdigest()

def count_folder(path):
    files = folders = 0; total_size = 0
    try:
        for r, ds, fs in os.walk(path):
            folders += len(ds); files += len(fs)
            for f in fs:
                try: total_size += (Path(r)/f).stat().st_size
                except Exception: pass
    except Exception: pass
    return files, folders, total_size

def safe_extract(zip_file, destination):
    destination = Path(destination).resolve()
    safe_members = []
    for member in zip_file.infolist():
        target = (destination / member.filename).resolve()
        try: target.relative_to(destination)
        except ValueError: raise ValueError(f"Небезопасный путь в ZIP: {member.filename}")
        safe_members.append(member)
    zip_file.extractall(destination, safe_members)

# =============================
# OPERATION MANAGER
# =============================
class OperationManager:
    def __init__(self, app):
        self.app = app; self.queue = Queue(); self._poll_thread()
    def _poll_thread(self):
        try:
            while True:
                try: cb, args = self.queue.get_nowait()
                except Empty: break
                try: cb(*args)
                except Exception: log.exception("ui cb")
        finally:
            self.app.root.after(50, self._poll_thread)
    def enqueue(self, cb, *args): self.queue.put((cb, args))
    def copy(self, sources, destination, parent): self._run_op("Копирование", sources, destination, parent, "copy")
    def move(self, sources, destination, parent): self._run_op("Перемещение", sources, destination, parent, "move")
    def delete(self, sources, parent): self._run_op_delete("Удаление", sources, parent)
    def zip(self, sources, dest_zip, parent): self._run_op_zip("Архивация", sources, dest_zip, parent)
    def unzip(self, archive, destination, parent): self._run_op_unzip("Распаковка", archive, destination, parent)

    def _run_op(self, title, sources, destination, parent, action):
        destination = Path(destination)
        items = [Path(s) for s in sources if Path(s).exists()]
        if not items: return
        dialog = ProgressDialog(parent, title)
        def worker():
            try:
                dialog.update(0, "Подготовка...", "Считаем файлы...")
                files_list = []; total_bytes = 0
                for src in items:
                    if src.is_file():
                        files_list.append(src)
                        try: total_bytes += src.stat().st_size
                        except Exception: pass
                    else:
                        for r, ds, fs in os.walk(src):
                            for f in fs:
                                files_list.append(Path(r)/f)
                                try: total_bytes += (Path(r)/f).stat().st_size
                                except Exception: pass
                dialog.set_total(len(files_list) or 1)
                conflict_action = None; conflict_all = False
                done = 0; copied = 0; skipped = 0; errors = 0
                for src in items:
                    if dialog.cancelled.is_set(): break
                    if not src.exists(): continue
                    target = destination / src.name
                    if src.is_dir():
                        if action == "move" and is_inside(destination, src):
                            skipped += 1; continue
                        try:
                            for r, ds, fs in os.walk(src):
                                if dialog.cancelled.is_set(): break
                                rel = Path(r).relative_to(src)
                                dst_dir = target / rel; dst_dir.mkdir(parents=True, exist_ok=True)
                                for f in fs:
                                    if dialog.cancelled.is_set(): break
                                    fp = Path(r)/f
                                    act_taken, nt, bd = self._copy_one(fp, dst_dir/f, action, parent, dialog, conflict_action, conflict_all)
                                    if act_taken == "cancel": dialog.cancelled.set(); break
                                    if act_taken == "skip": skipped += 1; done += 1; continue
                                    done += 1; copied += bd or 0
                                    dialog.update(done, fp.name, f"{human_size(copied)} / {human_size(total_bytes)}")
                        except Exception: errors += 1; log.exception("folder")
                        if action == "move" and not dialog.cancelled.is_set():
                            try:
                                if src.exists() and target.exists(): shutil.rmtree(src)
                            except Exception: pass
                    else:
                        act_taken, nt, bd = self._copy_one(src, target, action, parent, dialog, conflict_action, conflict_all)
                        if act_taken == "cancel": dialog.cancelled.set(); break
                        if act_taken == "skip": skipped += 1; done += 1; continue
                        done += 1; copied += bd or 0
                        dialog.update(done, src.name, f"{human_size(copied)} / {human_size(total_bytes)}")
                self.enqueue(dialog.close)
                verb = "Перемещено" if action == "move" else "Скопировано"
                msg = f"{verb}: {done}\nПропущено: {skipped}\nОшибок: {errors}"
                if dialog.cancelled.is_set(): msg += "\n\nОтменено."
                self.enqueue(lambda: messagebox.showinfo(title, msg))
            except Exception as e:
                self.enqueue(dialog.close); self.enqueue(lambda: report_error(title, str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _copy_one(self, src, target, action, parent, dialog, conflict_action, conflict_all):
        if target.exists():
            if conflict_all and conflict_action: chosen = conflict_action
            else:
                result, all_flag = ask_conflict(parent, src, target)
                if result is None or result == "cancel": return ("cancel", None, 0)
                chosen = result; conflict_all = all_flag
            if chosen == "skip": return ("skip", None, 0)
            elif chosen == "replace":
                try:
                    if target.is_dir(): shutil.rmtree(target)
                    else: target.unlink()
                except Exception: return ("cancel", None, 0)
            elif chosen == "rename": target = get_unique_destination(target)
        try: size = src.stat().st_size
        except Exception: size = 0
        try:
            if action == "move": shutil.move(str(src), str(target))
            else: shutil.copy2(str(src), str(target))
        except Exception: log.exception("file"); return ("cancel", None, 0)
        return (chosen, target, size)

    def _run_op_delete(self, title, sources, parent):
        items = [Path(s) for s in sources if Path(s).exists()]
        if not items: return
        dialog = ProgressDialog(parent, title)
        def worker():
            try:
                total = len(items); dialog.set_total(total)
                done = 0; errors = 0
                for p in items:
                    if dialog.cancelled.is_set(): break
                    try: delete_path(p); done += 1
                    except Exception: errors += 1; log.exception("del")
                    dialog.update(done, p.name, f"{done} / {total}")
                self.enqueue(dialog.close)
                msg = f"Удалено: {done}\nОшибок: {errors}"
                if dialog.cancelled.is_set(): msg += "\n\nОтменено."
                self.enqueue(lambda: messagebox.showinfo(title, msg))
            except Exception as e:
                self.enqueue(dialog.close); self.enqueue(lambda: report_error(title, str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _run_op_zip(self, title, sources, dest_zip, parent):
        dialog = ProgressDialog(parent, title)
        def worker():
            try:
                dialog.update(0, "Подготовка...", "Считаем...")
                files = []
                for s in sources:
                    src = Path(s)
                    if not src.exists(): continue
                    if src.is_file(): files.append((src, src.name))
                    else:
                        for r, ds, fs in os.walk(src):
                            for f in fs:
                                fp = Path(r)/f
                                files.append((fp, str(Path(src.name)/fp.relative_to(src))))
                dialog.set_total(len(files) or 1)
                done = 0; errors = 0
                with zipfile.ZipFile(str(dest_zip), "w", zipfile.ZIP_DEFLATED) as z:
                    for fp, arc in files:
                        if dialog.cancelled.is_set(): break
                        try: z.write(str(fp), arc); done += 1
                        except Exception: errors += 1
                        dialog.update(done, fp.name, f"{done} / {len(files)}")
                self.enqueue(dialog.close)
                msg = f"Архивировано: {done}\nОшибок: {errors}\n\n{dest_zip}"
                if dialog.cancelled.is_set(): msg += "\n\nОтменено."
                self.enqueue(lambda: messagebox.showinfo(title, msg))
            except Exception as e:
                self.enqueue(dialog.close); self.enqueue(lambda: report_error(title, str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _run_op_unzip(self, title, archive, destination, parent):
        dialog = ProgressDialog(parent, title)
        def worker():
            try:
                dialog.update(0, "Проверка архива...", "")
                archive = Path(archive)
                with zipfile.ZipFile(str(archive)) as z:
                    total_size = sum(i.file_size for i in z.infolist())
                    if total_size > 1_000_000_000:
                        answer = [None]
                        def ask():
                            answer[0] = messagebox.askyesno("Большой архив",
                                f"Распакованный архив ~{human_size(total_size)}.\nПродолжить?")
                        self.enqueue(ask)
                        while answer[0] is None: time.sleep(0.05)
                        if not answer[0]:
                            self.enqueue(dialog.close); return
                    safe_extract(z, destination)
                self.enqueue(dialog.close)
                self.enqueue(lambda: messagebox.showinfo(title, f"Распаковано в:\n{destination}"))
            except ValueError as e:
                self.enqueue(dialog.close); self.enqueue(lambda: report_error("Безопасность", str(e)))
            except Exception as e:
                self.enqueue(dialog.close); self.enqueue(lambda: report_error(title, str(e)))
        threading.Thread(target=worker, daemon=True).start()

# =============================
# BREADCRUMB
# =============================
class Breadcrumb(tk.Canvas):
    def __init__(self, master, on_click, **kw):
        super().__init__(master, height=32, bg=BREADCRUMB, highlightthickness=0, bd=0, **kw)
        self.on_click = on_click; self.segments = []
        self.bind("<Button-1>", self._click)
    def set_path(self, path):
        try: p = Path(path).resolve()
        except Exception: p = Path(path)
        self.segments = list(p.parts); self._redraw()
    def _redraw(self):
        self.delete("all"); x = 8; y = 16
        for i, seg in enumerate(self.segments):
            label = seg
            if IS_WIN and seg.endswith("\\"): label = seg.rstrip("\\") + ":"
            elif seg == "/": label = "💻"
            self.create_text(x+4, y, text=label, anchor="w", fill=ACCENT, font=(FONT,10,"bold"), tags=f"seg{i}")
            bbox = self.bbox(f"seg{i}") or (x, y-10, x+30, y+10)
            x += (bbox[2]-bbox[0]) + 10
            if i < len(self.segments)-1:
                self.create_text(x, y, text="›", anchor="w", fill=MUTED, font=(FONT,12)); x += 12
    def _click(self, e):
        x = 8
        for i, seg in enumerate(self.segments):
            label = seg
            if IS_WIN and seg.endswith("\\"): label = seg.rstrip("\\") + ":"
            elif seg == "/": label = "💻"
            f = tkfont.Font(family=FONT, size=10, weight="bold")
            w = f.measure(label) + 10
            if x <= e.x < x + w:
                target = seg if i == 0 else str(Path(*self.segments[:i+1]))
                self.on_click(target); return
            x += w + 12

# =============================
# PREVIEW PANE
# =============================
class PreviewPane(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=PREVIEW_BG, width=280, **kw)
        self.pack_propagate(False)
        tk.Label(self, text="Предпросмотр", bg=PREVIEW_BG, fg=MUTED,
                 font=(FONT,9,"bold"), anchor="w", padx=10, pady=6).pack(fill="x")
        self.content = tk.Frame(self, bg=PREVIEW_BG); self.content.pack(fill="both", expand=True)
        self._pil = None
        try:
            from PIL import Image, ImageTk
            self._pil = (Image, ImageTk)
        except Exception: pass
    def show(self, path):
        for w in self.content.winfo_children(): w.destroy()
        if path is None:
            tk.Label(self.content, text="(ничего не выбрано)", bg=PREVIEW_BG, fg=MUTED,
                     font=(FONT,9), wraplength=240, justify="center").pack(pady=20); return
        p = Path(path)
        if not p.exists():
            tk.Label(self.content, text="Не найдено", bg=PREVIEW_BG, fg=MUTED).pack(pady=20); return
        tk.Label(self.content, text=p.name, bg=PREVIEW_BG, fg=TEXT, font=(FONT,10,"bold"),
                 wraplength=250, justify="left").pack(padx=10, pady=(6,4), anchor="w")
        ext = p.suffix.lower()
        if p.is_dir():
            lbl = tk.Label(self.content, text="📁 считаем...", bg=PREVIEW_BG, fg=TEXT, font=(FONT,9),
                           wraplength=250, justify="left"); lbl.pack(padx=10, anchor="w")
            def worker():
                files, folders, total = count_folder(p)
                self.after(0, lambda: lbl.config(
                    text=f"📁 Папка\nФайлов: {files}\nПодпапок: {folders}\nРазмер: {human_size(total)}"))
            threading.Thread(target=worker, daemon=True).start()
        elif ext in IMAGE_EXTS and self._pil:
            try:
                Image, ImageTk = self._pil
                img = Image.open(str(p)); img.thumbnail((240, 240))
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(self.content, image=photo, bg=PREVIEW_BG); lbl.image = photo
                lbl.pack(padx=10, pady=4)
            except Exception:
                tk.Label(self.content, text="Не удалось показать", bg=PREVIEW_BG, fg=MUTED).pack(padx=10)
        elif ext in IMAGE_EXTS and not self._pil:
            tk.Label(self.content, text="🖼 картинка\n(установи Pillow: pip install pillow)",
                     bg=PREVIEW_BG, fg=MUTED, font=(FONT,9), wraplength=250, justify="left").pack(padx=10, anchor="w")
        elif ext in TEXT_PREVIEW_EXTS:
            try: text = p.read_text(encoding="utf-8", errors="replace")[:4000]
            except Exception: text = ""
            txt = tk.Text(self.content, bg=PREVIEW_BG, fg=TEXT, font=("Consolas",9),
                          wrap="word", padx=6, pady=6, relief="flat", bd=0)
            txt.insert("1.0", text); txt.configure(state="disabled")
            txt.pack(fill="both", expand=True, padx=6, pady=4)
        else:
            try: size = human_size(p.stat().st_size)
            except Exception: size = "?"
            tk.Label(self.content, text=f"{get_icon(p)}  {size}", bg=PREVIEW_BG, fg=TEXT,
                     font=(FONT,11)).pack(padx=10, pady=10, anchor="w")

# =============================
# ФАЙЛОВАЯ ПАНЕЛЬ
# =============================
class FilePanel:
    def __init__(self, parent, app, side):
        self.app = app; self.side = side
        try: self.current_path = START_PATH or Path.home()
        except Exception: self.current_path = Path.cwd()
        self.history = []; self.history_index = -1; self.forward_history = []
        self.filter_text = ""; self.sort_key = "name"; self.sort_reverse = False
        self.frame = tk.Frame(parent, bg=BG, padx=4, pady=4)
        self.header = tk.Label(self.frame, text="", bg=PANEL, fg=TEXT, anchor="w",
                               font=(FONT,9,"bold"), padx=6, pady=5); self.header.pack(fill="x")
        self.breadcrumb = Breadcrumb(self.frame, on_click=self.navigate); self.breadcrumb.pack(fill="x")
        inner = tk.Frame(self.frame, bg=BG); inner.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(inner, columns=("name","type","size","modified"),
                                 show="headings", selectmode="extended")
        self.tree.heading("name", text="Имя", command=lambda: self.set_sort("name"))
        self.tree.heading("type", text="Тип", command=lambda: self.set_sort("type"))
        self.tree.heading("size", text="Размер", command=lambda: self.set_sort("size"))
        self.tree.heading("modified", text="Изменён", command=lambda: self.set_sort("modified"))
        self.tree.column("name", width=280, anchor="w", stretch=True)
        self.tree.column("type", width=60, anchor="center", stretch=False)
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.column("modified", width=130, anchor="w", stretch=False)
        self.tree.tag_configure("folder", foreground=FOLDER_FG)
        self.tree.tag_configure("file", foreground=FILE_FG)
        sb = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.open_selected())
        self.tree.bind("<Return>", lambda e: self.open_selected())
        self.tree.bind("<BackSpace>", lambda e: self.go_up())
        self.tree.bind("<Button-1>", lambda e: self.app.set_active_panel(self))
        self.tree.bind("<FocusIn>", lambda e: self.app.set_active_panel(self))
        self.tree.bind("<F2>", lambda e: self.rename_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Button-3>", lambda e: self.app.show_tree_menu(e, self))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())

    def _on_select(self):
        self.app.update_status()
        if CFG.get("show_preview", False):
            sel = [x for x in self.tree.selection() if not x.startswith("__")]
            self.app.preview.show(sel[0] if sel else None)

    def set_active(self, active):
        animate_widget_color(self.header, ACCENT if active else PANEL, "bg")
        animate_widget_color(self.header, "white" if active else TEXT, "fg")

    def set_sort(self, key):
        if self.sort_key == key: self.sort_reverse = not self.sort_reverse
        else: self.sort_key = key; self.sort_reverse = False
        self.load_items(); self.app.update_status()

    def navigate(self, path, add_history=True):
        try: path = Path(path).resolve()
        except Exception as e: report_error("Путь", str(path), e); return
        if not path.exists():
            messagebox.showwarning("Не найдено", f"Папка не найдена:\n{path}"); return
        if path.is_file(): open_file(path); return
        if add_history:
            if self.history_index < 0 or Path(self.history[self.history_index]) != path:
                self.history = self.history[:self.history_index+1]
                self.history.append(str(path)); self.history_index += 1
                self.forward_history = []
        self.current_path = path
        self.header.config(text=str(path)); self.breadcrumb.set_path(path)
        self.load_items(); self.app.on_panel_navigated(self)

    def _sort_key(self, p):
        try:
            if self.sort_key == "size": return p.stat().st_size if p.is_file() else -1
            if self.sort_key == "type": return p.suffix.lower()
            if self.sort_key == "modified": return p.stat().st_mtime
        except Exception: pass
        return natural_key(p.name)

    def load_items(self):
        self.tree.delete(*self.tree.get_children())
        show_hidden = CFG.get("show_hidden", False)
        ft = self.filter_text.lower().strip()
        try: entries = list(self.current_path.iterdir())
        except PermissionError:
            self.tree.insert("", "end", iid="__no_access__",
                             values=("🔒 Нет доступа (запусти от администратора)","—","—","—")); return
        except Exception as e: report_error("Папка", str(self.current_path), e); return
        folders = []; files = []
        for item in entries:
            try:
                if not show_hidden and is_hidden(item): continue
                if ft and ft not in item.name.lower(): continue
                (folders if item.is_dir() else files).append(item)
            except Exception: pass
        folders.sort(key=self._sort_key, reverse=self.sort_reverse)
        files.sort(key=self._sort_key, reverse=self.sort_reverse)
        folder_iids = []
        for f in folders:
            iid = str(f); folder_iids.append(iid)
            try: mt = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
            except Exception: mt = "—"
            self.tree.insert("", "end", iid=iid, values=(f"{get_icon(f)} {f.name}","Папка","…",mt), tags=("folder",))
        for f in files:
            try:
                size = human_size(f.stat().st_size)
                mt = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
            except Exception: size = "?"; mt = "—"
            self.tree.insert("", "end", iid=str(f), values=(f"{get_icon(f)} {f.name}","Файл",size,mt), tags=("file",))
        if folder_iids and not ft and CFG.get("auto_size_folders", True):
            threading.Thread(target=self._size_worker,
                             args=(str(self.current_path), folder_iids[:50]), daemon=True).start()

    def _size_worker(self, start, folder_iids):
        for iid in folder_iids:
            p = Path(iid); total = 0
            try:
                for r, ds, fs in os.walk(p):
                    for f in fs:
                        try: total += (Path(r)/f).stat().st_size
                        except Exception: pass
            except Exception: pass
            self.app.root.after(0, lambda i=iid, t=total, s=start: self._set_size(i, t, s))

    def _set_size(self, iid, total, start):
        if str(self.current_path) != start: return
        if self.tree.exists(iid): self.tree.set(iid, "size", human_size(total))

    def set_filter(self, text):
        self.filter_text = text; self.load_items(); self.app.update_status()
    def refresh(self): self.navigate(self.current_path, add_history=False)
    def go_back(self):
        if self.history_index > 0:
            self.forward_history.append(self.history[self.history_index])
            self.history_index -= 1
            self.navigate(self.history[self.history_index], add_history=False)
    def go_forward(self):
        if self.forward_history:
            nxt = self.forward_history.pop()
            self.history.append(nxt); self.history_index += 1
            self.navigate(nxt, add_history=False)
    def go_up(self):
        p = self.current_path.parent
        if p and p != self.current_path: self.navigate(p)
    def get_selected_paths(self): return list(self.tree.selection())
    def select_all(self): self.tree.selection_set(self.tree.get_children())

    def open_selected(self):
        s = self.tree.selection()
        if not s: return
        self.tree.focus(s[0]); iid = self.tree.focus()
        if not iid or iid.startswith("__"): return
        p = Path(iid)
        try:
            if p.is_dir(): self.navigate(p)
            else: open_file(p)
        except Exception as e: report_error("Открыть", str(p), e)

    def create_folder(self):
        name = ask_text(self.frame, "Новая папка", "Имя новой папки:", "")
        if not name: return
        if not is_valid_filename(name):
            messagebox.showwarning("Имя", "Запрещённые символы"); return
        np = self.current_path / name
        if np.exists(): messagebox.showwarning("", "Уже существует"); return
        try: np.mkdir()
        except Exception as e: report_error("Папка", str(np), e); return
        self.refresh()

    def create_text_file(self):
        name = ask_text(self.frame, "Текстовый файл", "Имя:", "note.txt")
        if not name: return
        if "." not in name: name += ".txt"
        if not is_valid_filename(name):
            messagebox.showwarning("Имя", "Запрещённые символы"); return
        np = self.current_path / name
        if np.exists(): messagebox.showwarning("", "Уже существует"); return
        try: np.write_text("", encoding="utf-8")
        except Exception as e: report_error("Файл", str(np), e); return
        self.refresh()

    def rename_selected(self):
        s = [x for x in self.tree.selection() if not x.startswith("__")]
        if len(s) != 1: messagebox.showinfo("", "Выбери один элемент"); return
        p = Path(s[0])
        if not p.exists(): self.refresh(); return
        nn = ask_text(self.frame, "Переименовать", f"Новое имя для '{p.name}':", p.name)
        if not nn or nn == p.name: return
        if not is_valid_filename(nn):
            messagebox.showwarning("", "Запрещённые символы"); return
        np = p.with_name(nn)
        if np.exists(): messagebox.showwarning("", "Уже существует"); return
        try: p.rename(np)
        except Exception as e: report_error("Переименовать", str(p), e); return
        self.refresh()

    def delete_selected(self):
        s = [x for x in self.tree.selection() if not x.startswith("__")]
        if not s: return
        if CFG.get("confirm_delete", True):
            if not messagebox.askyesno("Удалить", f"Удалить {len(s)} элементов?"): return
        self.app.operations.delete(s, self.frame)

# =============================
# DUAL VIEW
# =============================
class DualView:
    def __init__(self, parent, app):
        self.app = app; self.frame = tk.Frame(parent, bg=BG)
        self.left = FilePanel(self.frame, app, "Левая панель")
        self.right = FilePanel(self.frame, app, "Правая панель")
        self.sep = tk.Frame(self.frame, width=4, bg=BORDER)
        self.left.frame.pack(side="left", fill="both", expand=True)
        self.sep.pack(side="left", fill="y")
        self.right.frame.pack(side="left", fill="both", expand=True)
        self.active = self.left; self.single = False
    def set_active(self, panel, update_app=True):
        self.active = panel
        self.left.set_active(panel is self.left); self.right.set_active(panel is self.right)
        if update_app: self.app.update_ui()
    def set_single(self, single):
        self.single = single
        if single:
            self.sep.pack_forget(); self.right.frame.pack_forget()
            self.active = self.left; self.left.set_active(True); self.right.set_active(False)
        else:
            self.sep.pack(side="left", fill="y")
            self.right.frame.pack(side="left", fill="both", expand=True)
        self.app.update_ui()

# =============================
# APP
# =============================
class ExplorerApp:
    def __init__(self, root):
        self.root = root
        root.title("Мой Проводник")
        g = CFG.get("last_window", {})
        w = g.get("width", 1450); h = g.get("height", 760)
        x, y = g.get("x"), g.get("y")
        root.geometry(f"{w}x{h}+{x}+{y}" if x is not None else f"{w}x{h}")
        root.minsize(900, 500)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._apply_style()
        self.operations = OperationManager(self)
        self.clipboard = None; self.tab_counter = 0; self.admin = is_admin()
        self.search_var = tk.StringVar()
        self.create_interface()
        self.bind_shortcuts()
        self._restore_tabs()
        self.update_ui()

    def _apply_style(self):
        self.root.configure(bg=BG); style = ttk.Style(self.root)
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("TNotebook", background=BG, bordercolor=BORDER)
        style.configure("TNotebook.Tab", background=BUTTON, foreground=TEXT, padding=(12,6), font=(FONT,9,"bold"))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected","white")])
        style.configure("Treeview", background=LIST_BG, fieldbackground=LIST_BG, foreground=LIST_FG,
                        rowheight=30, bordercolor=BORDER, font=(FONT,10))
        style.configure("Treeview.Heading", background=BUTTON, foreground=TEXT, bordercolor=BORDER,
                        relief="flat", padding=5, font=(FONT,9,"bold"))
        style.map("Treeview", background=[("selected", SELECT_BG)], foreground=[("selected", TEXT)])
        style.configure("Vertical.TScrollbar", background=BUTTON, troughcolor=BG, bordercolor=BORDER, arrowcolor=TEXT)

    def create_interface(self):
        top = tk.Frame(self.root, bg=TOOLBAR, padx=6, pady=6); top.pack(fill="x")
        self.back_btn = ModernButton(top, text="←", command=self.go_back); self.back_btn.pack(side="left", padx=2)
        self.fwd_btn = ModernButton(top, text="→", command=self.go_forward); self.fwd_btn.pack(side="left", padx=2)
        ModernButton(top, text="↑", command=self.go_up).pack(side="left", padx=2)
        ModernButton(top, text="⟳", command=self.refresh).pack(side="left", padx=2)
        self.panel_btn = ModernButton(top, text="2 панели", command=self.toggle_panels); self.panel_btn.pack(side="left", padx=2)
        self.preview_btn = ModernButton(top, text="👁", command=self.toggle_preview); self.preview_btn.pack(side="left", padx=2)
        self.theme_btn = ModernButton(top, text=f"🎨 {THEME_LABELS.get(CURRENT_THEME,'голубая')}",
                                      command=self.show_theme_menu); self.theme_btn.pack(side="left", padx=2)
        ModernButton(top, text="⚙", command=self.open_settings).pack(side="left", padx=2)
        ModernButton(top, text="Админ ✓" if self.admin else "Админ", command=self.admin_click,
                     accent=self.admin).pack(side="left", padx=2)
        self.address_var = tk.StringVar()
        self.address_entry = tk.Entry(top, textvariable=self.address_var, bg=ENTRY_BG, fg=ENTRY_FG,
                                      relief="flat", font=(FONT,10), highlightthickness=1,
                                      highlightbackground=BORDER, highlightcolor=ACCENT)
        self.address_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.address_entry.bind("<Return>", self._address_enter)

        act = tk.Frame(self.root, bg=PANEL, padx=6, pady=5); act.pack(fill="x")
        self.cut_btn = ModernButton(act, text="Вырезать", command=self.cut_selected); self.cut_btn.pack(side="left", padx=2)
        self.copy_btn = ModernButton(act, text="Копировать", command=self.copy_selected); self.copy_btn.pack(side="left", padx=2)
        self.paste_btn = ModernButton(act, text="Вставить", command=self.paste_items); self.paste_btn.pack(side="left", padx=2)
        self.delete_btn = ModernButton(act, text="Удалить", command=self.delete_selected); self.delete_btn.pack(side="left", padx=2)
        self.rename_btn = ModernButton(act, text="Переименовать", command=self.rename_selected); self.rename_btn.pack(side="left", padx=2)
        ModernButton(act, text="Массовое", command=self.bulk_rename).pack(side="left", padx=2)
        ModernButton(act, text="Дубликаты", command=self.find_duplicates).pack(side="left", padx=2)
        ModernButton(act, text="+ Вкладка", command=self.new_tab).pack(side="right", padx=2)
        ModernButton(act, text="× Вкладка", command=self.close_tab).pack(side="right", padx=2)

        sb = tk.Frame(self.root, bg=TOOLBAR, padx=6, pady=5); sb.pack(fill="x")
        tk.Label(sb, text="Поиск:", bg=TOOLBAR, fg=TEXT, font=(FONT,10,"bold")).pack(side="left", padx=(0,6))
        self.search_entry = tk.Entry(sb, textvariable=self.search_var, bg=ENTRY_BG, fg=ENTRY_FG, relief="flat", font=(FONT,10))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self.on_search_changed())
        ModernButton(sb, text="✕", command=self.clear_search).pack(side="left", padx=6)

        self.status = tk.Label(self.root, text="", bg=TOOLBAR, fg=TEXT, anchor="w", font=(FONT,9), padx=10, pady=6)
        self.status.pack(side="bottom", fill="x")

        body = tk.Frame(self.root, bg=BG); body.pack(fill="both", expand=True)
        self.build_sidebar(body)
        right = tk.Frame(body, bg=BG); right.pack(side="left", fill="both", expand=True)

        # ГЛАВНОЕ: grid-разметка, чтобы предпросмотр получил место
        right.columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(right)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.update_ui())

        self.preview = PreviewPane(right)
        if CFG.get("show_preview", False):
            self.preview.grid(row=0, column=1, sticky="ns", padx=4, pady=4)

        self.build_menus()

    def build_sidebar(self, parent):
        side = tk.Frame(parent, bg=PANEL, width=220)
        side.pack(side="left", fill="y"); side.pack_propagate(False)
        self._side_item(side, "🏠", "Главная", path=Path.home())
        self._side_header(side, "Быстрый доступ")
        for label, icon, p in get_user_folders(): self._side_item(side, icon, label, path=p)
        self._side_header(side, "Этот компьютер")
        for d in get_drives(): self._side_item(side, "💽", self._drive_label(d), path=Path(d))
        self._side_item(side, "🌐", "Сеть", action=lambda: messagebox.showinfo("Сеть","Пока не поддерживается"))

    def _side_header(self, master, text):
        tk.Frame(master, bg=PANEL, height=10).pack(fill="x")
        tk.Label(master, text=text, bg=PANEL, fg=MUTED, anchor="w", font=(FONT,9,"bold"), padx=10, pady=2).pack(fill="x")

    def _side_item(self, master, icon, text, path=None, action=None):
        lbl = tk.Label(master, text=f"{icon}  {text}", bg=PANEL, fg=TEXT, anchor="w",
                       font=(FONT,10), padx=10, pady=5, cursor="hand2"); lbl.pack(fill="x")
        lbl.bind("<Enter>", lambda e: animate_widget_color(lbl, BUTTON_HOVER, "bg"))
        lbl.bind("<Leave>", lambda e: animate_widget_color(lbl, PANEL, "bg"))
        def click(e):
            if action: action()
            elif path is not None: self.navigate_active(path)
        lbl.bind("<Button-1>", click)

    def _drive_label(self, d):
        if IS_WIN: return f"Диск ({d[0]}:)"
        name = d.rstrip("/").split("/")[-1]
        return name if name else d

    def build_menus(self):
        self.theme_menu = tk.Menu(self.root, tearoff=0, bg=MENU_BG, fg=MENU_FG, activebackground=SELECT_BG,
                                  activeforeground=MENU_FG, font=(FONT,10), relief="flat", bd=0)
        for k in ("blue","dark","yellow"):
            self.theme_menu.add_command(label=THEME_LABELS[k], command=lambda k=k: self.choose_theme(k))
        self.theme_menu.add_separator()
        self.theme_menu.add_command(label="своя тема...", command=self.open_theme_editor)

        self.context_menu = tk.Menu(self.root, tearoff=0, bg=MENU_BG, fg=MENU_FG, activebackground=SELECT_BG,
                                    activeforeground=MENU_FG, font=(FONT,10), relief="flat", bd=0)
        self.context_menu.add_command(label="Открыть", command=self.open_selected)
        self.context_menu.add_command(label="Открыть в редакторе", command=self.open_notepad_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Вырезать", command=self.cut_selected)
        self.context_menu.add_command(label="Копировать", command=self.copy_selected)
        self.context_menu.add_command(label="Вставить", command=self.paste_items)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Новая папка", command=self.new_folder)
        self.context_menu.add_command(label="Новый файл", command=self.new_text_file)
        self.context_menu.add_command(label="Переименовать", command=self.rename_selected)
        self.context_menu.add_command(label="Массовое переименование", command=self.bulk_rename)
        self.context_menu.add_command(label="Удалить", command=self.delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Архивировать в ZIP", command=self.zip_selected)
        self.context_menu.add_command(label="Распаковать ZIP", command=self.unzip_selected)
        self.context_menu.add_command(label="Дубликаты", command=self.find_duplicates)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Копировать путь", command=self.copy_path)
        self.context_menu.add_command(label="Свойства", command=self.show_properties)
        self.context_menu.add_command(label="Терминал здесь", command=self.open_cmd_here)

    def bind_shortcuts(self):
        # ВАЖНО: F3 убран полностью. Предпросмотр — только кнопка 👁 или настройки.
        self.root.bind("<Control-t>", lambda e: self.new_tab())
        self.root.bind("<Control-w>", lambda e: self.close_tab())
        self.root.bind("<Control-Tab>", lambda e: self._next_tab(1))
        self.root.bind("<Control-Shift-Tab>", lambda e: self._next_tab(-1))
        self.root.bind("<Control-n>", lambda e: self.new_folder())
        self.root.bind("<Control-Shift-N>", lambda e: self.new_folder())
        self.root.bind("<Control-p>", lambda e: self.toggle_panels())
        self.root.bind("<F5>", lambda e: self.refresh())
        self.root.bind("<F4>", lambda e: self.open_notepad_selected())
        self.root.bind("<Alt-Return>", lambda e: self.show_properties())
        self.root.bind("<Alt-Left>", lambda e: self.go_back())
        self.root.bind("<Alt-Right>", lambda e: self.go_forward())
        self.root.bind("<Alt-Up>", lambda e: self.go_up())
        self.root.bind("<Control-l>", lambda e: self.focus_address())
        self.root.bind("<Control-f>", lambda e: self.focus_search())
        self.root.bind("<Control-Shift-C>", lambda e: self.copy_path())
        self.root.bind("<Control-x>", lambda e: self.on_ctrl_x())
        self.root.bind("<Control-c>", lambda e: self.on_ctrl_c())
        self.root.bind("<Control-v>", lambda e: self.on_ctrl_v())
        self.root.bind("<Control-a>", lambda e: self.on_ctrl_a())
        self.root.bind("<Escape>", lambda e: self.clear_search())

    def entry_has_focus(self):
        try: return isinstance(self.root.focus_get(), tk.Entry)
        except Exception: return False
    def on_ctrl_x(self):
        if not self.entry_has_focus(): self.cut_selected()
    def on_ctrl_c(self):
        if not self.entry_has_focus(): self.copy_selected()
    def on_ctrl_v(self):
        if not self.entry_has_focus(): self.paste_items()
    def on_ctrl_a(self):
        if not self.entry_has_focus(): self.select_all()
    def focus_address(self):
        self.address_entry.focus(); self.address_entry.select_range(0, tk.END)
    def focus_search(self):
        self.search_entry.focus(); self.search_entry.select_range(0, tk.END)
    def _address_enter(self, e):
        text = self.address_var.get().strip()
        if not text: return
        p = Path(text).expanduser()
        if p.exists(): self.navigate_active(p)
        else: messagebox.showwarning("Не найдено", f"Путь не найден:\n{text}")
    def _next_tab(self, direction):
        tabs = self.notebook.tabs()
        if len(tabs) < 2: return
        idx = (tabs.index(self.notebook.select()) + direction) % len(tabs)
        self.notebook.select(tabs[idx])

    def toggle_panels(self):
        d = self.current_dual()
        if d: d.set_single(not d.single)

    def toggle_preview(self):
        cfg = load_config()
        cfg["show_preview"] = not cfg.get("show_preview", False)
        save_config(cfg); CFG.update(cfg)
        if cfg["show_preview"]:
            self.preview.grid(row=0, column=1, sticky="ns", padx=4, pady=4)
            p = self.active_panel()
            if p:
                sel = [x for x in p.tree.selection() if not x.startswith("__")]
                self.preview.show(sel[0] if sel else None)
        else:
            self.preview.grid_remove()

    def admin_click(self):
        if self.admin: messagebox.showinfo("","Уже от администратора"); return
        if not IS_WIN: messagebox.showinfo("","Через sudo вручную"); return
        if not messagebox.askyesno("","Перезапустить от администратора?"): return
        if relaunch_as_admin(): self.root.destroy()

    def current_dual(self):
        s = self.notebook.select()
        if not s: return None
        return getattr(self.root.nametowidget(s), "dual_view", None)
    def active_panel(self):
        d = self.current_dual(); return d.active if d else None
    def set_active_panel(self, panel):
        d = self.current_dual()
        if d and panel in (d.left, d.right): d.set_active(panel, update_app=False)
        self.update_ui()

    def update_ui(self):
        d = self.current_dual()
        if d:
            self.panel_btn.set_text("1 панель" if d.single else "2 панели")
            d.set_active(d.active, update_app=False)
            try: self.notebook.tab(d.frame, text=f"📁 {d.active.current_path.name or 'Корень'}")
            except Exception: pass
        p = self.active_panel()
        if p:
            self.address_var.set(str(p.current_path)); self.search_var.set(p.filter_text)
        else:
            self.address_var.set(""); self.search_var.set("")
        self._update_buttons(); self.update_status()

    def _update_buttons(self):
        p = self.active_panel(); has_sel = False; single = False
        if p:
            s = [x for x in p.tree.selection() if not x.startswith("__")]
            has_sel = bool(s); single = (len(s) == 1)
        self.cut_btn.set_enabled(has_sel); self.copy_btn.set_enabled(has_sel)
        self.delete_btn.set_enabled(has_sel); self.rename_btn.set_enabled(single)
        self.paste_btn.set_enabled(bool(self.clipboard))
        self.back_btn.set_enabled(bool(p and p.history_index > 0))
        self.fwd_btn.set_enabled(bool(p and p.forward_history))

    def update_status(self):
        p = self.active_panel()
        if not p: self.status.config(text=""); return
        count = len(p.tree.get_children())
        sel_text = ""
        s = [x for x in p.tree.selection() if not x.startswith("__")]
        if s:
            total = 0
            for x in s:
                try:
                    pp = Path(x)
                    if pp.is_file(): total += pp.stat().st_size
                except Exception: pass
            sel_text = f" | Выбрано: {len(s)} ({human_size(total)})"
        clip = ""
        if self.clipboard:
            a, items = self.clipboard
            clip = f" | {'Вырезано' if a=='move' else 'Скопировано'}: {len(items)}"
        mode = "⚠ Админ" if self.admin else ""
        self.status.config(text=f"{mode} {p.side} | {p.current_path} | {count} элементов{sel_text}{clip}")

    def on_panel_navigated(self, panel):
        if panel is self.active_panel():
            self.address_var.set(str(panel.current_path)); self.search_var.set(panel.filter_text)
        self.update_status()
    def on_search_changed(self):
        p = self.active_panel()
        if p: p.set_filter(self.search_var.get())
    def clear_search(self):
        self.search_var.set("")
        p = self.active_panel()
        if p: p.set_filter("")

    def _new_dual(self):
        d = DualView(self.notebook, self); d.frame.dual_view = d; return d
    def new_tab(self):
        self.tab_counter += 1
        d = self._new_dual()
        self.notebook.add(d.frame, text=f"Вкладка {self.tab_counter}")
        self.notebook.select(d.frame); self.update_ui()
    def close_tab(self):
        if self.notebook.index("end") <= 1: return
        c = self.notebook.select()
        if not c: return
        w = self.root.nametowidget(c); self.notebook.forget(c)
        try: w.destroy()
        except Exception: pass
        self.update_ui()

    def _restore_tabs(self):
        tabs = CFG.get("tabs", []) or [{"left": None, "right": None, "single": False}]
        for t in tabs:
            d = self._new_dual()
            self.notebook.add(d.frame, text="Вкладка")
            try:
                if t.get("left"):
                    p = Path(t["left"])
                    if p.exists(): d.left.navigate(p, add_history=False)
            except Exception: pass
            try:
                if t.get("right"):
                    p = Path(t["right"])
                    if p.exists(): d.right.navigate(p, add_history=False)
            except Exception: pass
            if t.get("single"): d.set_single(True)
        try: self.notebook.select(CFG.get("active_tab", 0))
        except Exception: pass
        for tab in self.notebook.tabs():
            w = self.root.nametowidget(tab)
            if hasattr(w, "dual_view"):
                try: self.notebook.tab(tab, text=f"📁 {w.dual_view.active.current_path.name or 'Корень'}")
                except Exception: pass

    def _on_close(self):
        try:
            cfg = load_config()
            cfg["last_window"] = {"width": self.root.winfo_width(), "height": self.root.winfo_height(),
                                  "x": self.root.winfo_x(), "y": self.root.winfo_y()}
            tabs = []; active_tab = 0
            for i, tab in enumerate(self.notebook.tabs()):
                w = self.root.nametowidget(tab)
                if not hasattr(w, "dual_view"): continue
                d = w.dual_view
                tabs.append({"left": str(d.left.current_path), "right": str(d.right.current_path), "single": d.single})
                if tab == self.notebook.select(): active_tab = i
            cfg["tabs"] = tabs or [{"left": None, "right": None, "single": False}]
            cfg["active_tab"] = active_tab
            save_config(cfg)
        except Exception: log.exception("save state")
        self.root.destroy()

    def show_theme_menu(self):
        try: self.theme_menu.tk_popup(self.theme_btn.winfo_rootx(), self.theme_btn.winfo_rooty()+self.theme_btn.winfo_height())
        finally: self.theme_menu.grab_release()
    def choose_theme(self, name):
        if name == CURRENT_THEME: return
        save_theme(name)
        restart_app(str(self.active_panel().current_path) if self.active_panel() else None)
        self.root.destroy()
    def open_theme_editor(self):
        base = CUSTOM_BASE or {"BG":BG,"PANEL":PANEL,"ACCENT":ACCENT,"TEXT":TEXT}
        dialog = tk.Toplevel(self.root); dialog.title("Своя тема"); dialog.configure(bg=BG)
        dialog.transient(self.root); dialog.grab_set(); dialog.resizable(False, False); fade_window(dialog)
        entries = {}; row = 0
        for key, label in [("BG","Фон"),("PANEL","Панели"),("ACCENT","Акцент"),("TEXT","Текст")]:
            tk.Label(dialog, text=label, bg=BG, fg=TEXT, font=(FONT,10,"bold"), width=8, anchor="w"
                     ).grid(row=row, column=0, padx=10, pady=6, sticky="w")
            e = tk.Entry(dialog, font=(FONT,10), bg=ENTRY_BG, fg=ENTRY_FG, width=10, relief="solid", bd=1)
            e.insert(0, base.get(key,"#888888")); e.grid(row=row, column=1, padx=4, pady=6)
            def pick(k=key, ent=e):
                r = colorchooser.askcolor(color=ent.get(), parent=dialog)
                if r and r[1]: ent.delete(0,"end"); ent.insert(0, r[1])
            ModernButton(dialog, text="🎨", command=pick).grid(row=row, column=2, padx=4, pady=6)
            entries[key] = e; row += 1
        def apply():
            nb = {}
            for k, e in entries.items():
                v = e.get().strip()
                if not v.startswith("#"): v = "#" + v
                if len(v) != 7 or not all(c in "0123456789abcdefABCDEF" for c in v[1:]):
                    messagebox.showwarning("Цвет", f"Неверный цвет {k}"); return
                nb[k] = v.upper()
            save_theme("custom", nb)
            restart_app(str(self.active_panel().current_path) if self.active_panel() else None)
            self.root.destroy()
        bf = tk.Frame(dialog, bg=BG); bf.grid(row=row, column=0, columnspan=3, pady=12)
        ModernButton(bf, text="Применить", command=apply, accent=True).pack(side="left", padx=6)
        ModernButton(bf, text="Отмена", command=dialog.destroy).pack(side="left", padx=6)

    def open_settings(self):
        cfg = load_config()
        dialog = tk.Toplevel(self.root); dialog.title("Настройки"); dialog.configure(bg=BG)
        dialog.transient(self.root); dialog.grab_set(); dialog.resizable(False, False); fade_window(dialog)
        row = 0; vars = {}
        for key, label in [("show_hidden","Показывать скрытые файлы"),
                           ("auto_size_folders","Автоматически считать размеры папок"),
                           ("confirm_delete","Подтверждать удаление"),
                           ("show_preview","Панель предпросмотра")]:
            v = tk.BooleanVar(value=cfg.get(key, False))
            tk.Checkbutton(dialog, text=label, variable=v, bg=BG, fg=TEXT, selectcolor=ENTRY_BG,
                           activebackground=BG, font=(FONT,10), anchor="w"
                           ).grid(row=row, column=0, columnspan=2, padx=16, pady=4, sticky="w")
            vars[key] = v; row += 1
        ctx_var = tk.BooleanVar(value=cfg.get("ctx_menu", False))
        tk.Checkbutton(dialog, text="«Открыть в Моём Проводнике» в правом клике (Windows)",
                       variable=ctx_var, bg=BG, fg=TEXT, selectcolor=ENTRY_BG, activebackground=BG,
                       font=(FONT,10), anchor="w").grid(row=row, column=0, columnspan=2, padx=16, pady=4, sticky="w"); row += 1
        if IS_LINUX:
            ModernButton(dialog, text="Файловый менеджер по умолчанию (Linux)",
                         command=lambda: (linux_set_default(), messagebox.showinfo("","Готово"))
                         ).grid(row=row, column=0, columnspan=2, padx=16, pady=6); row += 1
        def apply():
            for k, v in vars.items(): cfg[k] = v.get()
            cfg["ctx_menu"] = ctx_var.get()
            save_config(cfg); CFG.update(cfg)
            if IS_WIN:
                if ctx_var.get(): register_context_menu()
                else: unregister_context_menu()
            dialog.destroy()
            p = self.active_panel()
            if p: p.load_items()
            if cfg["show_preview"]: self.preview.grid(row=0, column=1, sticky="ns", padx=4, pady=4)
            else: self.preview.grid_remove()
            messagebox.showinfo("Настройки", "Сохранено")
        bf = tk.Frame(dialog, bg=BG); bf.grid(row=row, column=0, columnspan=2, pady=12)
        ModernButton(bf, text="Сохранить", command=apply, accent=True).pack(side="left", padx=6)
        ModernButton(bf, text="Отмена", command=dialog.destroy).pack(side="left", padx=6)

    def show_tree_menu(self, event, panel):
        self.set_active_panel(panel)
        item = panel.tree.identify_row(event.y)
        if item and not item.startswith("__"):
            if item not in panel.tree.selection(): panel.tree.selection_set(item)
            panel.tree.focus(item)
        try: self.context_menu.tk_popup(event.x_root, event.y_root)
        finally: self.context_menu.grab_release()

    def navigate_active(self, path):
        p = self.active_panel()
        if p: p.navigate(path)
    def go_back(self):
        p = self.active_panel()
        if p: p.go_back()
    def go_forward(self):
        p = self.active_panel()
        if p: p.go_forward()
    def go_up(self):
        p = self.active_panel()
        if p: p.go_up()
    def refresh(self):
        p = self.active_panel()
        if p: p.refresh()
    def new_folder(self):
        p = self.active_panel()
        if p: p.create_folder()
    def new_text_file(self):
        p = self.active_panel()
        if p: p.create_text_file()
    def rename_selected(self):
        p = self.active_panel()
        if p: p.rename_selected()
    def delete_selected(self):
        p = self.active_panel()
        if p: p.delete_selected()
    def select_all(self):
        p = self.active_panel()
        if p: p.select_all()
    def open_selected(self):
        p = self.active_panel()
        if p: p.open_selected()
    def open_notepad_selected(self):
        p = self.active_panel()
        if not p: return
        s = [x for x in p.get_selected_paths() if not x.startswith("__")]
        for x in s:
            pp = Path(x)
            if pp.is_file(): open_notepad(pp)
    def cut_selected(self):
        p = self.active_panel()
        if not p: return
        s = [x for x in p.get_selected_paths() if not x.startswith("__")]
        if not s: return
        self.clipboard = ("move", s); self.update_status()
    def copy_selected(self):
        p = self.active_panel()
        if not p: return
        s = [x for x in p.get_selected_paths() if not x.startswith("__")]
        if not s: return
        self.clipboard = ("copy", s); self.update_status()
    def paste_items(self):
        p = self.active_panel()
        if not p or not self.clipboard: return
        action, items = self.clipboard
        if action == "move":
            self.operations.move(items, p.current_path, p.frame); self.clipboard = None
        else:
            self.operations.copy(items, p.current_path, p.frame)
        self.update_status()
    def copy_path(self):
        p = self.active_panel()
        if not p: return
        s = [x for x in p.get_selected_paths() if not x.startswith("__")]
        text = "\n".join(s) if s else str(p.current_path)
        self.root.clipboard_clear(); self.root.clipboard_append(text)
        self.status.config(text="Скопирован путь")
    def show_properties(self):
        p = self.active_panel()
        if not p: return
        s = [x for x in p.get_selected_paths() if not x.startswith("__")]
        paths = [Path(x) for x in s] if s else [p.current_path]
        dialog = tk.Toplevel(self.root); dialog.title("Свойства"); dialog.configure(bg=BG)
        dialog.resizable(False, False); dialog.transient(self.root); dialog.grab_set(); fade_window(dialog)
        if len(paths) == 1:
            p = paths[0]
            tk.Label(dialog, text=p.name, bg=BG, fg=TEXT, font=(FONT,12,"bold")).pack(pady=10, padx=20, anchor="w")
            tk.Label(dialog, text=f"Путь: {p}", bg=BG, fg=TEXT, font=(FONT,10)).pack(padx=20, anchor="w")
            tk.Label(dialog, text=f"Тип: {'Папка' if p.is_dir() else 'Файл'}", bg=BG, fg=TEXT, font=(FONT,10)).pack(padx=20, anchor="w")
            size_lbl = tk.Label(dialog, text="Размер: считаем...", bg=BG, fg=TEXT, font=(FONT,10)); size_lbl.pack(padx=20, anchor="w")
            def worker():
                if p.is_file():
                    try: sz = human_size(p.stat().st_size)
                    except Exception: sz = "?"
                    self.root.after(0, lambda: size_lbl.config(text=f"Размер: {sz}"))
                else:
                    files, folders, total = count_folder(p)
                    self.root.after(0, lambda: size_lbl.config(
                        text=f"Размер: {human_size(total)} ({files} файлов, {folders} папок)"))
            threading.Thread(target=worker, daemon=True).start()
        else:
            tk.Label(dialog, text=f"Выбрано: {len(paths)}", bg=BG, fg=TEXT, font=(FONT,11)).pack(pady=10, padx=20, anchor="w")
        ModernButton(dialog, text="Закрыть", command=dialog.destroy, accent=True).pack(pady=12)
    def open_cmd_here(self):
        p = self.active_panel()
        if not p: return
        try:
            if IS_WIN: subprocess.Popen(["cmd","/k",f'cd /d "{p.current_path}"'], cwd=str(p.current_path))
            elif IS_MAC: subprocess.Popen(["open","-a","Terminal", str(p.current_path)])
            else:
                term = None
                for t in ("x-terminal-emulator","gnome-terminal","konsole","xterm"):
                    if shutil.which(t): term = t; break
                if term: subprocess.Popen([term], cwd=str(p.current_path))
        except Exception as e: report_error("Терминал","", e)

    def bulk_rename(self):
        p = self.active_panel()
        if not p: return
        sel = [Path(x) for x in p.get_selected_paths() if not x.startswith("__")]
        if not sel: messagebox.showinfo("", "Сначала выдели файлы"); return
        dialog = tk.Toplevel(self.root); dialog.title(f"Массовое ({len(sel)})"); dialog.configure(bg=BG)
        dialog.transient(self.root); dialog.grab_set(); dialog.geometry("640x520"); fade_window(dialog)
        f1 = tk.Frame(dialog, bg=BG); f1.pack(fill="x", padx=16, pady=8)
        tk.Label(f1, text="Найти:", bg=BG, fg=TEXT, font=(FONT,10,"bold")).pack(side="left")
        find_var = tk.StringVar()
        tk.Entry(f1, textvariable=find_var, bg=ENTRY_BG, fg=ENTRY_FG, relief="solid", bd=1, width=16).pack(side="left", padx=4)
        tk.Label(f1, text="Заменить на:", bg=BG, fg=TEXT, font=(FONT,10,"bold")).pack(side="left")
        repl_var = tk.StringVar()
        tk.Entry(f1, textvariable=repl_var, bg=ENTRY_BG, fg=ENTRY_FG, relief="solid", bd=1, width=16).pack(side="left", padx=4)
        f2 = tk.Frame(dialog, bg=BG); f2.pack(fill="x", padx=16)
        num_var = tk.BooleanVar()
        tk.Checkbutton(f2, text="Добавить номер", variable=num_var, bg=BG, fg=TEXT, selectcolor=ENTRY_BG, font=(FONT,10)).pack(side="left")
        start_var = tk.StringVar(value="1")
        tk.Entry(f2, textvariable=start_var, bg=ENTRY_BG, fg=ENTRY_FG, relief="solid", bd=1, width=6).pack(side="left", padx=4)
        date_var = tk.BooleanVar()
        tk.Checkbutton(f2, text="Добавить дату", variable=date_var, bg=BG, fg=TEXT, selectcolor=ENTRY_BG, font=(FONT,10)).pack(side="left", padx=(16,0))
        tk.Label(dialog, text="Предпросмотр:", bg=BG, fg=TEXT, font=(FONT,10,"bold")).pack(anchor="w", padx=16, pady=6)
        prev = tk.Text(dialog, bg=LIST_BG, fg=LIST_FG, font=("Consolas",10), relief="solid", bd=1)
        prev.pack(fill="both", expand=True, padx=16)
        def build():
            res = []
            try: st = int(start_var.get())
            except Exception: st = 1
            f = find_var.get()
            for i, pp in enumerate(sel):
                base = pp.stem if pp.is_file() else pp.name
                ext = pp.suffix if pp.is_file() else ""
                name = base
                if f: name = name.replace(f, repl_var.get())
                if date_var.get(): name += f" {datetime.date.today():%Y-%m-%d}"
                if num_var.get(): name += f"_{st+i}"
                res.append((pp, name+ext))
            return res
        def update(*a):
            prev.delete("1.0","end")
            for pp, new in build(): prev.insert("end", f"{pp.name}  →  {new}\n")
        for v in (find_var, repl_var, start_var): v.trace_add("write", update)
        num_var.trace_add("write", update); date_var.trace_add("write", update)
        def apply():
            done = err = 0
            for pp, new in build():
                if not is_valid_filename(new): err += 1; continue
                np = pp.with_name(new)
                if np.exists(): err += 1; continue
                try: pp.rename(np); done += 1
                except Exception: err += 1
            dialog.destroy(); p.refresh()
            messagebox.showinfo("Готово", f"Переименовано: {done}\nОшибок: {err}")
        bf = tk.Frame(dialog, bg=BG); bf.pack(pady=12)
        ModernButton(bf, text="Применить", command=apply, accent=True).pack(side="left", padx=6)
        ModernButton(bf, text="Отмена", command=dialog.destroy).pack(side="left", padx=6)
        update()

    def find_duplicates(self):
        p = self.active_panel()
        if not p: return
        start = str(p.current_path)
        dialog = tk.Toplevel(self.root); dialog.title("Поиск дубликатов..."); dialog.configure(bg=BG)
        dialog.geometry("900x520"); dialog.transient(self.root); fade_window(dialog)
        tk.Label(dialog, text="Сканируем...", bg=BG, fg=TEXT, font=(FONT,10,"bold")).pack(pady=10)
        tree = ttk.Treeview(dialog, columns=("name","size","path"), show="headings")
        tree.heading("name", text="Имя"); tree.heading("size", text="Размер"); tree.heading("path", text="Путь")
        tree.column("name", width=220, anchor="w"); tree.column("size", width=90, anchor="e"); tree.column("path", width=520, anchor="w")
        tree.pack(fill="both", expand=True, padx=10)
        bf = tk.Frame(dialog, bg=BG); bf.pack(pady=10)
        def do_delete():
            s = [x for x in tree.selection() if not x.startswith("__grp")]
            if not s: return
            if not messagebox.askyesno("", f"Удалить {len(s)} файлов?"): return
            self.operations.delete(s, p.frame)
        ModernButton(bf, text="Удалить выбранные", command=do_delete, accent=True).pack(side="left", padx=6)
        ModernButton(bf, text="Закрыть", command=dialog.destroy).pack(side="left", padx=6)
        def worker():
            bysize = {}
            for r, d, fs in os.walk(start):
                for f in fs:
                    fp = Path(r)/f
                    try: bysize.setdefault(fp.stat().st_size, []).append(fp)
                    except Exception: pass
            groups = []
            for sz, files in bysize.items():
                if sz == 0 or len(files) < 2: continue
                by_partial = {}
                for fp in files:
                    h = partial_hash(fp)
                    if h: by_partial.setdefault(h, []).append(fp)
                for fl in by_partial.values():
                    if len(fl) < 2: continue
                    by_full = {}
                    for fp in fl:
                        h = full_hash(fp)
                        if h: by_full.setdefault(h, []).append(fp)
                    for fl2 in by_full.values():
                        if len(fl2) > 1: groups.append(fl2)
            self.root.after(0, lambda: fill(groups))
        def fill(groups):
            dialog.title(f"Дубликаты: {sum(len(g)-1 for g in groups)} лишних")
            tree.delete(*tree.get_children())
            for gi, g in enumerate(groups):
                tree.insert("","end", iid=f"__grp{gi}", values=(f"=== {len(g)} шт ===","",""))
                for fp in g:
                    tree.insert("","end", iid=str(fp), values=(fp.name, human_size(fp.stat().st_size), str(fp.parent)))
            if not groups: tree.insert("","end", values=("Дубликаты не найдены","",""))
        threading.Thread(target=worker, daemon=True).start()

    def zip_selected(self):
        p = self.active_panel()
        if not p: return
        s = [x for x in p.get_selected_paths() if not x.startswith("__")]
        if not s: return
        name = ask_text(p.frame, "Архив ZIP", "Имя:", "archive.zip")
        if not name: return
        if not name.lower().endswith(".zip"): name += ".zip"
        zp = get_unique_destination(p.current_path / name)
        self.operations.zip(s, zp, p.frame)

    def unzip_selected(self):
        p = self.active_panel()
        if not p: return
        s = [x for x in p.get_selected_paths() if not x.startswith("__")]
        if len(s) != 1: messagebox.showinfo("", "Выбери один ZIP"); return
        src = Path(s[0])
        if src.suffix.lower() != ".zip": messagebox.showinfo("", "Только ZIP"); return
        dest = get_unique_destination(src.with_suffix(""))
        self.operations.unzip(src, dest, p.frame)


def main():
    root = tk.Tk()
    try: root.attributes("-alpha", 0.0)
    except Exception: pass
    app = ExplorerApp(root)
    fade_window(root, duration=400)
    root.mainloop()


if __name__ == "__main__":
    main()
