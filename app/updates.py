"""Atualizações oficiais por Releases; base de dados permanece fora do programa."""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from version_info import VERSION, REPOSITORY


def version_tuple(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',str(value))
    return tuple(map(int,match.groups())) if match else (0,0,0)


class UpdateManager:
    def __init__(self, home):
        self._folder=Path(home)/'updates'
        self._lock=threading.Lock()
        self._worker=None
        self._launched=False
        self._state=dict(version=VERSION,status='idle',message='Verificação automática ao abrir o aplicativo.')

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def _set(self,**fields):
        with self._lock:
            self._state.update(fields)

    def start(self):
        with self._lock:
            if self._worker and self._worker.is_alive():
                return self.snapshot_unlocked()
            self._worker=threading.Thread(target=self.check,daemon=True,name='troven-update')
            self._worker.start()
            return dict(self._state)

    def snapshot_unlocked(self):
        return dict(self._state)

    def _open(self,url):
        req=urllib.request.Request(url,headers={'User-Agent':'Troven-Cadastro/'+VERSION,'Accept':'application/vnd.github+json'})
        return urllib.request.urlopen(req,timeout=30)

    def check(self):
        self._set(status='checking',message='Buscando a versão mais recente…')
        try:
            with self._open(f'https://api.github.com/repos/{REPOSITORY}/releases/latest') as response:
                release=json.loads(response.read(2_000_000))
            if not release.get('draft') and not release.get('prerelease'):
                self._cache_notes(release)
            if release.get('draft') or release.get('prerelease') or version_tuple(release.get('tag_name'))<=version_tuple(VERSION):
                self._set(status='current',message='Você já está na versão mais recente.')
                return
            assets=release.get('assets',[])
            asset=next((a for a in assets if re.fullmatch(r'Troven-Cadastro-Instalador-v[\d.]+\.exe',a.get('name',''))),None)
            if not asset:
                raise ValueError('A nova versão ainda não tem instalador publicado.')
            url=asset['browser_download_url']
            expected_prefix=f'https://github.com/{REPOSITORY}/releases/download/'
            if not url.startswith(expected_prefix):
                raise ValueError('Origem do instalador não reconhecida.')
            digest=asset.get('digest','')
            if not re.fullmatch(r'sha256:[a-fA-F0-9]{64}',digest):
                sums=next((a for a in assets if a.get('name')=='SHA256SUMS.txt'),None)
                if not sums or not sums['browser_download_url'].startswith(expected_prefix):
                    raise ValueError('A publicação ainda não tem a verificação SHA-256.')
                with self._open(sums['browser_download_url']) as response:
                    lines=response.read(64_000).decode('utf-8').splitlines()
                match=next((re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?'+re.escape(asset['name']),line) for line in lines if asset['name'] in line),None)
                if not match:
                    raise ValueError('Não foi possível verificar o instalador.')
                digest='sha256:'+match[1]
            expected=digest.split(':')[1].lower()
            self._folder.mkdir(parents=True,exist_ok=True)
            target=self._folder/asset['name']
            self._set(status='downloading',message='Baixando atualização em segundo plano…')
            part=target.with_suffix('.part')
            sha=hashlib.sha256();count=0
            with self._open(url) as response,part.open('wb') as output:
                while chunk:=response.read(1024*1024):
                    count+=len(chunk)
                    if count>500*1024*1024:
                        raise ValueError('Instalador maior que o limite esperado.')
                    output.write(chunk);sha.update(chunk)
            if sha.hexdigest()!=expected or count!=asset['size']:
                part.unlink(missing_ok=True)
                raise ValueError('O instalador não passou na verificação de integridade. Tente novamente.')
            with part.open('rb') as file:
                executable=file.read(2)==b'MZ'
            if not executable:
                part.unlink(missing_ok=True)
                raise ValueError('Arquivo de instalação inválido.')
            part.replace(target)
            pending=dict(file=target.name,sha256=expected,version=release['tag_name'])
            (self._folder/'pending.json').write_text(json.dumps(pending),encoding='utf-8')
            self._set(status='ready',available=release['tag_name'],message='Atualização pronta. Na bandeja, escolha Sair do Troven Cadastro para instalar.')
        except urllib.error.HTTPError as exc:
            self._set(status='current' if exc.code==404 else 'error',message='Nenhuma atualização publicada ainda.' if exc.code==404 else 'Não foi possível consultar atualizações agora. Seu cadastro continua funcionando.')
        except Exception as exc:
            self._set(status='error',message='Atualização indisponível no momento: '+str(exc))

    def _cache_notes(self,release):
        self._folder.mkdir(parents=True,exist_ok=True)
        path=self._folder/'changelog.json'
        try:notes=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):notes=[]
        version=str(release.get('tag_name','')).lstrip('v')
        if version_tuple(version)==(0,0,0) or not release.get('body'):return
        notes=[n for n in notes if isinstance(n,dict) and n.get('version')!=version]
        notes.append(dict(version=version,title=release.get('name') or 'Novidades da versão '+version,
                          date=str(release.get('published_at',''))[:10],body=release['body'],url=release.get('html_url','')))
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(notes,ensure_ascii=False),encoding='utf-8')
        temporary.replace(path)

    def install_on_exit(self):
        if self._launched or not getattr(sys,'frozen',False):
            return False
        try:
            pending=json.loads((self._folder/'pending.json').read_text(encoding='utf-8'))
            if version_tuple(pending['version'])<=version_tuple(VERSION):
                return False
            installer=self._folder/pending['file']
            if installer.parent.resolve()!=self._folder.resolve() or not installer.name.endswith('.exe'):
                return False
            with installer.open('rb') as file:
                valid=hashlib.file_digest(file,'sha256').hexdigest()==pending['sha256']
            if not valid:
                return False
            quote=lambda s:"'"+str(s).replace("'","''")+"'"
            install_dir=Path(sys.executable).parent
            args=['/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/DIR="'+str(install_dir)+'"','/LOG="'+str(self._folder/'install.log')+'"']
            script=f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue; $result=Start-Process -FilePath {quote(installer)} -ArgumentList @({','.join(quote(a) for a in args)}) -WindowStyle Hidden -PassThru -Wait; exit $result.ExitCode"
            encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
            subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-EncodedCommand',encoded],creationflags=0x08000000,close_fds=True)
            self._launched=True
            return True
        except (OSError,ValueError,KeyError):
            return False
