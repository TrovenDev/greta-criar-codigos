"""Build reproduzível do aplicativo e do instalador. Execute no Windows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
VERSION=runpy.run_path(str(ROOT/'app/version_info.py'))['VERSION']
TOOLS=ROOT/'.build/tools'
DIST=ROOT/'dist'

def run(args):
    subprocess.run([str(x) for x in args],cwd=ROOT,check=True)

def download(url,dest,expected=None):
    if not dest.exists():
        print('Baixando',dest.name,flush=True)
        request=urllib.request.Request(url,headers={'User-Agent':'Troven-build/'+VERSION})
        with urllib.request.urlopen(request,timeout=90) as response:
            dest.write_bytes(response.read())
    if expected and hashlib.sha256(dest.read_bytes()).hexdigest()!=expected:
        raise RuntimeError('Integridade inválida: '+dest.name)
    if expected:
        # Hash de uma distribuição cuja assinatura oficial foi conferida.
        # Evita depender de servidores de revogação durante builds isolados.
        return
    command="$s=Get-AuthenticodeSignature -LiteralPath '"+str(dest).replace("'","''")+"'; if($s.Status -ne 'Valid'){throw 'Assinatura do componente inválida'}"
    run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command])

def main():
    p=argparse.ArgumentParser();p.add_argument('--inno');p.add_argument('--skip-freeze',action='store_true');args=p.parse_args()
    TOOLS.mkdir(parents=True,exist_ok=True);DIST.mkdir(exist_ok=True)
    demo=ROOT/'app/web/media/demo.mp4'
    demo.parent.mkdir(parents=True,exist_ok=True)
    download('https://github.com/TrovenDev/greta-criar-codigos/releases/download/v9.0.1/Troven-Cadastro-Demonstracao.mp4',demo,
             'b3780522e8cb7620473e894cf0a6f5f71605988ab29144d84e15ff0cb1673ecc')
    resource=ROOT/'.build/version.txt'
    numbers=tuple(int(x) for x in VERSION.split('.'))+(0,)
    resource.write_text("VSVersionInfo(ffi=FixedFileInfo(filevers="+repr(numbers)+",prodvers="+repr(numbers)+",mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),kids=[StringFileInfo([StringTable('041604B0',[StringStruct('CompanyName','Troven'),StringStruct('FileDescription','Troven Cadastro'),StringStruct('FileVersion',"+repr(VERSION)+"),StringStruct('ProductVersion',"+repr(VERSION)+"),StringStruct('ProductName','Troven Cadastro'),StringStruct('OriginalFilename','Troven Cadastro.exe')])]),VarFileInfo([VarStruct('Translation',[1046,1200])])])",encoding='utf-8')
    if not args.skip_freeze:
        command=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','Troven Cadastro',
          '--icon',ROOT/'app/assets/troven.ico','--version-file',resource,
          '--add-data',str(ROOT/'app/assets')+';assets','--add-data',str(ROOT/'app/web')+';web',
          '--collect-all','webview','--collect-all','clr_loader','--hidden-import','pythonnet','--hidden-import','clr',
          '--hidden-import','webview.platforms.edgechromium','--hidden-import','webview.platforms.winforms',
          '--distpath',DIST,'--workpath',ROOT/'.build/pyinstaller','--specpath',ROOT/'.build']
        for module in ('numpy','pandas','PIL','lxml','matplotlib','PyQt5','PyQt6','PySide2','PySide6','scipy','playwright'):
            command+=['--exclude-module',module]
        run(command+[ROOT/'app/desktop.py'])
    bootstrap=TOOLS/'MicrosoftEdgeWebview2Setup.exe'
    shutil.copy2(ROOT/'installer/vendor/webview2-bootstrapper.bin',bootstrap)
    download('',bootstrap,'f414de01c4680f0bb0694d1ea7803c6968f3a81bf6bad01b89bfc65dce14c2a2')
    if args.inno:
        compiler=Path(args.inno)
    else:
        compiler=TOOLS/'inno/ISCC.exe'
        if not compiler.exists():
            installer=TOOLS/'inno-setup.exe'
            download('https://github.com/jrsoftware/issrc/releases/download/is-6_4_3/innosetup-6.4.3.exe',installer,
                     'f3c42116542c4cc57263c5ba6c4feabfc49fe771f2f98a79d2f7628b8762723b')
            run([installer,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/PORTABLE=1','/DIR='+str(compiler.parent)])
    run([compiler,'/DProjectRoot='+str(ROOT),'/DAppVersion='+VERSION,ROOT/'installer/Troven.iss'])
    output=DIST/f'Troven-Cadastro-Instalador-v{VERSION}.exe'
    with output.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    (DIST/'SHA256SUMS.txt').write_text(digest+'  '+output.name+'\n',encoding='utf-8')
    history=json.loads((ROOT/'app/web/changelog.json').read_text(encoding='utf-8'))
    note=next((n for n in history if n['version']==VERSION),None)
    if not note:raise RuntimeError('Inclua o changelog da versão antes de publicar.')
    (DIST/'RELEASE_NOTES.md').write_text(note['title']+'\n\n'+note['body']+'\n',encoding='utf-8')
    print('INSTALADOR:',output,flush=True)

if __name__=='__main__':main()
