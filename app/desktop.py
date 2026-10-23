"""Troven Cadastro — interface web local, sem serviços externos."""
import os
import sys
from pathlib import Path
from desktop_api import DesktopAPI


def main():
    mutex = None
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.restype=wintypes.HANDLE
        kernel.CreateMutexW.argtypes=(ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR)
        mutex=kernel.CreateMutexW(None,False,'TrovenCadastroDesktop')
        if ctypes.get_last_error()==183:
            ctypes.windll.user32.FindWindowW.restype=wintypes.HWND
            ctypes.windll.user32.FindWindowW.argtypes=(wintypes.LPCWSTR,wintypes.LPCWSTR)
            ctypes.windll.user32.ShowWindow.argtypes=(wintypes.HWND,ctypes.c_int)
            ctypes.windll.user32.SetForegroundWindow.argtypes=(wintypes.HWND,)
            hwnd=ctypes.windll.user32.FindWindowW(None,'Troven Cadastro')
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd,9)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            else:
                ctypes.windll.user32.MessageBoxW(None,'O Troven Cadastro já está aberto. Use o ícone Troven na bandeja para continuar.','Troven Cadastro',0x40)
            return
    import webview
    base = Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    api = DesktopAPI()
    screen = webview.screens[0]
    window = webview.create_window('Troven Cadastro',str(base/'web/index.html'),js_api=api,
        width=min(1480,screen.width-40),height=min(940,screen.height-80),min_size=(600,440),
        background_color='#F7F5F1',text_select=True,zoomable=True)
    api._window = window
    tray=None
    if sys.platform=='win32':
        from tray import TrayController
        tray=TrayController(window,base/'assets/troven.ico')
        window.events.shown+=tray.start
        def restart_exit():
            from System import Action
            window.native.BeginInvoke(Action(tray.quit))
        api._exit_callback=restart_exit
    if getattr(sys,'frozen',False):
        api._updates.start()
    try:
        webview.start(gui='edgechromium',icon=str(base/'assets/troven.ico'),
                      storage_path=str(api._home/'WebView'),private_mode=True,
                      debug=os.environ.get('TROVEN_DEBUG')=='1')
    finally:
        if tray:tray.stop()
        api._close()
        api._updates.install_on_exit(restart=api._restart_requested)
        if mutex:
            kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
            kernel.CloseHandle(mutex)


if __name__=='__main__':
    try:
        main()
    except Exception:
        import traceback
        report=traceback.format_exc()
        folder=Path(os.environ.get('TROVEN_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Troven'/'Cadastro')
        try:
            folder.mkdir(parents=True,exist_ok=True)
            (folder/'inicializacao.log').write_text(report,encoding='utf-8')
        except OSError:
            pass
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Não foi possível iniciar o Troven Cadastro. Execute novamente o instalador para reparar os componentes.\n\nDetalhes em: '+str(folder/'inicializacao.log'),'Troven Cadastro',0x10)
        else:
            raise
