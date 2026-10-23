import functools,json,sys,tempfile,threading,time,types,os
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from unittest.mock import patch
from openpyxl import Workbook
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from playwright.sync_api import sync_playwright,expect
from desktop_api import DesktopAPI

OUT=ROOT/'.build/demo';OUT.mkdir(exist_ok=True)
DOCS=ROOT/'docs';DOCS.mkdir(exist_ok=True)
class Dialogs:
    paths=[]
    def create_file_dialog(self,*a,**kw):return [str(self.paths.pop(0))] if self.paths else None
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT/'app/web')))
threading.Thread(target=server.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(dir=ROOT/'.build') as temp:
    temp=Path(temp);api=DesktopAPI(temp);dialogs=Dialogs();api._window=dialogs
    stock=temp/'Estoque demonstrativo.xlsx';b=Workbook();s=b.active;s.title='Estoque'
    s.append(['Cód. Sistema','Produto','Referência','GP'])
    s.append(['47114914W','47-1149 14 W','AR-ESTOQUE-MRS04-F83 W 14','47-ANEL MOISSANITE RODIO'])
    s.append(['461148JW','46-1148 J W','BR-ESTOQUE-MRS04-F83 W','46-BRINCO MOISSANITE RODIO'])
    s.append(['27114714W','27-1147 14 W','AR-PRATA-F83 W 14','27-ANEL PRATA BRANCA'])
    b.save(stock);b.close()
    incoming=temp/'Novos produtos.xlsx';b=Workbook();s=b.active;s.title='Produtos'
    s.append(['Referência','Preço da origem','Peso','GP','Tipo','Tamanho e cor'])
    for ref,gp,kind in [('AR-LUMI-MRS04-F83 W 12','47','Anel'),('AR-LUMI-MRS04-F83 W 14','47','Anel'),('AR-LUMI-MRS04-F83 W 16','47','Anel'),('BR-AURA-MRS04-F83 W','46','Brinco'),('ZZ-MODELO W 14','','Anel'),('AR-ESTOQUE-MRS04-F83 W 14','','Anel')]:s.append([ref,199,None,gp,kind,'J W' if kind=='Brinco' else ''])
    b.save(incoming);b.close()
    try:
        with patch.dict(sys.modules,webview=types.SimpleNamespace(FileDialog=types.SimpleNamespace(OPEN=1,SAVE=2))),sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context(viewport=dict(width=1440,height=1000),record_video_dir=str(OUT),record_video_size=dict(width=1440,height=1000))
            page=context.new_page();page.expose_function('nativeCall',lambda action,payload:api.call(action,payload))
            page.add_init_script('window.pywebview={api:{call:(a,p)=>window.nativeCall(a,p)}}')
            page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
            expect(page.locator('[data-action="dismiss-news"]')).to_be_visible()
            page.locator('[data-action="dismiss-news"]').click()
            page.evaluate("""() => {
              const st=document.createElement('style'); st.textContent='.app-shell{height:calc(100dvh - 104px)} .demo-caption{position:fixed;inset:auto 0 0;height:104px;background:#0f1020;color:white;padding:24px 34px;z-index:120;display:flex;align-items:center;gap:25px;border-top:3px solid #c6f432;pointer-events:none}.demo-caption b{font-size:10px;letter-spacing:2px;color:#c6f432;white-space:nowrap}.demo-caption span{font-size:17px;line-height:1.6}.demo-marker{position:fixed;top:18px;left:520px;color:#a69bb6;font-size:9px;letter-spacing:1px;z-index:40;pointer-events:none}.demo-cursor{position:fixed;left:0;top:0;z-index:200;pointer-events:none;width:24px;height:30px;filter:drop-shadow(0 2px 3px #0005)}';document.head.append(st);
              const cap=document.createElement('div');cap.className='demo-caption';cap.innerHTML='<b>GUIA TROVEN</b><span id="demo-caption-text">Seu cadastro, mais fluido.</span>';document.body.append(cap);
              const marker=document.createElement('div');marker.className='demo-marker';marker.textContent='DEMONSTRAÇÃO · DADOS FICTÍCIOS';document.body.append(marker);
              const cursor=document.createElement('div');cursor.className='demo-cursor';cursor.innerHTML='<svg viewBox="0 0 24 30"><path d="M2 1v23l6-6 5 10 4-2-5-10h9z" fill="#c6f432" stroke="#0f1020" stroke-width="1.6"/></svg>';document.body.append(cursor);gsap.set(cursor,{x:1200,y:700});
            }""")
            def caption(text):
                page.evaluate("text=>{const e=document.querySelector('#demo-caption-text');e.textContent=text;gsap.fromTo(e,{opacity:0,y:8},{opacity:1,y:0,duration:.4})}",text)
            def pause(seconds=2.5):page.wait_for_timeout(seconds*1000)
            def click(selector):
                el=page.locator(selector).first;el.scroll_into_view_if_needed();box=el.bounding_box()
                page.evaluate("p=>gsap.to('.demo-cursor',{x:p.x,y:p.y,duration:.65,ease:'power2.inOut'})",dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2))
                pause(.7);el.click();pause(.65)
            caption('Troven Cadastro. Do estoque à Grade Lançar, em um só fluxo.');pause(3)
            page.wait_for_function("!gsap.isTweening('#page > *')")
            # Imagem do README sem os elementos editoriais do vídeo.
            page.locator('.demo-caption').evaluate("e=>e.style.visibility='hidden'")
            page.locator('.demo-cursor').evaluate("e=>e.style.visibility='hidden'")
            page.screenshot(path=str(DOCS/'visao-geral.png'),clip=dict(x=0,y=0,width=1440,height=896))
            page.locator('.demo-caption').evaluate("e=>e.style.visibility='visible'")
            page.locator('.demo-cursor').evaluate("e=>e.style.visibility='visible'")
            caption('01 · Selecione o Excel de estoque. A sequência é única entre os grupos.')
            click('[data-action="open-stock"]');dialogs.paths.append(stock);click('[data-action="choose-stock"]');click('[data-action="load-stock"]');pause(2)
            caption('02 · Importe os produtos. Escolha só as colunas úteis; o restante é ignorado.')
            dialogs.paths.append(incoming);click('[data-action="choose-new"]');pause(3);click('[data-action="confirm-import"]');pause(2)
            caption('A cadastrar reúne novos modelos e novas variações. Cada situação indica o próximo passo.')
            click('[data-filter="A cadastrar (novos e variações)"]');pause(3)
            caption('Pendências ficam separadas. Selecione um item e aplique a categoria correta.')
            click('[data-filter="Precisam de atenção"]');click('.row-select');click('[data-action="bulk-category"]')
            page.locator('#group-search').fill('47 anel');page.locator('#group-select').select_option(label='47-ANEL MOISSANITE RODIO');pause(2);click('[data-action="apply-category"]');pause(1)
            click('[data-filter="Todos"]')
            caption('03 · Confira pesos e unidades. Sem peso: 1 PC ou PR. Com peso informado: G.')
            click('[data-action="open-weights"]');pause(3)
            caption('A prévia mostra as 19 colunas, as variações e os pais únicos no final.')
            click('[data-action="preview-grade"]');pause(3)
            dialogs.paths.append(temp/'Grade Lançar.xlsx');caption('Exporte a Grade Lançar. O pai acompanha a unidade e mantém os valores fixos.')
            click('#modal-footer [data-action="export"]');expect(page.locator('#success-lottie svg')).to_be_visible();pause(3);click('#modal-footer [data-action="close-modal"]')
            caption('Novidades dentro do sistema: o changelog aparece após atualizar e fica disponível offline.')
            click('[data-page="novidades"]');pause(4)
            caption('Ao fechar ou minimizar, o Troven vai para a bandeja. Use o ícone para reabrir ou Sair.')
            pause(4)
            caption('Tutorial integrado, fontes locais e interface responsiva. GSAP + Lottie, sem depender de internet.')
            click('[data-action="tutorial"]');pause(3);click('[data-action="next-lesson"]');pause(2);click('#close-modal')
            click('[data-page="inicio"]');caption('Menos trabalho repetitivo. Mais clareza para o próximo lançamento. Troven.');pause(4)
            video=page.video;context.close();video.save_as(str(OUT/'Troven-Cadastro-Demonstracao.webm'));browser.close()
            print(OUT/'Troven-Cadastro-Demonstracao.webm',flush=True)
    finally:api._close();server.shutdown()
