import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import updates
from updates import UpdateManager,version_tuple


class Response(io.BytesIO):
    pass


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.home=Path(self.tmp.name)
        self.manager=UpdateManager(self.home)
        self.content=b'MZ'+b'installer-test'*100
        self.asset=dict(name='Troven-Cadastro-Instalador-v10.0.0.exe',size=len(self.content),
            digest='sha256:'+hashlib.sha256(self.content).hexdigest(),
            browser_download_url='https://github.com/TrovenDev/greta-criar-codigos/releases/download/v10.0.0/Troven-Cadastro-Instalador-v10.0.0.exe')
        self.release=dict(tag_name='v10.0.0',assets=[self.asset],draft=False,prerelease=False)

    def tearDown(self):self.tmp.cleanup()

    def responses(self,url):
        return Response(json.dumps(self.release).encode() if '/releases/latest' in url else self.content)

    def test_downloads_and_validates_new_release(self):
        with patch.object(self.manager,'_open',side_effect=self.responses):self.manager.check()
        self.assertEqual(self.manager.snapshot()['status'],'ready')
        self.assertEqual((self.home/'updates'/self.asset['name']).read_bytes(),self.content)

    def test_tampered_download_is_never_prepared(self):
        self.asset['digest']='sha256:'+'0'*64
        with patch.object(self.manager,'_open',side_effect=self.responses):self.manager.check()
        self.assertEqual(self.manager.snapshot()['status'],'error')
        self.assertFalse((self.home/'updates/pending.json').exists())

    def test_current_and_prerelease_do_not_download(self):
        for version,pre in [('v9.0.0',False),('v11.0.0',True)]:
            self.release.update(tag_name=version,prerelease=pre)
            with patch.object(self.manager,'_open',side_effect=self.responses) as request:
                self.manager.check();self.assertEqual(request.call_count,1)
            self.assertEqual(self.manager.snapshot()['status'],'current')

    def test_external_repository_is_rejected(self):
        self.asset['browser_download_url']='https://example.com/installer.exe'
        with patch.object(self.manager,'_open',side_effect=self.responses):self.manager.check()
        self.assertEqual(self.manager.snapshot()['status'],'error')

    def test_installs_only_after_parent_exits_and_preserves_install_path(self):
        with patch.object(self.manager,'_open',side_effect=self.responses):self.manager.check()
        with patch.object(updates.sys,'frozen',True,create=True),patch.object(updates.sys,'executable',str(self.home/'program/Troven Cadastro.exe')),patch.object(updates.subprocess,'Popen') as launch:
            self.assertTrue(self.manager.install_on_exit());self.assertFalse(self.manager.install_on_exit())
            command=launch.call_args.args[0]
            import base64
            script=base64.b64decode(command[-1]).decode('utf-16le')
            self.assertIn('Wait-Process -Id',script)
            self.assertIn('/DIR="'+str(self.home/'program')+'"',script)
            self.assertIn('/VERYSILENT',script)

    def test_changed_installer_cannot_launch(self):
        with patch.object(self.manager,'_open',side_effect=self.responses):self.manager.check()
        (self.home/'updates'/self.asset['name']).write_bytes(b'changed')
        with patch.object(updates.sys,'frozen',True,create=True),patch.object(updates.subprocess,'Popen') as launch:
            self.assertFalse(self.manager.install_on_exit());launch.assert_not_called()

    def test_restart_reopens_only_after_successful_install(self):
        with patch.object(self.manager,'_open',side_effect=self.responses):self.manager.check()
        executable=str(self.home/"Troven's program"/'Troven Cadastro.exe')
        with patch.object(updates.sys,'frozen',True,create=True),patch.object(updates.sys,'executable',executable),patch.object(updates.subprocess,'Popen') as launch:
            self.assertTrue(self.manager.install_on_exit(restart=True))
            import base64
            script=base64.b64decode(launch.call_args.args[0][-1]).decode('utf-16le')
            self.assertIn('if ($result.ExitCode -eq 0)',script)
            self.assertIn(executable.replace("'","''"),script)
            self.assertLess(script.index('-PassThru -Wait'),script.index('if ($result.ExitCode'))
            self.assertIn('Wait-Process -Id',script)

    def test_versions(self):
        self.assertGreater(version_tuple('v10.0.0'),version_tuple('9.10.0'))
        self.assertEqual(version_tuple('v9.0.0-beta'),(0,0,0))
