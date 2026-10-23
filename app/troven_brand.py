"""Identidade oficial: https://marca.troven.com.br/ (manual 2026)."""
import sys
from pathlib import Path

COBALTO = '#2B35F0'
LIMA = '#C6F432'
NOITE = '#0F1020'
NOITE2 = '#191A30'
PAPEL = '#F7F5F1'
BRANCO = '#FFFFFF'
LINHA = '#E4E1DA'
MUTED = '#5E5F6E'
MUTED_DARK = '#A3A5BE'
SOFT = '#F0F1FF'
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets'
BODY, STRONG, DISPLAY = 'Inter', 'Inter SemiBold', 'Unbounded SemiBold'


def load_fonts(root):
    global BODY, STRONG, DISPLAY
    if sys.platform == 'win32':
        import ctypes
        for path in ASSETS.glob('*.ttf'):
            ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)
    from tkinter import font
    available = set(font.families(root))
    BODY = 'Inter' if 'Inter' in available else 'Segoe UI'
    STRONG = 'Inter SemiBold' if 'Inter SemiBold' in available else BODY
    DISPLAY = 'Unbounded SemiBold' if 'Unbounded SemiBold' in available else BODY


def configure(root):
    from tkinter import ttk
    load_fonts(root)
    root.configure(background=PAPEL)
    root.option_add('*Font', (BODY, 10))
    root.option_add('*TCombobox*Listbox.font', (BODY, 10))
    try:
        root.iconbitmap(str(ASSETS / 'troven.ico'))
    except Exception:
        pass
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('.', font=(BODY, 10))
    s.configure('TFrame', background=BRANCO)
    s.configure('TLabel', background=BRANCO, foreground=NOITE, font=(BODY, 10))
    s.configure('App.TFrame', background=PAPEL)
    s.configure('Caption.TLabel', background=PAPEL, foreground=MUTED, font=(BODY, 10))
    s.configure('PageTitle.TLabel', background=BRANCO, foreground=NOITE, font=(DISPLAY, 15))
    s.configure('Muted.TLabel', background=BRANCO, foreground=MUTED)
    s.configure('TButton', padding=(13, 9), font=(STRONG, 10), background=BRANCO, foreground=NOITE, bordercolor=LINHA, borderwidth=1, focusthickness=2, focuscolor=COBALTO)
    s.map('TButton', background=[('active', PAPEL), ('pressed', LINHA)], foreground=[('disabled', '#8C8D97')])
    s.configure('Primary.TButton', background=COBALTO, foreground=BRANCO, bordercolor=COBALTO, focuscolor=LIMA)
    s.map('Primary.TButton', background=[('active', '#222BD1'), ('pressed', '#1D24B7'), ('disabled', '#C7CAF8')], foreground=[('disabled', '#F7F7FF')])
    s.configure('TEntry', fieldbackground=BRANCO, foreground=NOITE, bordercolor=LINHA, padding=7, lightcolor=LINHA, darkcolor=LINHA)
    s.map('TEntry', bordercolor=[('focus', COBALTO)])
    s.configure('TCombobox', fieldbackground=BRANCO, foreground=NOITE, bordercolor=LINHA, padding=7, arrowcolor=COBALTO)
    s.map('TCombobox', fieldbackground=[('readonly', BRANCO)], selectbackground=[('readonly', BRANCO)], selectforeground=[('readonly', NOITE)], bordercolor=[('focus', COBALTO)])
    s.configure('TCheckbutton', background=BRANCO, foreground=NOITE, font=(BODY, 10), padding=3)
    s.map('TCheckbutton', background=[('active', BRANCO)])
    s.configure('Treeview', background=BRANCO, fieldbackground=BRANCO, foreground=NOITE, rowheight=33, borderwidth=0, font=(BODY, 10))
    s.configure('Treeview.Heading', background=PAPEL, foreground=MUTED, font=(STRONG, 10), relief='flat', padding=(8, 10), borderwidth=0)
    s.map('Treeview', background=[('selected', COBALTO)], foreground=[('selected', BRANCO)])
    s.map('Treeview.Heading', background=[('active', LINHA)])
    s.configure('TScrollbar', background=LINHA, troughcolor=PAPEL, arrowcolor=MUTED, borderwidth=0, arrowsize=12)
    s.configure('Troven.TNotebook', background=PAPEL, borderwidth=0, tabmargins=0)
    s.layout('Troven.TNotebook.Tab', [])
    return s


def tip(parent, title, body, wrap=800):
    import tkinter as tk
    box = tk.Frame(parent, bg=SOFT, highlightthickness=0)
    box.pack(fill='x', pady=(10, 4))
    tk.Frame(box, bg=COBALTO, width=3).pack(side='left', fill='y')
    inner = tk.Frame(box, bg=SOFT)
    inner.pack(fill='x', padx=12, pady=9)
    tk.Label(inner, text=title, bg=SOFT, fg=COBALTO, font=(STRONG, 10), anchor='w').pack(anchor='w')
    label = tk.Label(inner, text=body, bg=SOFT, fg=MUTED, font=(BODY, 9), justify='left', wraplength=wrap, anchor='w')
    label.pack(anchor='w', pady=(3, 0))
    inner.bind('<Configure>', lambda e: label.configure(wraplength=max(160, e.width - 8)))
    return box


