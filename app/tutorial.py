"""Tutorial guiado com dados isolados; nenhuma reserva ou arquivo é criado."""
import tkinter as tk
from tkinter import ttk
import troven_brand as brand

LESSONS = (
    ('Estoque', 'Comece com o estoque atualizado.',
     'Clique em Selecionar Excel de estoque e escolha um arquivo .xlsx ou .xlsm.\n\n'
     'O relatório precisa das colunas Código do sistema, Produto, Referência e GP. A ordem das colunas e o nome da aba podem variar. Se houver mais de uma aba compatível, escolha a aba e clique em Carregar estoque.\n\n'
     'A sequência é única para todos os grupos. O próximo número considera o estoque e as reservas locais. No exemplo abaixo, o estoque termina em 1149.',
     'Simular carregamento', 0),
    ('Referências', 'Cole as referências. Confira os códigos.',
     'Na etapa Códigos novos, clique em Selecionar planilha de códigos novos. Escolha seu Excel, a aba e a linha dos títulos. Selecione as colunas de referência, peso, categoria/GP e tipo que forem úteis. As demais são ignoradas. Confira a prévia e clique em Importar produtos.\n\n'
     'Você pode misturar anéis, brincos e outras categorias no mesmo arquivo. Para colar referências, marque Colar referências manualmente (opcional) e use o campo de texto.\n\n'
     'O sistema identifica a categoria pela referência ou pelo modelo no estoque quando a correspondência é única. Se aparecer Escolha a categoria, selecione a linha, busque o GP e clique em Aplicar categoria. A opção abaixo da busca também aplica a escolha às variações sem categoria do mesmo modelo.\n\n'
     'Use Mostrar para filtrar A cadastrar (novos e variações): tanto o primeiro tamanho de um modelo novo quanto seus outros tamanhos aparecem juntos. Já cadastrado no estoque significa que aquela referência já possui código no grupo compatível. Precisa de atenção explica o que corrigir na coluna O que fazer agora. Buscar produto encontra referência, código e produto. Os filtros não mudam quais itens serão exportados.\n\nClique em Gerar e conferir códigos. Novos modelos recebem a próxima sequência geral. As variações de uma família existente mantêm seu número.\n\n'
     'Tamanho e cor são identificados por referência. Em AR38137-MRS04-F83 MCB 12, são tamanho 12 e cor MCB. Se faltarem dados, dê dois cliques na linha para editar categoria, tamanho e cor.\n\n'
     'Também é possível colar quatro colunas: referência, tamanho e cor, peso (g) e GP. A segunda coluna vale apenas para aquela linha. Separe as colunas copiando-as diretamente do Excel.',
     'Gerar códigos de exemplo', 1),
    ('Padrões', 'Defina a categoria uma vez por padrão.',
     'Abra Regras de categoria na etapa Códigos novos. Informe um padrão de referência, escolha o GP e clique em Salvar e aplicar regra. A regra fica disponível nos próximos lotes.\n\n'
     '* significa qualquer trecho. AR* encontra referências que começam com AR. AR*-MRS*-F83* encontra esse conjunto de trechos em sequência.\n\n'
     'Use Categoria na planilha de origem para ajudar a reconhecer o material. Referências com -MRS e itens identificados como moissanite na origem só aceitam grupos de moissanite, inclusive na escolha manual. Registros antigos de outros materiais são desconsiderados. Regras conflitantes ficam para revisão.\n\n'
     'O sistema também reconhece padrões presentes em vários modelos do estoque quando todos apontam para a mesma categoria. Você pode conferir ou desativar esse recurso na janela de regras.',
     'Aplicar uma regra a 10 itens', 1),
    ('Pesos e unidades', 'Confira como cada produto é vendido.',
     'Quando a planilha tem peso informado, o produto fica com unidade G. Quando o peso está vazio, o valor é 1 e a unidade é PC para anéis e outros produtos ou PR para brincos. Peso zero e texto inválido precisam ser corrigidos.\n\n'
     'Abra Cadastro e peso. Dê dois cliques em uma linha para escolher venda por peso ou por unidade. Você pode digitar 2,35 ou 2.35. Um peso informado deve ser maior que zero.\n\n'
     'Para repetir o peso, selecione várias linhas com Ctrl ou Shift, digite o valor e clique em Aplicar às selecionadas.\n\n'
     'Para pesos diferentes, use Colar pesos por referência: copie duas colunas do Excel, com código ou referência na primeira e peso na segunda.',
     'Aplicar pesos de exemplo', 2),
    ('Exportação', 'Exporte só o que você conferiu.',
     'Confira a coluna Exportar. Somente as linhas marcadas com Sim entram no arquivo. Use Marcar/desmarcar selecionadas para ajustar a seleção.\n\n'
     'Clique em Exportar Excel para salvar Grade Lançar.xlsx com as 19 colunas do modelo dmaaa. Exportar CSV usa os mesmos campos.\n\n'
     'As variações vêm primeiro. Depois, o sistema cria um pai para cada aaa_produtobase único. No pai, a referência não tem cor nem tamanho, pesogramas é 0, fatconv é 50 e peso é 0. O campo aaa_produtobase do pai fica vazio. A unidade do pai acompanha as variações: G, PC ou PR. Se as variações do mesmo modelo tiverem unidades diferentes, revise antes de exportar.\n\n'
     'Confira G para venda por peso e PC/PR para venda por unidade. Ao exportar, os novos códigos são reservados localmente. Produtos já presentes no estoque ficam de fora por padrão. Marque Incluir já cadastrados se quiser incluí-los.',
     'Visualizar arquivo de exemplo', 2),
    ('Salvar e dúvidas', 'Retome seu lote quando precisar.',
     'Clique em Salvar lote para guardar o trabalho. O fechamento também salva automaticamente. Na próxima abertura, use Restaurar último lote na etapa Estoque. Mantenha o Excel do estoque acessível no mesmo caminho.\n\n'
     'Referência ambígua: há mais de um código possível. Confira o GP e o estoque. Código em uso: revise tamanho, cor e referência. Preencher peso: informe o peso antes de exportar.\n\n'
     'Os dados ficam no arquivo reservas.sqlite3, junto do executável. Para trocar de versão, copie esse arquivo com o aplicativo fechado. Cópias em computadores diferentes não compartilham a sequência. A exportação não cadastra produtos automaticamente no ERP.',
     'Ver exemplos de avisos', 0),
)


