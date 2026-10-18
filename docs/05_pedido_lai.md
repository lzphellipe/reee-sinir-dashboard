# Pedido de acesso à informação: endereços dos pontos de recebimento de REEE

O SINIR publica os relatórios anuais das entidades gestoras (ABREE e Green Eletron), mas não os endereços dos pontos de recebimento. Para o painel mostrar onde estão os pontos, a forma limpa de obter esses dados é um pedido pela Lei de Acesso à Informação (Lei nº 12.527/2011), sem raspar os localizadores das entidades.

## Onde enviar

- **Ministério do Meio Ambiente e Mudança do Clima (MMA):** pela plataforma **Fala.BR** (canal oficial do Poder Executivo federal para pedidos de acesso à informação; ver o [manual do Fala.BR](https://www.gov.br/acessoainformacao/pt-br/arquivos/manual_falabr_sic_versao2-defeso.pdf)). O MMA recebe os relatórios anuais dos sistemas de logística reversa e os publica no SINIR.
- **Prefeitura (opcional, por cidade):** pelo serviço de informação ao cidadão (SIC/e-SIC) do município, para os pontos instalados em espaços públicos ou por termo de cooperação.

Prazos e recursos (conferidos no texto da lei em 18/10/2026): resposta em até 20 dias (art. 11, § 1º), prorrogáveis por mais 10 com justificativa (art. 11, § 2º); recurso em 10 dias se o pedido for negado (art. 15). É vedado exigir o motivo do pedido (art. 10, § 3º).

## Modelo 1: MMA (Fala.BR)

> **Assunto:** Endereços dos pontos de recebimento de eletroeletrônicos (Decreto nº 10.240/2020)
>
> Com base na Lei nº 12.527/2011, solicito, em formato aberto (CSV ou planilha), a relação dos pontos de recebimento de produtos eletroeletrônicos de uso doméstico informados ao Ministério pelos sistemas de logística reversa (entidades gestoras e sistemas individuais) no âmbito do Decreto nº 10.240/2020, referente aos anos de 2023, 2024 e 2025, contendo, para cada ponto:
>
> 1. entidade gestora ou empresa responsável;
> 2. município (com código IBGE, se disponível) e UF;
> 3. endereço ou, ao menos, bairro e CEP;
> 4. tipo de ponto (recebimento ou consolidação) e situação (ativo/inativo) em cada ano;
> 5. coordenadas geográficas, se disponíveis.
>
> Caso parte dessas informações não esteja em poder do Ministério, solicito que seja informado qual órgão ou entidade a detém, conforme o art. 11, § 1º, III, da mesma lei. Caso parte seja considerada sigilosa, solicito acesso à parte não sigilosa, conforme o art. 7º, § 2º.

## Modelo 2: Prefeitura (e-SIC municipal)

> **Assunto:** Pontos de entrega de lixo eletrônico no município
>
> Com base na Lei nº 12.527/2011, solicito a relação dos pontos de entrega voluntária (PEVs), ecopontos e demais locais que recebem resíduos de equipamentos eletroeletrônicos no município, com endereço, responsável (prefeitura, entidade gestora ou empresa) e horário de funcionamento, bem como eventuais termos de cooperação firmados com entidades gestoras de logística reversa de eletroeletrônicos. Solicito a resposta em formato aberto (CSV ou planilha), se possível.

## O que fazer com a resposta

Salve a planilha recebida em `data/raw/sinir/relatorios/` e registre o número do protocolo e a data em `fontes.json`. O painel passa a usar os endereços quando o formato for incorporado ao pipeline (`src/reee/relatorios.py`).
