import os
import sys
import subprocess
import shutil
import zipfile
import threading
import datetime
import hashlib
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
from pathlib import Path

BG="#EAF6FF"; PANEL="#D7EDFF"; TOOLBAR="#C7E6FF"
BUTTON="#A7D8FF"; BUTTON_HOVER="#86C8FF"; BUTTON_PRESSED="#63B4FF"
ACCENT="#2E90FF"; ACCENT_HOVER="#1D7CEA"; ACCENT_PRESSED="#1468CF"
TEXT="#083A5D"; LIST_BG="#FBFEFF"; SELECT_BG="#C9E8FF"; BORDER="#9FD6FF"

IMAGE_EXTS={".png",".jpg",".jpeg",".gif",".bmp",".webp",".ico",".tif",".tiff"}
AUDIO_EXTS={".mp3",".wav",".flac",".aac",".ogg",".m4a",".wma",".opus"}
VIDEO_EXTS={".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm",".m4v",".mpg",".mpeg"}
ARCHIVE_EXTS={".zip",".rar",".7z",".tar",".gz",".bz2",".xz",".iso"}
EXEC_EXTS={".exe",".msi",".bat",".cmd",".ps1",".appx"}
DOCUMENT_EXTS={".doc",".docx",".odt",".rtf",".txt",".xlsx",".xls",".csv",".ppt",".pptx"}
PDF_EXTS={".pdf"}
CODE_EXTS={".py",".js",".html",".css",".json",".xml",".c",".cpp",".cs",".java",".php",".sh"}

def hex_to_rgb(h):
    h=str(h).lstrip("#")
    if len(h)==3: h="".join(c*2 for c in h)
    return tuple(int(h[i:i+2],16) for i in (0,2,4))
def rgb_to_hex(r): return "#%02x%02x%02x"%tuple(int(max(0,min(255,v))) for v in r)

def fade_window(win,duration=280,steps=16):
    try:
        win.attributes("-alpha",0.0)
        def step(i):
            win.attributes("-alpha",min(1.0,(i+1)/steps))
            if i+1<steps: win.after(int(duration/steps),lambda: step(i+1))
        win.after(0,lambda: step(0))
    except Exception: pass

def animate_widget_color(widget,to,attr="bg",steps=10,duration=180):
    try:
        c=hex_to_rgb(widget.cget(attr)); t=hex_to_rgb(to)
    except Exception:
        widget.configure(**{attr:to}); return
    def step(i):
        f=(i+1)/steps
        widget.configure(**{attr:rgb_to_hex(tuple(c[k]+(t[k]-c[k])*f for k in range(3)))})
        if i+1<steps: widget.after(int(duration/steps),lambda: step(i+1))
    step(0)

class ModernButton(tk.Canvas):
    def __init__(self,master,text,command=None,accent=False,height=32,padx=16,radius=9,**kw):
        bg=master.cget("bg")
        self.text=text; self.command=command; self.pad=padx
        self.fgcol="white" if accent else TEXT
        self.base=hex_to_rgb(ACCENT if accent else BUTTON)
        self.hover=hex_to_rgb(ACCENT_HOVER if accent else BUTTON_HOVER)
        self.press=hex_to_rgb(ACCENT_PRESSED if accent else BUTTON_PRESSED)
        self.cur=list(self.base); self.tgt=list(self.base); self._anim=None
        f=tkfont.Font(family="Segoe UI",size=9,weight="bold")
        w=int(f.measure(text))+padx*2
        super().__init__(master,width=w,height=height,bg=bg,highlightthickness=0,bd=0,cursor="hand2",**kw)
        self.w=w; self.h=height; self.r=radius
        self._shapes=[]; self._txt=None
        self._draw()
        self.bind("<Enter>",lambda e:self._go(self.hover))
        self.bind("<Leave>",lambda e:self._go(self.base))
        self.bind("<ButtonPress-1>",lambda e:(self._go(self.press),self.coords(self._txt,self.w/2,self.h/2+1)))
        self.bind("<ButtonRelease-1>",self._release)
    def set_text(self,t):
        self.text=t
        f=tkfont.Font(family="Segoe UI",size=9,weight="bold")
        self.w=int(f.measure(t))+self.pad*2
        self.configure(width=self.w)
        self._draw()
    def _draw(self):
        self.delete("all"); self._shapes=[]
        x0,y0,x1,y1,r=0,0,self.w,self.h,self.r
        col=rgb_to_hex(self.cur)
        self._shapes.append(self.create_rectangle(x0+r,y0,x1-r,y1,fill=col,outline=""))
        self._shapes.append(self.create_rectangle(x0,y0+r,x1,y1-r,fill=col,outline=""))
        for cx,cy in ((x0,y0),(x1-2*r,y0),(x0,y1-2*r),(x1-2*r,y1-2*r)):
            self._shapes.append(self.create_oval(cx,cy,cx+2*r,cy+2*r,fill=col,outline=""))
        self._txt=self.create_text(self.w/2,self.h/2,text=self.text,fill=self.fgcol,font=("Segoe UI",9,"bold"))
    def _go(self,rgb):
        self.tgt=list(rgb)
        if self._anim is None: self._tick()
    def _tick(self):
        done=True
        for i in range(3):
            d=self.tgt[i]-self.cur[i]
            if abs(d)>0.5: self.cur[i]+=d*0.35; done=False
            else: self.cur[i]=self.tgt[i]
        col=rgb_to_hex(self.cur)
        for s in self._shapes: self.itemconfigure(s,fill=col)
        if not done: self._anim=self.after(16,self._tick)
        else: self._anim=None
    def _release(self,e):
        self.coords(self._txt,self.w/2,self.h/2)
        if 0<=e.x<=self.w and 0<=e.y<=self.h:
            self._go(self.hover)
            if self.command: self.command()
        else: self._go(self.base)

def ask_text(parent,title,label,initial=""):
    dialog=tk.Toplevel(parent); dialog.title(title); dialog.configure(bg=BG)
    dialog.resizable(False,False); dialog.transient(parent); dialog.grab_set()
    w,h=460,190; parent.update_idletasks()
    x=parent.winfo_rootx()+(parent.winfo_width()-w)//2; y=parent.winfo_rooty()+(parent.winfo_height()-h)//2
    dialog.geometry(f"{w}x{h}+{max(x,0)}+{max(y,0)}")
    fade_window(dialog)
    result=None
    tk.Label(dialog,text=label,bg=BG,fg=TEXT,font=("Segoe UI",10,"bold")).pack(pady=(18,6),padx=20,anchor="w")
    entry=tk.Entry(dialog,font=("Segoe UI",11),bg="white",fg=TEXT,relief="solid",bd=1,highlightthickness=0)
    entry.pack(fill="x",padx=20,ipady=6); entry.insert(0,initial); entry.select_range(0,tk.END); entry.focus()
    def ok(e=None):
        nonlocal result; result=entry.get().strip(); dialog.destroy()
    def cancel(e=None): dialog.destroy()
    entry.bind("<Return>",ok); dialog.bind("<Escape>",cancel)
    b=tk.Frame(dialog,bg=BG); b.pack(pady=18)
    ModernButton(b,text="OK",command=ok,accent=True).pack(side="left",padx=6)
    ModernButton(b,text="Отмена",command=cancel).pack(side="left",padx=6)
    parent.wait_window(dialog); return result