class Tutorial:
    def __init__(self, app):
        Workflow = type(app.catalog)
        self.app = app
        self.catalog = Workflow([
            dict(codigo='17114814W', produto='17-1148 14 W', referencia='AR-ANTIGO W 14', grupo='17-ANEL'),
            dict(codigo='261149JW', produto='26-1149 J W', referencia='BR-ANTIGO W', grupo='26-BRINCO'),
        ], ':memory:')
        self.example = []
        self.index = 0
        self.window = tk.Toplevel(app.root)
        self.window.title('Troven • Tutorial do cadastro')
        w, h = min(1080, app.root.winfo_screenwidth() - 80), min(800, app.root.winfo_screenheight() - 90)
        self.window.geometry(f'{w}x{h}')
        self.window.minsize(min(900, w), min(620, h))
        self.window.configure(bg=brand.PAPEL)
        self.window.transient(app.root)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Escape>', lambda e: self.close())
        try:
            self.window.iconbitmap(str(brand.ASSETS / 'troven.ico'))
        except Exception:
            pass
        self.logo = tk.PhotoImage(file=str(brand.ASSETS / 'troven-horizontal-negativo-ui.png'))
        header = tk.Frame(self.window, bg=brand.NOITE)
        header.pack(fill='x')
        tk.Label(header, image=self.logo, bg=brand.NOITE).pack(side='left', padx=24, pady=23)
        tk.Label(header, text='TUTORIAL DO CADASTRO', bg=brand.NOITE, fg=brand.LIMA, font=(brand.STRONG, 10)).pack(side='right', padx=24)
        middle = tk.Frame(self.window, bg=brand.PAPEL)
        middle.pack(fill='both', expand=True, padx=20, pady=20)
        side = tk.Frame(middle, bg=brand.PAPEL, width=185)
        side.pack(side='left', fill='y', padx=(0, 20))
        side.pack_propagate(False)
        self.nav = []
        tk.Label(side, text='PASSO A PASSO', bg=brand.PAPEL, fg=brand.MUTED, font=(brand.STRONG, 9)).pack(anchor='w', pady=(4, 12))
        for i, lesson in enumerate(LESSONS):
            b = tk.Button(side, text=f'{i + 1:02d}  {lesson[0]}', anchor='w', font=(brand.STRONG, 10), bg=brand.PAPEL, fg=brand.MUTED, bd=0, padx=12, pady=13, activebackground=brand.SOFT, cursor='hand2', command=lambda n=i: self.show(n))
            b.pack(fill='x', pady=3)
            self.nav.append(b)
        tk.Label(side, text='DADOS DE EXEMPLO\n\nEste tutorial funciona sem arquivos e não altera seu cadastro.', bg=brand.PAPEL, fg=brand.MUTED, font=(brand.BODY, 9), wraplength=175, justify='left').pack(anchor='w', pady=24)
        content = tk.Frame(middle, bg=brand.BRANCO, padx=22, pady=18)
        content.pack(side='left', fill='both', expand=True)
        self.step_label = tk.Label(content, bg=brand.BRANCO, fg=brand.COBALTO, font=(brand.STRONG, 9), anchor='w')
        self.step_label.pack(anchor='w')
        self.title = tk.Label(content, bg=brand.BRANCO, fg=brand.NOITE, font=(brand.DISPLAY, 14), justify='left', anchor='w', wraplength=700)
        self.title.pack(anchor='w', pady=(8, 14))
        bodyframe = tk.Frame(content, bg=brand.BRANCO)
        bodyframe.pack(fill='both', expand=True)
        self.body = tk.Text(bodyframe, height=8, wrap='word', font=(brand.BODY, 10), bg=brand.BRANCO, fg=brand.MUTED, bd=0, highlightthickness=0, padx=0, pady=0, spacing1=0, spacing3=4)
        sy = ttk.Scrollbar(bodyframe, command=self.body.yview)
        self.body.configure(yscrollcommand=sy.set)
        self.body.pack(side='left', fill='both', expand=True)
        sy.pack(side='right', fill='y')
        self.demo_button = ttk.Button(content, style='Primary.TButton', command=self.run_demo)
        self.demo_button.pack(anchor='w', pady=(15, 10))
        self.demo_tree = ttk.Treeview(content, show='headings', height=4)
        self.demo_tree.pack(fill='x')
        self.demo_note = tk.StringVar()
        self.demo_label = tk.Label(content, textvariable=self.demo_note, bg=brand.BRANCO, fg=brand.COBALTO, font=(brand.BODY, 9), justify='left', anchor='w', wraplength=700)
        self.demo_label.pack(anchor='w', pady=(9, 0))
        content.bind('<Configure>', lambda e: (self.title.configure(wraplength=max(250, e.width - 44)), self.demo_label.configure(wraplength=max(250, e.width - 44))))
        footer = tk.Frame(self.window, bg=brand.PAPEL)
        footer.pack(fill='x', padx=20, pady=(0, 20))
        self.progress = tk.StringVar()
        tk.Label(footer, textvariable=self.progress, bg=brand.PAPEL, fg=brand.MUTED, font=(brand.BODY, 10)).pack(side='left')
        ttk.Button(footer, text='Abrir esta etapa no cadastro', command=self.open_stage).pack(side='left', padx=20)
        self.next = ttk.Button(footer, text='Próximo', style='Primary.TButton', command=self.forward)
        self.next.pack(side='right')
        self.previous = ttk.Button(footer, text='Anterior', command=lambda: self.show(self.index - 1))
        self.previous.pack(side='right', padx=10)
        self.show(0)

    def table(self, titles, rows):
        self.demo_tree.delete(*self.demo_tree.get_children())
        self.demo_tree['columns'] = tuple(str(i) for i in range(len(titles)))
        for i, title in enumerate(titles):
            self.demo_tree.heading(str(i), text=title)
            self.demo_tree.column(str(i), width=150, minwidth=60, stretch=True)
        for row in rows:
            self.demo_tree.insert('', 'end', values=row)

    def show(self, index):
        if not 0 <= index < len(LESSONS):
            return
        self.index = index
        lesson = LESSONS[index]
        self.step_label.configure(text=f'{index + 1:02d} / {len(LESSONS):02d}   {lesson[0].upper()}')
        self.title.configure(text=lesson[1])
        self.body.configure(state='normal')
        self.body.delete('1.0', 'end')
        self.body.insert('1.0', lesson[2])
        self.body.configure(state='disabled')
        self.body.yview_moveto(0)
        self.demo_button.configure(text=lesson[3])
        self.progress.set(f'Etapa {index + 1} de {len(LESSONS)}')
        self.previous.configure(state='disabled' if index == 0 else 'normal')
        self.next.configure(text='Concluir tutorial' if index == len(LESSONS) - 1 else 'Próximo')
        for i, nav in enumerate(self.nav):
            nav.configure(bg=brand.COBALTO if i == index else brand.PAPEL, fg=brand.BRANCO if i == index else brand.MUTED)
        self.table(('Exemplo guiado', 'Resultado'), [('Clique no botão acima para experimentar.', '—')])
        self.demo_note.set('Você pode navegar pelas etapas em qualquer ordem.')

    def ensure_examples(self):
        if not self.example:
            self.example = self.catalog.prepare('AR-ANTIGO CZ04 14\nBR-ANTIGO CZ04')

    def run_demo(self):
        if self.index == 0:
            self.table(('Produtos no exemplo', 'Última sequência', 'Próximo número'), [('2 produtos', f'{self.catalog.last_number(True):04d}', f'{self.catalog.last_number() + 1:04d}')])
            self.demo_note.set('Estoque de exemplo carregado. O próximo modelo recebe 1150, em qualquer grupo.')
        elif self.index == 1:
            self.ensure_examples()
            self.table(('Referência', 'Categoria', 'Código'), [(r['referencia'], r['grupo'], r['codigo']) for r in self.example])
            self.demo_note.set('Anel e brinco ficam em categorias diferentes. Cada variação preserva o número de seu modelo no estoque.')
        elif self.index == 2:
            self.catalog.rules.save('AR-DEMO-*', '', '17-ANEL')
            rows = self.catalog.prepare('\n'.join(f'AR-DEMO-{i}-F83 W 14' for i in range(10)))
            self.table(('Referência', 'Categoria', 'Situação'), [(r['referencia'],r['grupo'],r['status']) for r in rows[:3]])
            self.demo_note.set('Uma regra aplicou a categoria 17-ANEL aos 10 itens de exemplo. A tabela mostra os três primeiros.')
        elif self.index == 3:
            self.ensure_examples()
            for r, v in zip(self.example, ('2,35', '3,10')):
                self.catalog.set_weight(r, v)
            self.catalog.set_weight(self.example[1], None)
            self.table(('Código', 'Referência', 'Peso', 'Unidade'), [(r['codigo'], r['referencia'], str(r['peso']).replace('.', ','), r['unidade']) for r in self.example])
            self.demo_note.set('O anel tem peso 2,35 e unidade G. O brinco sem peso usa valor 1 e unidade PR.')
        elif self.index == 4:
            self.ensure_examples()
            for r, v in zip(self.example, ('2,35', '3,10')):
                self.catalog.set_weight(r, v)
            self.catalog.set_weight(self.example[1], None)
            records = self.catalog.export_rows(self.example)
            from grade_export import grade_rows
            rows = grade_rows(records)
            self.table(('Código', 'Referência', 'Pesogramas', 'Fatconv'), [(r[2],r[4],r[7],r[8]) for r in rows])
            self.demo_note.set('Prévia de quatro dos 19 campos: duas variações e dois pais. Nos pais, os valores são 0 e 50.')
        else:
            self.table(('Aviso', 'Como resolver'), [('Preencher peso', 'Informe um peso maior que zero.'), ('Escolha a categoria', 'Selecione a linha e aplique o GP correto.'), ('Referência ambígua', 'Confira a categoria e as referências do estoque.')])
            self.demo_note.set('Volte à etapa indicada, corrija o campo e confira o resultado novamente.')

    def forward(self):
        if self.index == len(LESSONS) - 1:
            self.close()
        else:
            self.show(self.index + 1)

    def open_stage(self):
        page = LESSONS[self.index][4]
        if self.app.tabs.tab(page, 'state') == 'disabled':
            page = 0
        self.app.tabs.select(page)
        self.app.shell.refresh()
        self.close()

    def close(self):
        self.catalog.db.close()
        self.window.destroy()
