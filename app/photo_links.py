"""Vínculo por nome exato do arquivo: código do produto + extensão da foto."""
import json
from pathlib import Path,PureWindowsPath
from criar_codigos import product_parts

DEFAULT_FOLDER=r'C:\DevMaster\dados\imagens\produtos'
EXTENSIONS={'.jpg':0,'.jpeg':1,'.png':2,'.webp':3}


class PhotoLinks:
    def __init__(self,home):
        self._file=Path(home)/'photos.json'
        self.enabled=False
        self.folder=DEFAULT_FOLDER
        self._signature=None
        self._index={}
        self.error=''
        try:
            config=json.loads(self._file.read_text(encoding='utf-8'))
            self.enabled=bool(config.get('enabled',False))
            self.folder=str(config.get('folder') or DEFAULT_FOLDER)
        except (OSError,ValueError,TypeError):pass

    def configure(self,folder,enabled=True):
        directory=Path(folder).expanduser()
        if enabled and not directory.is_dir():
            raise ValueError('Pasta de fotos não encontrada. Escolha a pasta que contém os arquivos das imagens.')
        self.enabled=bool(enabled)
        self.folder=str(directory)
        self._signature=None
        self._file.write_text(json.dumps(dict(enabled=self.enabled,folder=self.folder),ensure_ascii=False),encoding='utf-8')

    def _scan(self,force=False):
        directory=Path(self.folder)
        stat=directory.stat()
        signature=(str(directory),stat.st_mtime_ns)
        if not force and signature==self._signature:return
        index={}
        for path in directory.iterdir():
            if path.suffix.lower() in EXTENSIONS and path.is_file():
                index.setdefault(path.stem.casefold(),[]).append(path)
        self._index=index
        self._signature=signature

    def find(self,code):
        files=self._index.get(str(code).casefold(),[])
        if not files:return '',False
        rank=min(EXTENSIONS[p.suffix.lower()] for p in files)
        best=[p for p in files if EXTENSIONS[p.suffix.lower()]==rank]
        return (str(PureWindowsPath(DEFAULT_FOLDER)/best[0].name),False) if len(best)==1 else ('',True)

    def apply(self,rows,strict=False,force=False):
        self.error=''
        if self.enabled:
            try:self._scan(force)
            except OSError:
                self.error='A pasta de fotos não está disponível. Escolha outra pasta ou desative o vínculo para exportar sem fotos.'
                if strict:raise ValueError(self.error)
        for row in rows:
            row['foto']=row['foto_pai']=''
            row['foto_status']='Desativado' if not self.enabled else 'Pasta indisponível' if self.error else 'Sem foto'
            if not self.enabled or self.error:continue
            code=row.get('codigo','')
            if not code:
                row['foto_status']='Aguardando código';continue
            row['foto'],ambiguous=self.find(code)
            row['foto_status']='Mais de uma foto' if ambiguous else 'Encontrada' if row['foto'] else 'Sem foto'
            if parts:=product_parts(row.get('produto','')):
                row['foto_pai']=self.find(parts[0]+parts[2])[0]
        return self.summary(rows)

    def summary(self,rows):
        return dict(enabled=self.enabled,folder=self.folder,export_folder=DEFAULT_FOLDER,error=self.error,
                    found=sum(bool(r.get('foto')) for r in rows),
                    missing=sum(bool(r.get('codigo')) and not r.get('foto') for r in rows),
                    parents=len({r['foto_pai'] for r in rows if r.get('foto_pai')}),
                    ambiguous=sum(r.get('foto_status')=='Mais de uma foto' for r in rows))