class Shell:
    def __init__(self, app, root):
        import tkinter as tk
        from tkinter import ttk
        self.app, self.root = app, root
        self.nav = []
        root.title('Troven • Criar códigos')
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        width, height = min(1440, screen_w - 60), min(920, screen_h - 80)
        root.geometry(f'{width}x{height}')
        root.minsize(min(1180, width), min(760, height))
        configure(root)
        sidebar = tk.Frame(root, bg=NOITE, width=244)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        self.logo = tk.PhotoImage(file=str(ASSETS / 'troven-horizontal-negativo-ui.png'))
        tk.Label(sidebar, image=self.logo, bg=NOITE).pack(anchor='w', padx=23, pady=(32, 26))
        tk.Label(sidebar, text='CADASTRO DE PRODUTOS', bg=NOITE, fg=MUTED_DARK, font=(STRONG, 9)).pack(anchor='w', padx=24)
        tk.Frame(sidebar, height=1, bg='#2A2C47').pack(fill='x', padx=24, pady=25)
        for i, (title, desc) in enumerate((('Estoque', 'Carregue seu Excel'), ('Códigos novos', 'Importe os produtos'), ('Cadastro e peso', 'Confira peso e unidade'))):
            box = tk.Frame(sidebar, bg=NOITE, cursor='hand2')
            box.pack(fill='x', padx=12, pady=5)
            number = tk.Label(box, text=f'{i + 1:02d}', bg=NOITE, fg=MUTED_DARK, font=(DISPLAY, 12), width=3)
            number.pack(side='left', padx=(8, 5), pady=15)
            text = tk.Frame(box, bg=NOITE)
            text.pack(side='left', fill='x', expand=True, pady=12)
            label = tk.Label(text, text=title, bg=NOITE, fg=BRANCO, font=(STRONG, 11), anchor='w')
            label.pack(anchor='w')
            sub = tk.Label(text, text=desc, bg=NOITE, fg=MUTED_DARK, font=(BODY, 9), anchor='w')
            sub.pack(anchor='w', pady=(4, 0))
            self.nav.append((box, number, text, label, sub))
            for widget in (box, number, text, label, sub):
                widget.bind('<Button-1>', lambda e, n=i: self.navigate(n))
        lower = tk.Frame(sidebar, bg=NOITE)
        lower.pack(side='bottom', fill='x', padx=24, pady=24)
        tk.Label(lower, text='PRIMEIRA VEZ POR AQUI?', bg=NOITE, fg=MUTED_DARK, font=(STRONG, 8)).pack(anchor='w')
        tk.Button(lower, text='Ver tutorial  ↗', command=app.open_tutorial, bg=LIMA, fg=NOITE, activebackground='#D5FC62', activeforeground=NOITE, font=(STRONG, 11), bd=0, relief='flat', cursor='hand2', padx=18, pady=12).pack(fill='x', pady=(12, 8))
        tk.Label(lower, text='Aprenda com exemplos.\nF1 abre a ajuda a qualquer momento.', bg=NOITE, fg=MUTED_DARK, justify='left', font=(BODY, 9), wraplength=196).pack(anchor='w', pady=(2, 25))
        tk.Frame(lower, height=1, bg='#2A2C47').pack(fill='x', pady=(0, 15))
        tk.Label(lower, text='troven.com.br', bg=NOITE, fg=MUTED_DARK, font=(BODY, 9)).pack(anchor='w')
        main = ttk.Frame(root, style='App.TFrame', padding=(26, 20, 26, 12))
        main.pack(side='left', fill='both', expand=True)
        header = ttk.Frame(main, style='App.TFrame')
        header.pack(fill='x', pady=(0, 17))
        titlebox = ttk.Frame(header, style='App.TFrame')
        titlebox.pack(side='left')
        ttk.Label(titlebox, text='Criar códigos', style='Caption.TLabel', font=(DISPLAY, 20), foreground=NOITE).pack(anchor='w')
        ttk.Label(titlebox, text='Do estoque ao cadastro com peso.', style='Caption.TLabel').pack(anchor='w', pady=(5, 0))
        ttk.Button(header, text='Tutorial e ajuda  F1', command=app.open_tutorial).pack(side='right', anchor='n', pady=5)
        app.tabs = ttk.Notebook(main, style='Troven.TNotebook')
        app.tabs.pack(fill='both', expand=True)
        app.pages = [ttk.Frame(app.tabs, padding=20) for _ in range(3)]
        for page, title in zip(app.pages, ('Estoque', 'Códigos novos', 'Cadastro e peso')):
            app.tabs.add(page, text=title)
        app.tabs.tab(1, state='disabled')
        app.tabs.tab(2, state='disabled')
        ttk.Label(main, textvariable=app.summary, style='Caption.TLabel', wraplength=1000).pack(anchor='w', pady=(12, 0))
        app.tabs.bind('<<NotebookTabChanged>>', lambda e: self.refresh())
        root.bind('<F1>', lambda e: app.open_tutorial())

    def navigate(self, index):
        if self.app.tabs.tab(index, 'state') == 'disabled':
            self.app.summary.set('Carregue o estoque na etapa 1. Depois, gere os códigos na etapa 2 para abrir o cadastro.')
            return
        self.app.tabs.select(index)
        self.refresh()

    def refresh(self):
        selected = self.app.tabs.index(self.app.tabs.select())
        for i, widgets in enumerate(self.nav):
            enabled = self.app.tabs.tab(i, 'state') != 'disabled'
            bg = COBALTO if i == selected else NOITE
            for widget in widgets:
                widget.configure(bg=bg, cursor='hand2' if enabled else 'arrow')
            _, number, _, title, desc = widgets
            number.configure(fg=LIMA if i == selected else MUTED_DARK if enabled else '#66687C')
            title.configure(fg=BRANCO if enabled else '#77798C')
            desc.configure(fg='#E6E7FF' if i == selected else MUTED_DARK if enabled else '#66687C')
