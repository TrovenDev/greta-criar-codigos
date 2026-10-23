# Microsoft WebView2 Bootstrapper

`webview2-bootstrapper.bin` é a cópia sem alterações do instalador oficial
Microsoft WebView2 Evergreen Bootstrapper, renomeada apenas para armazenamento.
Versão do arquivo: 1.3.299.15. Assinatura Authenticode Microsoft Corporation
conferida como válida na obtenção. O build valida o SHA-256 fixado em
`scripts/build_windows.py` e grava o arquivo com extensão `.exe` para o Inno Setup.

Fonte: https://go.microsoft.com/fwlink/p/?LinkId=2124703

Distribuição com o aplicativo, conforme a documentação oficial:
https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution

Esse componente pertence à Microsoft e é executado pelo instalador somente
quando o WebView2 Runtime ainda não está disponível. Pode precisar de internet
para preparar o Runtime. Não é o executável do Troven Cadastro.
