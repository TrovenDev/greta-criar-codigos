"""Bandeja nativa do Windows, usando o mesmo loop WinForms do WebView2."""
import logging


class TrayController:
    def __init__(self,window,icon_path):
        self.window=window
        self.icon_path=str(icon_path)
        self._icon=None
        self._menu=None
        self._image=None
        self._ready=False
        self._exiting=False
        self._notified=False
        self._restore_state=None

    def start(self):
        try:
            from System import Action
            self.window.native.Invoke(Action(self._create))
        except Exception:
            # Nunca oculta uma janela se o ícone não pôde ser criado.
            logging.exception('Não foi possível preparar a bandeja do Troven.')

    def _create(self):
        if self._ready:return
        from System.Drawing import Icon
        from System.Windows.Forms import NotifyIcon,ContextMenuStrip,ToolStripMenuItem,ToolStripSeparator,FormWindowState
        self._image=Icon(self.icon_path)
        self._menu=ContextMenuStrip()
        self._open=ToolStripMenuItem('Abrir Troven Cadastro')
        self._open.Click+=self.restore
        self._quit=ToolStripMenuItem('Sair do Troven Cadastro')
        self._quit.Click+=self.quit
        self._menu.Items.Add(self._open)
        self._menu.Items.Add(ToolStripSeparator())
        self._menu.Items.Add(self._quit)
        self._icon=NotifyIcon()
        self._icon.Icon=self._image
        self._icon.Text='Troven Cadastro — clique para abrir'
        self._icon.ContextMenuStrip=self._menu
        self._icon.MouseClick+=self._click
        self._icon.Visible=True
        self._restore_state=FormWindowState.Normal
        self.window.native.FormClosing+=self._closing
        self.window.native.Resize+=self._resize
        self.window.native.FormClosed+=self._closed
        self._ready=True

    def _click(self,sender,event):
        from System.Windows.Forms import MouseButtons
        if event.Button==MouseButtons.Left:self.restore()

    def _hide(self):
        if not self._ready or self._exiting:return
        self.window.native.Hide()
        if not self._notified:
            from System.Windows.Forms import ToolTipIcon
            self._icon.ShowBalloonTip(3500,'Troven continua aberto','Clique no ícone para voltar. Para encerrar, use o botão direito e escolha Sair.',ToolTipIcon.Info)
            self._notified=True

    def _closing(self,sender,event):
        from System.Windows.Forms import CloseReason
        if self._exiting or event.CloseReason!=CloseReason.UserClosing:return
        if self._ready:
            event.Cancel=True
            self._hide()

    def _resize(self,sender,event):
        from System.Windows.Forms import FormWindowState
        current=self.window.native.WindowState
        if current==FormWindowState.Minimized:self._hide()
        else:self._restore_state=current

    def restore(self,*args):
        if self._exiting:return
        self.window.native.Show()
        if self._restore_state is not None:self.window.native.WindowState=self._restore_state
        self.window.native.Activate()

    def quit(self,*args):
        self._exiting=True
        self.window.native.Close()

    def _closed(self,*args):
        self._exiting=True
        self._dispose()

    def _dispose(self):
        self._ready=False
        if self._icon is not None:
            self._icon.Visible=False
            self._icon.Dispose()
            self._icon=None
        if self._menu is not None:
            self._menu.Dispose();self._menu=None
        if self._image is not None:
            self._image.Dispose();self._image=None

    def stop(self):
        if self._icon is None:return
        from System import Action
        native=self.window.native
        if native is not None and native.IsHandleCreated and not native.IsDisposed:
            native.Invoke(Action(self._dispose))
        else:self._dispose()
