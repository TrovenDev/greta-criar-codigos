# Troven Cadastro

Aplicativo Windows para transformar um Excel de estoque e uma planilha de referências novas em **Grade Lançar.xlsx**. Interface local em HTML/CSS/JavaScript, GSAP e Lottie, com regras de cadastro em Python.

## Usar

Baixe o instalador na seção [Releases](https://github.com/TrovenDev/greta-criar-codigos/releases/latest), execute e abra **Troven Cadastro** pelo menu Iniciar. O atalho na área de trabalho é opcional. Não exige Python nem Excel instalados. Se necessário, o instalador prepara o Microsoft WebView2 com internet.

1. Selecione o estoque atualizado.
2. Importe os produtos novos e escolha as colunas úteis.
3. Confira categorias, códigos, pesos e unidades; exporte a grade.

O tutorial fica dentro do aplicativo e também abre com F1. As fontes, animações e bibliotecas da interface são locais.

## Regras preservadas

- Sequência única entre grupos; variações compartilham o número do modelo.
- Filtro **A cadastrar** inclui novos modelos e novas variações.
- Referências MRS e itens identificados como moissanite na origem exigem grupo de moissanite. Um registro em prata não representa cadastro em moissanite.
- Categoria por referência, escolhas manuais e regras com padrões para lotes grandes.
- Peso positivo informado: G. Sem peso: valor 1 e PC para anéis/outros ou PR para brincos.
- A grade tem 19 colunas. Pais únicos ficam no final, com a unidade das variações, `pesogramas = 0`, `fatconv = 50` e `peso = 0`.
- Unidades conflitantes no mesmo modelo impedem a exportação até a revisão.

## Dados e atualizações

Reservas, regras e último lote: `%LOCALAPPDATA%\Troven\Cadastro\reservas.sqlite3`. Atualizações e desinstalação preservam essa pasta. Para migrar da versão portátil, use **Base e continuidade → Escolher base anterior** e selecione o antigo `reservas.sqlite3`. A importação faz backup da base atual.

O aplicativo consulta as Releases públicas ao abrir, baixa a versão mais nova em segundo plano e confere SHA-256 e tamanho. O instalador é aplicado ao fechar o aplicativo. Falta de internet não interrompe o cadastro. Em **Base e continuidade**, use **Verificar agora** para repetir a consulta. Os dados do cadastro não são enviados ao GitHub.

## Desenvolver e testar

No Windows com Python 3.13:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python -m unittest discover -s app -p "test_*.py"
python app/desktop.py
```

Para isolar os dados durante testes, defina `TROVEN_DATA_DIR` para uma pasta temporária. Alguns testes de comparação com os arquivos originais são ignorados quando esses arquivos não estão disponíveis; planilhas reais não integram o repositório.

```powershell
python scripts/build_windows.py
```

O script baixa e valida as ferramentas oficiais, empacota o aplicativo, gera o instalador em `dist/` e escreve `SHA256SUMS.txt`. Os fontes dos componentes ficam em `app/`; o instalador está em `installer/`.

## Publicar uma atualização

1. Atualize `VERSION` em `app/version_info.py` e implemente a mudança.
2. Faça commit e push em `main`; o GitHub Actions executa testes e gera um instalador de revisão.
3. Após revisar, crie e envie a tag correspondente, por exemplo `v9.0.1`.
4. O workflow gera o instalador e publica a Release e seu SHA-256. As instalações detectam essa versão na próxima abertura.

Um push de código sem uma nova tag não distribui uma versão aos usuários. Não republique a mesma versão para mudanças de comportamento.

## Componentes

Identidade oficial: [Troven](https://marca.troven.com.br/). Inter e Unbounded: SIL OFL. Lottie-web: MIT. GSAP: [licença padrão](https://gsap.com/standard-license/). A composição Lottie geométrica é original do aplicativo. Licenças e metadados acompanham os arquivos em `app/web/vendor` e `app/web/assets`. Instalador: Inno Setup 6.4.3.

Planilhas, bases locais, executáveis, credenciais e arquivos de build são ignorados pelo Git.
