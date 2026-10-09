"""Procura menções a eletroeletrônicos / logística reversa nas planilhas baixadas do SINIR.

Diferente do inventário (que só olha os nomes das colunas), este script olha
também o CONTEÚDO das células, para achar tabelas em que o tipo de resíduo
aparece nas linhas (ex.: coluna "Tipo de resíduo" = "Eletroeletrônicos").

Uso (na raiz do projeto):
    python scripts/procurar_reee.py
    python scripts/procurar_reee.py 2023          # só um ano
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from reee.extract import ler_tabela  # noqa: E402
from reee.utils import normalizar_texto  # noqa: E402

PADRAO = re.compile(r"eletroeletr|eletro eletr|\breee\b|eletronic|lixo eletron|logistica reversa|\bpev\b|ponto de entrega")


def main() -> None:
    pasta = RAIZ / "data" / "raw" / "sinir" / "extraido"
    anos = sys.argv[1:] or sorted(p.name for p in pasta.iterdir() if p.is_dir())
    achou = False
    for ano in anos:
        for arq in sorted((pasta / ano).rglob("*")):
            if arq.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
                continue
            try:
                df = ler_tabela(arq).drop(columns=["_arquivo", "_ano_arquivo"])
            except Exception as e:  # noqa: BLE001
                print(f"[{ano}] {arq.name}: não abriu ({e})")
                continue
            for col in df.columns:
                no_nome = bool(PADRAO.search(normalizar_texto(col)))
                valores = df[col].dropna().astype(str)
                hits = valores[valores.map(lambda v: bool(PADRAO.search(normalizar_texto(v))))]
                if no_nome or len(hits):
                    achou = True
                    onde = "NOME DA COLUNA" if no_nome else f"{len(hits)} célula(s)"
                    exemplos = "; ".join(sorted(set(h[:80] for h in hits))[:5])
                    print(f"[{ano}] {arq.name} | coluna '{col}' | {onde}" + (f" | ex.: {exemplos}" if exemplos else ""))
                    if len(hits):
                        print(f"        colunas do arquivo: {list(df.columns)[:25]}")
    if not achou:
        print("Nenhuma menção a eletroeletrônicos ou logística reversa nas planilhas baixadas.")


if __name__ == "__main__":
    main()