def is_valid_filename(name):
    if not name or name in (".",".."): return False
    return not any(c in r'\/:*?"<>|' for c in name)

def get_icon(path):
    try:
        if path.is_dir(): return "📁"
        e=path.suffix.lower()
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
    size=float(size)
    for u in ["Б","КБ","МБ","ГБ","ТБ"]:
        if size<1024 or u=="ТБ":
            return f"{int(size)} {u}" if u=="Б" else f"{size:.1f} {u}"
        size/=1024

def get_drives():
    if os.name=="nt":
        try:
            import ctypes; b=ctypes.windll.kernel32.GetLogicalDrives(); d=[]
            for i in range(26):
                if b&(1<<i): d.append(f"{chr(ord('A')+i)}:\\")
            return d
        except Exception: return ["C:\\"]
    return ["/"]

def get_quick_links():
    home=Path.home(); windir=Path(os.environ.get("WINDIR","C:\\Windows"))
    items=[("Рабочий стол",home/"Desktop"),("Документы",home/"Documents"),("Загрузки",home/"Downloads"),
        ("Изображения",home/"Pictures"),("Музыка",home/"Music"),("Видео",home/"Videos")]
    items+=[("Папка Windows",windir),("System32",windir/"System32"),("Sysnative (реальный System32)",windir/"Sysnative"),
        ("SysWOW64",windir/"SysWOW64"),("Program Files",Path(os.environ.get("ProgramFiles","C:\\Program Files"))),
        ("Program Files (x86)",Path(os.environ.get("ProgramFiles(x86)","C:\\Program Files (x86)"))),
        ("ProgramData",Path(os.environ.get("ProgramData","C:\\ProgramData")))]
    res=[]
    for n,p in items:
        try:
            p=Path(p)
            if p.exists(): res.append((n,p))
        except Exception: pass
    return res

def open_file(path):
    try:
        if os.name=="nt": os.startfile(str(path))
        else: subprocess.Popen(["xdg-open",str(path)])
    except Exception as e: messagebox.showerror("Ошибка",f"Не удалось открыть файл:\n{path}\n\n{e}")

def open_notepad(path):
    try: subprocess.Popen(["notepad.exe",str(path)])
    except Exception as e: messagebox.showerror("Ошибка",f"Не удалось открыть Блокнот:\n{e}")

def is_inside(child,parent):
    try: child.relative_to(parent); return True
    except ValueError: return False

def is_hidden(path):
    try:
        if path.name.startswith("."): return True
        if os.name=="nt":
            import stat as sm
            return bool(path.stat().st_file_attributes & sm.FILE_ATTRIBUTE_HIDDEN)
    except Exception: pass
    return False

def get_unique_destination(dest):
    if not dest.exists(): return dest
    base=dest.stem if dest.is_file() else dest.name
    ext=dest.suffix if dest.is_file() else ""
    c=1
    while True:
        nd=dest.parent/f"{base} ({c}){ext}"
        if not nd.exists(): return nd
        c+=1

def is_admin():
    if os.name!="nt": return False
    try:
        import ctypes; return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False

def relaunch_as_admin():
    if os.name!="nt": return False
    try:
        import ctypes
        r=ctypes.windll.shell32.ShellExecuteW(None,"runas",sys.executable,f'"{os.path.abspath(sys.argv[0])}"',None,1)
        return r>32
    except Exception: return False

def send_to_recycle_bin(path):
    if os.name!="nt": return False
    try:
        import ctypes; from ctypes import wintypes
        class S(ctypes.Structure):
            _fields_=[("hwnd",wintypes.HWND),("wFunc",wintypes.UINT),("pFrom",ctypes.c_void_p),
                ("pTo",ctypes.c_void_p),("fFlags",ctypes.c_ushort),("fAnyOperationsAborted",wintypes.BOOL),
                ("hNameMappings",ctypes.c_void_p),("lpszProgressTitle",wintypes.LPCWSTR)]
        buf=ctypes.create_unicode_buffer(str(path)+"\0")
        op=S(); op.hwnd=None; op.wFunc=3; op.pFrom=ctypes.cast(buf,ctypes.c_void_p); op.pTo=None
        op.fFlags=0x0040|0x0010|0x0004|0x0400; op.fAnyOperationsAborted=False; op.hNameMappings=None; op.lpszProgressTitle=None
        return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))==0
    except Exception: return False

def delete_path(path):
    if send_to_recycle_bin(path): return
    if path.is_symlink(): path.unlink()
    elif path.is_dir(): shutil.rmtree(path)
    else: path.unlink()

