"""Histórico disponível offline e notas recebidas das Releases oficiais."""
import json
from pathlib import Path
from version_info import VERSION
from updates import version_tuple


def changelog(home):
    notes={}
    for path in (Path(__file__).parent/'web/changelog.json',Path(home)/'updates/changelog.json'):
        try:
            for item in json.loads(path.read_text(encoding='utf-8')):
                version=str(item.get('version','')).lstrip('v')
                if version_tuple(version)!=(0,0,0) and version_tuple(version)<=version_tuple(VERSION):
                    notes[version]=dict(item,version=version)
        except (OSError,ValueError,TypeError,AttributeError):pass
    seen=Path(home)/'changelog-seen.txt'
    try:last=seen.read_text(encoding='utf-8').strip()
    except OSError:last=''
    return dict(current=VERSION,unread=last!=VERSION,entries=sorted(notes.values(),key=lambda n:version_tuple(n['version']),reverse=True))


def mark_seen(home):
    (Path(home)/'changelog-seen.txt').write_text(VERSION,encoding='utf-8')
