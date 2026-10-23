# Empresas e modelos de cadastro

Abra **Empresas e modelos** no menu lateral. O modelo inicial Troven traz faixa etária, estilo, pedra, gênero e tema, todos opcionais e com preenchimento livre.

## Personalizar a empresa

Em **Editar atributos**, altere o nome, crie novos atributos e escolha quais são obrigatórios. Para oferecer uma lista de opções, separe os valores por `|`, como `Adulto | Infantil`. Sem opções, o campo aceita texto livre.

**Nova empresa / modelo** cria outra configuração a partir dos atributos atuais. Cada modelo mantém os seus valores de descrição e atributos para os produtos do lote. Os modelos compartilham a base de estoque e a sequência de códigos; não são bases independentes de empresas.

Renomear um atributo preserva seus valores. Ao retirar um atributo, ele deixa de aparecer no cadastro; os dados antigos continuam no lote. Um atributo usado por um formato personalizado deve ser removido das colunas desse formato antes de ser retirado do modelo.

## Preencher produtos

Selecione o modelo da empresa acima da tabela de produtos **antes de importar**. A janela de importação oferece a descrição e os atributos ativos no mapeamento das colunas.

Use o botão de características na linha para editar um produto. Para preencher muitos produtos de uma vez, selecione-os e clique em **Descrição e atributos**. Marque os campos que deseja aplicar. A opção **Substituir valores** permite atualizar ou apagar valores existentes. Sem ela, apenas os campos vazios são preenchidos.

Ative **Aplicar também às variações** para usar os mesmos valores nos itens do mesmo modelo e categoria. A descrição é escrita ou importada, sem geração automática de texto.

O filtro **Cadastro incompleto** encontra produtos que precisam de descrição ou atributos obrigatórios. As pendências também aparecem na tabela. O arquivo não é exportado enquanto houver pendências nos produtos marcados para exportação.

## Escolher um formato

- **Grade Lançar · padrão ERP** mantém as 19 colunas. A descrição escrita preenche `aaa_descricao` quando informada; sem ela, permanece o identificador técnico. Os atributos extras não são acrescentados a esse formato fixo.
- **Cadastro completo · com atributos** oferece uma saída inicial com código, referência, descrição, identificador técnico, peso, unidade, categoria, foto, código pai, tipo de linha e os atributos ativos.
- **Criar formato** permite definir os cabeçalhos, a ordem e a informação de cada coluna. Use as setas para reordenar e **Valor fixo** para repetir um conteúdo em todas as linhas. As origens `aaa_*` fornecem os valores segundo as regras do ERP.

Os formatos personalizados podem incluir os pais no final ou apenas as variações. Pais recebem descrições e atributos comuns a todas as variações exportadas daquele pai; valores diferentes ficam vazios. Na Grade Lançar padrão, o pai sem descrição comum usa seu identificador técnico.

Todos os formatos validam os códigos, a compatibilidade com moissanite e as unidades dos pais. O formato personalizado define o conteúdo do arquivo; sua compatibilidade com o ERP deve ser adaptada aos cabeçalhos esperados por ele. Confira **Ver prévia da grade** antes de exportar.

## Fotos: busca e destino

A pasta escolhida em **Vincular fotos** serve para localizar os arquivos. Na planilha, o destino é fixo:

```text
C:\DevMaster\dados\imagens\produtos\NOME-DO-ARQUIVO
```

Exemplo: ao encontrar `97089318TOP.jpg` em uma pasta de busca, a coluna de foto recebe `C:\DevMaster\dados\imagens\produtos\97089318TOP.jpg`. O aplicativo não copia os arquivos para esse destino. Sem foto encontrada, o campo fica vazio. O pai usa uma imagem com o código do próprio pai.

## Variações

A geração das variações continua usando o fluxo atual de tamanho e cor. Esta versão acrescenta atributos de cadastro e formatos de exportação, sem criar novas dimensões para gerar códigos.

## Importar o próximo estoque com descrições escritas

O Cadastro completo inclui **Identificador técnico** para preservar grupo, sequência e variação. Essa coluna tem prioridade sobre a descrição ao ler o estoque. Um relatório com `aaa_refbase` também permite reconstruir o identificador a partir do código.

Quando o código e a referência já constam das reservas locais, o sistema reconhece seu identificador automaticamente. Se não houver reservas nem informação explícita da sequência, a importação pede a coluna técnica: não tenta adivinhar números a partir de um nome escrito.

O atributo **Pedra**, quando preenchido com moissanite, também exige uma categoria compatível antes de exportar.