def hash_file(fp):
    h=hashlib.md5()
    with open(fp,"rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def show_properties_dialog(parent,paths):
    dialog=tk.Toplevel(parent); dialog.title("Свойства"); dialog.configure(bg=BG)
    dialog.resizable(False,False); dialog.transient(parent); dialog.grab_set()
    fade_window(dialog)
    lines=[]
    if len(paths)==1:
        p=paths[0]
        lines.append(f"Имя: {p.name}")
        lines.append(f"Тип: {'Папка' if p.is_dir() else 'Файл'}")
        try:
            st=p.stat()
            if p.is_file(): lines.append(f"Размер: {human_size(st.st_size)}")
            else:
                total=0
                for r,d,fs in os.walk(p):
                    for f in fs:
                        try: total+=(Path(r)/f).stat().st_size
                        except Exception: pass
                lines.append(f"Размер папки: {human_size(total)}")
            lines.append(f"Изменён: {datetime.datetime.fromtimestamp(st.st_mtime):%d.%m.%Y %H:%M}")
            lines.append(f"Создан: {datetime.datetime.fromtimestamp(st.st_ctime):%d.%m.%Y %H:%M}")
            if os.name=="nt":
                import stat as sm
                lines.append(f"Скрытый: {'Да' if st.st_file_attributes & sm.FILE_ATTRIBUTE_HIDDEN else 'Нет'}")
        except Exception: lines.append("Нет доступа к сведениям")
        lines.append(f"Путь: {p}")
    else:
        total=0; cnt=0
        for p in paths:
            try:
                if p.is_file(): total+=p.stat().st_size; cnt+=1
            except Exception: pass
        lines.append(f"Элементов: {len(paths)}")
        lines.append(f"Файлов: {cnt}")
        lines.append(f"Общий размер файлов: {human_size(total)}")
    for line in lines:
        tk.Label(dialog,text=line,bg=BG,fg=TEXT,anchor="w",font=("Segoe UI",10),wraplength=560,justify="left").pack(fill="x",padx=20,pady=2)
    ModernButton(dialog,text="Закрыть",command=dialog.destroy,accent=True).pack(pady=14)

def apply_style(root):
    root.configure(bg=BG); style=ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass
    style.configure("TNotebook",background=BG,bordercolor=BORDER)
    style.configure("TNotebook.Tab",background=BUTTON,foreground=TEXT,padding=(12,6),font=("Segoe UI",9,"bold"))
    style.map("TNotebook.Tab",background=[("selected",ACCENT)],foreground=[("selected","white")])
    style.configure("Treeview",background=LIST_BG,fieldbackground=LIST_BG,foreground="#123249",rowheight=30,bordercolor=BORDER,font=("Segoe UI",10))
    style.configure("Treeview.Heading",background=BUTTON,foreground=TEXT,bordercolor=BORDER,relief="flat",padding=5,font=("Segoe UI",9,"bold"))
    style.map("Treeview",background=[("selected",SELECT_BG)],foreground=[("selected",TEXT)])
    style.configure("Vertical.TScrollbar",background=BUTTON,troughcolor=BG,bordercolor=BORDER,arrowcolor=TEXT)
    style.map("Vertical.TScrollbar",background=[("active",BUTTON_HOVER),("pressed",BUTTON_PRESSED)])

class FilePanel:
    def __init__(self,parent,app,side):
        self.app=app; self.side=side
        try: self.current_path=Path.home()
        except Exception: self.current_path=Path.cwd()
        self.history=[]; self.history_index=-1; self.filter_text=""
        self.sort_key="name"; self.sort_reverse=False
        self.frame=tk.Frame(parent,bg=BG,padx=4,pady=4)
        self.header=tk.Label(self.frame,text="",bg=PANEL,fg=TEXT,anchor="w",font=("Segoe UI",9,"bold"),padx=6,pady=5)
        self.header.pack(fill="x")
        inner=tk.Frame(self.frame,bg=BG); inner.pack(fill="both",expand=True)
        self.tree=ttk.Treeview(inner,columns=("name","type","size"),show="headings",selectmode="extended")
        self.tree.heading("name",text="Имя",command=lambda:self.set_sort("name"))
        self.tree.heading("type",text="Тип",command=lambda:self.set_sort("type"))
        self.tree.heading("size",text="Размер",command=lambda:self.set_sort("size"))
        self.tree.column("name",width=320,anchor="w",stretch=True)
        self.tree.column("type",width=70,anchor="center",stretch=False)
        self.tree.column("size",width=90,anchor="e",stretch=False)
        self.tree.tag_configure("folder",foreground="#0B67B2")
        self.tree.tag_configure("file",foreground="#173245")
        sb=ttk.Scrollbar(inner,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        self.tree.bind("<Double-1>",lambda e:self.open_selected())
        self.tree.bind("<Return>",lambda e:self.open_selected())
        self.tree.bind("<Button-1>",lambda e:self.app.set_active_panel(self))
        self.tree.bind("<FocusIn>",lambda e:self.app.set_active_panel(self))
        self.tree.bind("<F2>",lambda e:self.rename_selected())
        self.tree.bind("<F4>",lambda e:self.app.open_notepad_selected())
        self.tree.bind("<Delete>",lambda e:self.delete_selected())
        self.tree.bind("<Button-3>",lambda e:self.app.show_tree_menu(e,self))
        self.tree.bind("<<TreeviewSelect>>",lambda e:self.app.update_status())

    def set_active(self,active):
        animate_widget_color(self.header,ACCENT if active else PANEL,"bg")
        animate_widget_color(self.header,"white" if active else TEXT,"fg")

    def set_sort(self,key):
        if self.sort_key==key: self.sort_reverse=not self.sort_reverse
        else: self.sort_key=key; self.sort_reverse=False
        self.load_items(); self.app.update_status()

    def navigate(self,path,add_history=True):
        try: path=Path(path).resolve()
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось открыть путь:\n{path}\n\n{e}"); return
        if not path.exists(): messagebox.showwarning("Не найдено",f"Папка не найдена:\n{path}"); return
        if path.is_file(): open_file(path); return
        if add_history:
            if self.history_index<0 or Path(self.history[self.history_index])!=path:
                self.history=self.history[:self.history_index+1]; self.history.append(str(path)); self.history_index+=1
        self.current_path=path; self.header.config(text=str(path))
        self.load_items(); self.app.on_panel_navigated(self)

    def _sort_key(self,p):
        try:
            if self.sort_key=="size": return p.stat().st_size if p.is_file() else -1
            if self.sort_key=="type": return p.suffix.lower()
        except Exception: pass
        return p.name.lower()

    def load_items(self):
        self.tree.delete(*self.tree.get_children())
        show_hidden=self.app.show_hidden.get()
        deep=self.app.deep_search.get()
        ft=self.filter_text.lower().strip()
        if ft and deep:
            self.tree.insert("","end",iid="__searching__",values=("🔎 Ищем... (это может занять время)","",""))
            threading.Thread(target=self._deep_search,args=(ft,str(self.current_path)),daemon=True).start()
            return
        try: entries=list(self.current_path.iterdir())
        except PermissionError:
            self.tree.insert("","end",iid="__no_access__",values=("🔒 Нет доступа. Запусти программу от имени администратора (кнопка «Админ»).","","")); return
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось прочитать папку:\n{self.current_path}\n\n{e}"); return
        folders=[]; files=[]
        for item in entries:
            try:
                if not show_hidden and is_hidden(item): continue
                if ft and ft not in item.name.lower(): continue
                (folders if item.is_dir() else files).append(item)
            except Exception: pass
        folders.sort(key=self._sort_key,reverse=self.sort_reverse)
        files.sort(key=self._sort_key,reverse=self.sort_reverse)
        folder_iids=[]
        for f in folders:
            iid=str(f); folder_iids.append(iid)
            self.tree.insert("","end",iid=iid,values=(f"{get_icon(f)} {f.name}","Папка","…"),tags=("folder",))
        for f in files:
            try: size=human_size(f.stat().st_size)
            except Exception: size="?"
            self.tree.insert("","end",iid=str(f),values=(f"{get_icon(f)} {f.name}","Файл",size),tags=("file",))
        if folder_iids and not ft:
            threading.Thread(target=self._size_worker,args=(str(self.current_path),folder_iids[:300]),daemon=True).start()

    def _size_worker(self,start,folder_iids):
        for iid in folder_iids:
            p=Path(iid); total=0
            try:
                for r,d,fs in os.walk(p):
                    for f in fs:
                        try: total+=(Path(r)/f).stat().st_size
                        except Exception: pass
            except Exception: pass
            self.app.root.after(0,lambda i=iid,t=total,s=start:self._set_size(i,t,s))

    def _set_size(self,iid,total,start):
        if str(self.current_path)!=start: return
        if self.tree.exists(iid): self.tree.set(iid,"size",human_size(total))

    def _deep_search(self,ft,start):
        results=[]; limit=1000
        try:
            for root,dirs,files in os.walk(start):
                for n in dirs+files:
                    if ft in n.lower():
                        results.append(str(Path(root)/n))
                        if len(results)>=limit:
                            self.app.root.after(0,lambda r=results:self._apply_results(r,start,True)); return
        except Exception: pass
        self.app.root.after(0,lambda r=results:self._apply_results(r,start,False))

    def _apply_results(self,results,start,truncated):
        if str(self.current_path)!=start: return
        self.tree.delete(*self.tree.get_children())
        for r in results:
            p=Path(r)
            try:
                if p.is_dir():
                    self.tree.insert("","end",iid=r,values=(f"📁 {p.name}  ({p.parent})","Папка",""),tags=("folder",))
                else:
                    self.tree.insert("","end",iid=r,values=(f"{get_icon(p)} {p.name}  ({p.parent})","Файл",human_size(p.stat().st_size)),tags=("file",))
            except Exception: pass
        if truncated:
            self.tree.insert("","end",values=("… показаны первые 1000 совпадений","",""))
        self.app.update_status()

    def set_filter(self,text):
        self.filter_text=text; self.load_items(); self.app.update_status()

    def refresh(self): self.navigate(self.current_path,add_history=False)

    def go_back(self):
        if self.history_index>0:
            self.history_index-=1; self.navigate(self.history[self.history_index],add_history=False)

    def go_up(self):
        p=self.current_path.parent
        if p and p!=self.current_path: self.navigate(p)

    def get_selected_paths(self): return list(self.tree.selection())

    def select_all(self): self.tree.selection_set(self.tree.get_children())

    def open_selected(self):
        s=self.tree.selection()
        if not s: return
        self.tree.focus(s[0]); iid=self.tree.focus()
        if not iid or iid in ("__no_access__","__searching__"):
            if iid=="__no_access__":
                messagebox.showinfo("Нет доступа","Эта папка защищена Windows.\nНажми кнопку «Админ» сверху.")
            return
        p=Path(iid)
        try:
            if p.is_dir(): self.navigate(p)
            else: open_file(p)
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось открыть элемент:\n{p}\n\n{e}")

    def create_folder(self):
        name=ask_text(self.frame,"Новая папка","Имя новой папки:","")
        if not name: return
        if not is_valid_filename(name):
            messagebox.showwarning("Неподходящее имя",'Имя не может содержать символы:\n\n\\ / : * ? " < > |'); return
        np=self.current_path/name
        if np.exists(): messagebox.showwarning("Уже существует",f"Уже существует:\n{np.name}"); return
        try: np.mkdir()
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось создать папку:\n{np}\n\n{e}"); return
        self.refresh()
        if self.tree.exists(str(np)): self.tree.selection_set(str(np)); self.tree.focus(str(np)); self.tree.see(str(np))

    def create_text_file(self):
        name=ask_text(self.frame,"Новый текстовый файл","Имя файла:","note.txt")
        if not name: return
        if "." not in name: name+=".txt"
        if not is_valid_filename(name):
            messagebox.showwarning("Неподходящее имя",'Имя не может содержать символы:\n\n\\ / : * ? " < > |'); return
        np=self.current_path/name
        if np.exists(): messagebox.showwarning("Уже существует",f"Уже существует:\n{np.name}"); return
        try: np.write_text("",encoding="utf-8")
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось создать файл:\n{np}\n\n{e}"); return
        self.refresh()
        if self.tree.exists(str(np)): self.tree.selection_set(str(np)); self.tree.focus(str(np)); self.tree.see(str(np))

    def rename_selected(self):
        s=[x for x in self.tree.selection() if x not in ("__no_access__","__searching__")]
        if len(s)!=1: messagebox.showinfo("Переименовать","Выбери один файл или одну папку.\n\nДля нескольких используй «Групп. переименование»."); return
        p=Path(s[0])
        if not p.exists(): self.refresh(); return
        nn=ask_text(self.frame,"Переименовать",f"Новое имя для '{p.name}':",p.name)
        if not nn or nn==p.name: return
        if not is_valid_filename(nn):
            messagebox.showwarning("Неподходящее имя",'Имя не может содержать символы:\n\n\\ / : * ? " < > |'); return
        np=p.with_name(nn)
        if np.exists(): messagebox.showwarning("Уже существует",f"Уже существует:\n{nn}"); return
        try: p.rename(np)
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось переименовать:\n{p}\n\n{e}"); return
        self.refresh()
        if self.tree.exists(str(np)): self.tree.selection_set(str(np)); self.tree.focus(str(np)); self.tree.see(str(np))

    def delete_selected(self):
        s=[x for x in self.tree.selection() if x not in ("__no_access__","__searching__")]
        if not s: messagebox.showinfo("Удалить","Сначала выбери файлы или папки."); return
        if not messagebox.askyesno("Удалить",f"Удалить выбранные элементы?\n\nКоличество: {len(s)}\n\nПо возможности они будут удалены в корзину."): return
        d=0; er=0
        for item in s:
            p=Path(item)
            try:
                if not p.exists(): continue
                delete_path(p); d+=1
            except Exception as e:
                er+=1; messagebox.showerror("Ошибка",f"Не удалось удалить:\n{p}\n\n{e}")
        if not self.current_path.exists(): self.current_path=self.current_path.parent
        self.refresh()
        messagebox.showinfo("Удаление завершено",f"Удалено: {d}\nОшибок: {er}")

class DualView:
    def __init__(self,parent,app):
        self.app=app; self.frame=tk.Frame(parent,bg=BG)
        self.left=FilePanel(self.frame,app,"Левая панель")
        self.right=FilePanel(self.frame,app,"Правая панель")
        self.sep=tk.Frame(self.frame,width=4,bg=BORDER)
        self.left.frame.pack(side="left",fill="both",expand=True)
        self.sep.pack(side="left",fill="y")
        self.right.frame.pack(side="left",fill="both",expand=True)
        self.active=self.left; self.single=False
    def initialize(self):
        try: home=Path.home()
        except Exception: home=Path.cwd()
        self.left.navigate(home,add_history=False); self.right.navigate(home,add_history=False)
        self.set_active(self.left,update_app=False)
    def set_active(self,panel,update_app=True):
        self.active=panel
        self.left.set_active(panel is self.left); self.right.set_active(panel is self.right)
        if update_app: self.app.update_ui()
    def set_single(self,single):
        self.single=single
        if single:
            self.sep.pack_forget()
            self.right.frame.pack_forget()
            self.active=self.left
            self.left.set_active(True); self.right.set_active(False)
        else:
            self.sep.pack(side="left",fill="y")
            self.right.frame.pack(side="left",fill="both",expand=True)
        self.app.update_ui()

class ExplorerApp:
    def __init__(self,root):
        self.root=root
        root.title("Мой проводник — две панели, вкладки, поиск")
        root.geometry("1450x760"); root.minsize(1100,620)
        apply_style(root)
        self.clipboard=None; self.tab_counter=0; self.admin=is_admin()
        self.path_var=tk.StringVar(); self.search_var=tk.StringVar()
        self.deep_search=tk.BooleanVar(value=False)
        self.show_hidden=tk.BooleanVar(value=True)
        self._panel_single=None
        self.create_interface(); self.bind_shortcuts(); self.new_tab()

    def create_interface(self):
        top=tk.Frame(self.root,bg=TOOLBAR,padx=6,pady=6); top.pack(fill="x")
        ModernButton(top,text="← Назад",command=self.go_back).pack(side="left",padx=(0,4))
        ModernButton(top,text="↑ Вверх",command=self.go_up).pack(side="left",padx=4)
        ModernButton(top,text="⟳ Обновить",command=self.refresh).pack(side="left",padx=4)
        self.disks_button=ModernButton(top,text="Диски",command=self.show_drives_menu); self.disks_button.pack(side="left",padx=4)
        self.panel_button=ModernButton(top,text="2 панели",command=self.toggle_panels); self.panel_button.pack(side="left",padx=4)
        ModernButton(top,text="Админ ✓" if self.admin else "Админ",command=self.admin_click,accent=self.admin).pack(side="left",padx=4)
        self.path_entry=tk.Entry(top,textvariable=self.path_var,state="readonly",readonlybackground="white",bg="white",fg=TEXT,relief="flat",font=("Segoe UI",10),highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER)
        self.path_entry.pack(side="left",fill="x",expand=True,padx=8)
        ModernButton(top,text="Проводник",command=self.open_in_explorer,accent=True).pack(side="left",padx=(4,0))

        act=tk.Frame(self.root,bg=PANEL,padx=6,pady=5); act.pack(fill="x")
        ModernButton(act,text="+ Вкладка",command=self.new_tab).pack(side="left",padx=(0,4))
        ModernButton(act,text="× Вкладка",command=self.close_tab).pack(side="left",padx=4)
        ModernButton(act,text="Новая папка",command=self.new_folder).pack(side="left",padx=4)
        ModernButton(act,text="Текстовый файл",command=self.new_text_file).pack(side="left",padx=4)
        ModernButton(act,text="Вырезать",command=self.cut_selected).pack(side="left",padx=4)
        ModernButton(act,text="Копировать",command=self.copy_selected).pack(side="left",padx=4)
        ModernButton(act,text="Вставить",command=self.paste_items).pack(side="left",padx=4)
        ModernButton(act,text="Удалить",command=self.delete_selected).pack(side="left",padx=4)
        ModernButton(act,text="Переименовать",command=self.rename_selected).pack(side="left",padx=4)
        ModernButton(act,text="Групп. переименование",command=self.bulk_rename).pack(side="left",padx=4)
        ModernButton(act,text="Дубликаты",command=self.find_duplicates).pack(side="left",padx=4)
        ModernButton(act,text="Выделить всё",command=self.select_all).pack(side="left",padx=4)

        sb=tk.Frame(self.root,bg=TOOLBAR,padx=6,pady=5); sb.pack(fill="x")
        tk.Label(sb,text="Поиск:",bg=TOOLBAR,fg=TEXT,font=("Segoe UI",10,"bold")).pack(side="left",padx=(0,6))
        self.search_entry=tk.Entry(sb,textvariable=self.search_var,bg="white",fg=TEXT,relief="flat",font=("Segoe UI",10),highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER)
        self.search_entry.pack(side="left",fill="x",expand=True,padx=6,ipady=4)
        self.search_entry.bind("<KeyRelease>",lambda e:self.on_search_changed())
        ModernButton(sb,text="Очистить",command=self.clear_search).pack(side="left",padx=(6,6))
        tk.Checkbutton(sb,text="включая подпапки",variable=self.deep_search,bg=TOOLBAR,fg=TEXT,activebackground=TOOLBAR,selectcolor="white",font=("Segoe UI",9,"bold"),command=self.on_search_options).pack(side="left",padx=4)
        tk.Checkbutton(sb,text="скрытые",variable=self.show_hidden,bg=TOOLBAR,fg=TEXT,activebackground=TOOLBAR,selectcolor="white",font=("Segoe UI",9,"bold"),command=self.on_search_options).pack(side="left",padx=4)

        self.status=tk.Label(self.root,text="",bg=TOOLBAR,fg=TEXT,anchor="w",font=("Segoe UI",9),padx=10,pady=6)
        self.status.pack(side="bottom",fill="x")
        self.notebook=ttk.Notebook(self.root); self.notebook.pack(fill="both",expand=True,padx=6,pady=6)
        self.notebook.bind("<<NotebookTabChanged>>",lambda e:self.update_ui())
        self.build_drives_menu(); self.build_context_menu()

    def build_drives_menu(self):
        self.drives_menu=tk.Menu(self.root,tearoff=0,bg="#F4FBFF",fg=TEXT,activebackground=SELECT_BG,activeforeground=TEXT,font=("Segoe UI",10),relief="flat",bd=0)
        for n,p in get_quick_links(): self.drives_menu.add_command(label=n,command=lambda x=p:self.navigate_active(x))
        self.drives_menu.add_separator()
        for d in get_drives(): self.drives_menu.add_command(label=d,command=lambda x=d:self.navigate_active(x))

    def build_context_menu(self):
        m=tk.Menu(self.root,tearoff=0,bg="#F4FBFF",fg=TEXT,activebackground=SELECT_BG,activeforeground=TEXT,font=("Segoe UI",10),relief="flat",bd=0)
        m.add_command(label="Открыть",command=self.open_selected)
        m.add_command(label="Открыть в Блокноте",command=self.open_notepad_selected); m.add_separator()
        m.add_command(label="Вырезать",command=self.cut_selected)
        m.add_command(label="Копировать",command=self.copy_selected)
        m.add_command(label="Вставить",command=self.paste_items); m.add_separator()
        m.add_command(label="Новая папка",command=self.new_folder)
        m.add_command(label="Новый текстовый файл",command=self.new_text_file)
        m.add_command(label="Переименовать",command=self.rename_selected)
        m.add_command(label="Групп. переименование",command=self.bulk_rename)
        m.add_command(label="Удалить",command=self.delete_selected); m.add_separator()
        m.add_command(label="Архивировать в ZIP",command=self.zip_selected)
        m.add_command(label="Распаковать ZIP",command=self.unzip_selected)
        m.add_command(label="Найти дубликаты",command=self.find_duplicates); m.add_separator()
        m.add_command(label="Копировать путь",command=self.copy_path)
        m.add_command(label="Свойства",command=self.show_properties)
        m.add_command(label="Командная строка здесь",command=self.open_cmd_here); m.add_separator()
        m.add_command(label="Обновить",command=self.refresh)
        self.context_menu=m

    def bind_shortcuts(self):
        self.root.bind("<Control-t>",lambda e:self.new_tab())
        self.root.bind("<Control-w>",lambda e:self.close_tab())
        self.root.bind("<Control-n>",lambda e:self.new_folder())
        self.root.bind("<Control-p>",lambda e:self.toggle_panels())
        self.root.bind("<F5>",lambda e:self.refresh())
        self.root.bind("<F4>",lambda e:self.open_notepad_selected())
        self.root.bind("<Alt-Return>",lambda e:self.show_properties())
        self.root.bind("<Control-Shift-C>",lambda e:self.copy_path())
        self.root.bind("<Control-x>",lambda e:self.on_ctrl_x())
        self.root.bind("<Control-c>",lambda e:self.on_ctrl_c())
        self.root.bind("<Control-v>",lambda e:self.on_ctrl_v())
        self.root.bind("<Control-a>",lambda e:self.on_ctrl_a())

    def entry_has_focus(self):
        try: return isinstance(self.root.focus_get(),tk.Entry)
        except Exception: return False
    def on_ctrl_x(self):
        if not self.entry_has_focus(): self.cut_selected()
    def on_ctrl_c(self):
        if not self.entry_has_focus(): self.copy_selected()
    def on_ctrl_v(self):
        if not self.entry_has_focus(): self.paste_items()
    def on_ctrl_a(self):
        if not self.entry_has_focus(): self.select_all()

    def toggle_panels(self):
        d=self.current_dual()
        if not d: return
        d.set_single(not d.single)

    def admin_click(self):
        if self.admin: messagebox.showinfo("Администратор","Программа уже запущена с правами администратора."); return
        if not messagebox.askyesno("Администратор","Перезапустить программу от имени администратора?\n\nПоявится окно Windows — нажми «Да»."): return
        if relaunch_as_admin(): self.root.destroy()
        else: messagebox.showwarning("Администратор","Не удалось запустить от имени администратора.")

    def current_dual(self):
        s=self.notebook.select()
        if not s: return None
        return getattr(self.root.nametowidget(s),"dual_view",None)
    def active_panel(self):
        d=self.current_dual(); return d.active if d else None
    def set_active_panel(self,panel):
        d=self.current_dual()
        if d and panel in (d.left,d.right): d.set_active(panel,update_app=False)
        self.update_ui()

    def update_ui(self):
        d=self.current_dual()
        state=bool(d and d.single)
        if self._panel_single!=state:
            self._panel_single=state
            if hasattr(self,"panel_button"): self.panel_button.set_text("1 панель" if state else "2 панели")
        if d: d.set_active(d.active,update_app=False)
        p=self.active_panel()
        if p: self.path_var.set(str(p.current_path)); self.search_var.set(p.filter_text)
        else: self.path_var.set(""); self.search_var.set("")
        self.update_status()

    def update_status(self):
        p=self.active_panel()
        if not p: self.status.config(text=""); return
        count=len(p.tree.get_children())
        clip=""
        if self.clipboard:
            a,i=self.clipboard
            clip=f" | {'Вырезано' if a=='move' else 'Скопировано'}: {len(i)}"
        sel=""
        s=[x for x in p.tree.selection() if x not in ("__no_access__","__searching__")]
        if s:
            total=0
            for x in s:
                try:
                    pp=Path(x)
                    if pp.is_file(): total+=pp.stat().st_size
                except Exception: pass
            sel=f" | Выбрано: {len(s)} ({human_size(total)})"
        mode="⚠ Админ" if self.admin else "Обычный режим"
        self.status.config(text=f"{mode} | {p.side} | {p.current_path} | Элементов: {count}{sel}{clip}")

    def on_panel_navigated(self,panel):
        if panel is self.active_panel():
            self.path_var.set(str(panel.current_path)); self.search_var.set(panel.filter_text)
        self.update_status()

    def on_search_changed(self):
        p=self.active_panel()
        if p: p.set_filter(self.search_var.get())
    def on_search_options(self):
        p=self.active_panel()
        if p: p.load_items(); self.update_status()
    def clear_search(self):
        self.search_var.set("")
        p=self.active_panel()
        if p: p.set_filter("")

    def new_tab(self):
        self.tab_counter+=1
        d=DualView(self.notebook,self); d.frame.dual_view=d
        self.notebook.add(d.frame,text=f"Вкладка {self.tab_counter}")
        self.notebook.select(d.frame); d.initialize(); self.update_ui()
    def close_tab(self):
        if self.notebook.index("end")<=1: return
        c=self.notebook.select()
        if not c: return
        w=self.root.nametowidget(c); self.notebook.forget(c)
        try: w.destroy()
        except Exception: pass
        self.update_ui()

    def show_drives_menu(self):
        try: self.drives_menu.tk_popup(self.disks_button.winfo_rootx(),self.disks_button.winfo_rooty()+self.disks_button.winfo_height())
        finally: self.drives_menu.grab_release()
    def show_tree_menu(self,event,panel):
        self.set_active_panel(panel)
        item=panel.tree.identify_row(event.y)
        if item and item not in ("__no_access__","__searching__"):
            if item not in panel.tree.selection(): panel.tree.selection_set(item)
            panel.tree.focus(item)
        try: self.context_menu.tk_popup(event.x_root,event.y_root)
        finally: self.context_menu.grab_release()

    def navigate_active(self,path):
        p=self.active_panel()
        if p: p.navigate(path)
    def go_back(self):
        p=self.active_panel()
        if p: p.go_back()
    def go_up(self):
        p=self.active_panel()
        if p: p.go_up()
    def refresh(self):
        p=self.active_panel()
        if p: p.refresh()
    def open_in_explorer(self):
        p=self.active_panel()
        if not p: return
        try:
            if os.name=="nt": os.startfile(str(p.current_path))
            else: subprocess.Popen(["xdg-open",str(p.current_path)])
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось открыть Проводник:\n{p.current_path}\n\n{e}")
    def new_folder(self):
        p=self.active_panel()
        if p: p.create_folder()
    def new_text_file(self):
        p=self.active_panel()
        if p: p.create_text_file()
    def rename_selected(self):
        p=self.active_panel()
        if p: p.rename_selected()
    def delete_selected(self):
        p=self.active_panel()
        if p: p.delete_selected()
    def select_all(self):
        p=self.active_panel()
        if p: p.select_all()
    def open_selected(self):
        p=self.active_panel()
        if p: p.open_selected()
    def open_notepad_selected(self):
        p=self.active_panel()
        if not p: return
        s=[x for x in p.get_selected_paths() if x not in ("__no_access__","__searching__")]
        if not s: messagebox.showinfo("Блокнот","Сначала выбери файл."); return
        for x in s:
            pp=Path(x)
            if pp.is_file(): open_notepad(pp)
    def cut_selected(self): self.set_clipboard("move")
    def copy_selected(self): self.set_clipboard("copy")
    def set_clipboard(self,action):
        p=self.active_panel()
        if not p: return
        s=[x for x in p.get_selected_paths() if x not in ("__no_access__","__searching__")]
        if not s: messagebox.showinfo("Нет выбора","Сначала выбери файлы или папки."); return
        self.clipboard=(action,s); self.update_status()

    def copy_path(self):
        p=self.active_panel()
        if not p: return
        s=[x for x in p.get_selected_paths() if x not in ("__no_access__","__searching__")]
        text="\n".join(s) if s else str(p.current_path)
        self.root.clipboard_clear(); self.root.clipboard_append(text)
        self.status.config(text="Скопирован путь в буфер обмена.")

    def show_properties(self):
        p=self.active_panel()
        if not p: return
        s=[x for x in p.get_selected_paths() if x not in ("__no_access__","__searching__")]
        paths=[Path(x) for x in s] if s else [p.current_path]
        show_properties_dialog(self.root,paths)

    def open_cmd_here(self):
        p=self.active_panel()
        if not p: return
        try: subprocess.Popen(["cmd","/k",f'cd /d "{p.current_path}"'],cwd=str(p.current_path))
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось открыть командную строку:\n{e}")

    def bulk_rename(self):
        p=self.active_panel()
        if not p: return
        sel=[Path(x) for x in p.get_selected_paths() if x not in ("__no_access__","__searching__")]
        if not sel: messagebox.showinfo("Групп. переименование","Сначала выдели файлы или папки (можно несколько через Ctrl)."); return
        dialog=tk.Toplevel(self.root); dialog.title(f"Массовое переименование ({len(sel)})"); dialog.configure(bg=BG)
        dialog.transient(self.root); dialog.grab_set(); dialog.geometry("640x520")
        fade_window(dialog)
        f1=tk.Frame(dialog,bg=BG); f1.pack(fill="x",padx=16,pady=8)
        tk.Label(f1,text="Найти:",bg=BG,fg=TEXT,font=("Segoe UI",10,"bold")).pack(side="left")
        find_var=tk.StringVar(); tk.Entry(f1,textvariable=find_var,bg="white",fg=TEXT,relief="solid",bd=1,width=16).pack(side="left",padx=4)
        tk.Label(f1,text="Заменить на:",bg=BG,fg=TEXT,font=("Segoe UI",10,"bold")).pack(side="left")
        repl_var=tk.StringVar(); tk.Entry(f1,textvariable=repl_var,bg="white",fg=TEXT,relief="solid",bd=1,width=16).pack(side="left",padx=4)
        f2=tk.Frame(dialog,bg=BG); f2.pack(fill="x",padx=16)
        num_var=tk.BooleanVar(); tk.Checkbutton(f2,text="Добавить номер",variable=num_var,bg=BG,fg=TEXT,selectcolor="white",activebackground=BG,font=("Segoe UI",10)).pack(side="left")
        start_var=tk.StringVar(value="1"); tk.Entry(f2,textvariable=start_var,bg="white",fg=TEXT,relief="solid",bd=1,width=6).pack(side="left",padx=4)
        tk.Label(f2,text="(с какого числа)",bg=BG,fg=TEXT,font=("Segoe UI",9)).pack(side="left")
        date_var=tk.BooleanVar(); tk.Checkbutton(f2,text="Добавить дату",variable=date_var,bg=BG,fg=TEXT,selectcolor="white",activebackground=BG,font=("Segoe UI",10)).pack(side="left",padx=(16,0))
        tk.Label(dialog,text="Предпросмотр:",bg=BG,fg=TEXT,font=("Segoe UI",10,"bold")).pack(anchor="w",padx=16,pady=(8,2))
        prev=tk.Text(dialog,bg="#FBFEFF",fg="#123249",font=("Consolas",10),relief="solid",bd=1)
        prev.pack(fill="both",expand=True,padx=16)
        def build():
            res=[]
            try: st=int(start_var.get())
            except Exception: st=1
            f=find_var.get()
            for i,pp in enumerate(sel):
                base=pp.stem if pp.is_file() else pp.name
                ext=pp.suffix if pp.is_file() else ""
                name=base
                if f: name=name.replace(f,repl_var.get())
                if date_var.get(): name+=f" {datetime.date.today():%Y-%m-%d}"
                if num_var.get(): name+=f"_{st+i}"
                res.append((pp,name+ext))
            return res
        def update(*a):
            prev.delete("1.0","end")
            for pp,new in build():
                prev.insert("end",f"{pp.name}  ->  {new}\n")
        for v in (find_var,repl_var,start_var): v.trace_add("write",update)
        num_var.trace_add("write",update); date_var.trace_add("write",update)
        def apply():
            done=0; err=0
            for pp,new in build():
                if not is_valid_filename(new): err+=1; continue
                np=pp.with_name(new)
                if np.exists(): err+=1; continue
                try: pp.rename(np); done+=1
                except Exception: err+=1
            dialog.destroy(); p.refresh()
            messagebox.showinfo("Готово",f"Переименовано: {done}\nПропущено/ошибок: {err}")
        bf=tk.Frame(dialog,bg=BG); bf.pack(pady=12)
        ModernButton(bf,text="Переименовать всё",command=apply,accent=True).pack(side="left",padx=6)
        ModernButton(bf,text="Отмена",command=dialog.destroy).pack(side="left",padx=6)
        update()

    def find_duplicates(self):
        p=self.active_panel()
        if not p: return
        start=str(p.current_path)
        dialog=tk.Toplevel(self.root); dialog.title("Поиск дубликатов..."); dialog.configure(bg=BG)
        dialog.geometry("900x520"); dialog.transient(self.root)
        fade_window(dialog)
        tk.Label(dialog,text="Ищем одинаковые файлы в текущей папке и подпапках...\nЭто может занять время.",bg=BG,fg=TEXT,font=("Segoe UI",10,"bold")).pack(pady=10)
        tree=ttk.Treeview(dialog,columns=("name","size","path"),show="headings")
        tree.heading("name",text="Имя"); tree.heading("size",text="Размер"); tree.heading("path",text="Путь")
        tree.column("name",width=220,anchor="w"); tree.column("size",width=90,anchor="e"); tree.column("path",width=520,anchor="w")
        tree.pack(fill="both",expand=True,padx=10)
        bf=tk.Frame(dialog,bg=BG); bf.pack(pady=10)
        def do_delete():
            s=[x for x in tree.selection() if not x.startswith("__grp")]
            if not s: messagebox.showinfo("Удалить","Выбери файлы в списке."); return
            if not messagebox.askyesno("Удалить",f"Удалить выбранные файлы ({len(s)}) в корзину?"): return
            d=0
            for x in s:
                try: delete_path(Path(x)); d+=1
                except Exception: pass
            tree.delete(*s); p.refresh()
            messagebox.showinfo("Готово",f"Удалено: {d}")
        ModernButton(bf,text="Удалить выбранные",command=do_delete,accent=True).pack(side="left",padx=6)
        ModernButton(bf,text="Закрыть",command=dialog.destroy).pack(side="left",padx=6)
        def worker():
            bysize={}
            try:
                for r,d,fs in os.walk(start):
                    for f in fs:
                        fp=Path(r)/f
                        try: bysize.setdefault(fp.stat().st_size,[]).append(fp)
                        except Exception: pass
            except Exception: pass
            groups=[]
            for sz,files in bysize.items():
                if sz==0 or len(files)<2: continue
                hh={}
                for fp in files:
                    try: hh.setdefault(hash_file(fp),[]).append(fp)
                    except Exception: pass
                for h,fl in hh.items():
                    if len(fl)>1: groups.append(fl)
            self.root.after(0,lambda: fill(groups))
        def fill(groups):
            dialog.title(f"Дубликаты: {sum(len(g)-1 for g in groups)} лишних файлов")
            tree.delete(*tree.get_children())
            for gi,g in enumerate(groups):
                tree.insert("","end",iid=f"__grp{gi}",values=(f"=== Одинаковые ({len(g)} шт) ===","",""))
                for fp in g:
                    tree.insert("","end",iid=str(fp),values=(fp.name,human_size(fp.stat().st_size),str(fp.parent)))
            if not groups:
                tree.insert("","end",values=("Дубликаты не найдены","",""))
        threading.Thread(target=worker,daemon=True).start()

    def zip_selected(self):
        p=self.active_panel()
        if not p: return
        s=[x for x in p.get_selected_paths() if x not in ("__no_access__","__searching__")]
        if not s: messagebox.showinfo("Архив","Сначала выбери файлы или папки."); return
        name=ask_text(p.frame,"Архив ZIP","Имя архива:","archive.zip")
        if not name: return
        if not name.lower().endswith(".zip"): name+=".zip"
        zp=get_unique_destination(p.current_path/name)
        try:
            with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
                for x in s:
                    src=Path(x)
                    if src.is_file(): z.write(src,src.name)
                    else:
                        for r,ds,fs in os.walk(src):
                            for f in fs:
                                fp=Path(r)/f
                                z.write(fp,str(Path(src.name)/fp.relative_to(src)))
            p.refresh(); messagebox.showinfo("Готово",f"Архив создан:\n{zp}")
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось создать архив:\n{e}")

    def unzip_selected(self):
        p=self.active_panel()
        if not p: return
        s=[x for x in p.get_selected_paths() if x not in ("__no_access__","__searching__")]
        if len(s)!=1: messagebox.showinfo("Распаковать","Выбери один ZIP-архив."); return
        src=Path(s[0])
        if src.suffix.lower()!=".zip": messagebox.showinfo("Распаковать","Поддерживается только формат ZIP."); return
        dest=get_unique_destination(src.with_suffix(""))
        try:
            with zipfile.ZipFile(src) as z: z.extractall(dest)
            p.refresh(); messagebox.showinfo("Готово",f"Распаковано в:\n{dest}")
        except Exception as e: messagebox.showerror("Ошибка",f"Не удалось распаковать:\n{e}")

    def paste_items(self):
        p=self.active_panel()
        if not p: return
        if not self.clipboard: messagebox.showinfo("Вставить","Сначала выбери элементы и нажми «Вырезать» или «Копировать»."); return
        action,items=self.clipboard; dr=p.current_path
        pr=0; sk=0; er=0
        for st in items:
            src=Path(st)
            try:
                if not src.exists(): sk+=1; continue
                if src.is_dir() and is_inside(dr,src):
                    messagebox.showwarning("Невозможно",f"Нельзя выполнить действие с папкой '{src.name}' внутри самой себя."); sk+=1; continue
                dest=dr/src.name
                if action=="move" and dest==src: sk+=1; continue
                dest=get_unique_destination(dest)
                if action=="move": shutil.move(str(src),str(dest))
                else:
                    if src.is_dir(): shutil.copytree(str(src),str(dest))
                    else: shutil.copy2(str(src),str(dest))
                pr+=1
            except Exception as e:
                er+=1; messagebox.showerror("Ошибка",f"Не удалось выполнить действие:\n{src}\n\n{e}")
        if action=="move": self.clipboard=None
        p.refresh(); self.update_status()
        messagebox.showinfo("Готово",f"{'Перемещено' if action=='move' else 'Скопировано'}: {pr}\nПропущено: {sk}\nОшибок: {er}")

def main():
    root=tk.Tk()
    root.attributes("-alpha",0.0)
    app=ExplorerApp(root)
    fade_window(root,duration=400)
    root.mainloop()

if __name__=="__main__":
    main() 