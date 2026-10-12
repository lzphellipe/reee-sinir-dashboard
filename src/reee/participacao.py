"""e-Participação: contribuições do cidadão (sugerir ponto, relatar problema, corrigir dado).

Recebe o formulário do painel, valida e guarda uma linha por contribuição em
JSON Lines. Não pede nem guarda dados pessoais (nome, e-mail, IP): só o tipo,
o município, a referência de local e a descrição, com data e hora.
O arquivo publicado em dados abertos (contribuicoes.csv) é o que o gestor usa
para responder e corrigir o painel.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

TIPOS = (
    "Sugerir novo ponto de coleta",
    "Relatar problema em ponto existente",
    "Corrigir um dado do painel",
    "Solicitar informação (LAI)",
    "Elogio ou comentário",
)
LIMITES = {"municipio": 120, "local": 200, "descricao": 2000}


class ContribuicaoInvalida(ValueError):
    pass


def validar(dados: dict) -> dict:
    if not isinstance(dados, dict):
        raise ContribuicaoInvalida("Formato inválido.")
    tipo = str(dados.get("tipo", "")).strip()
    if tipo not in TIPOS:
        raise ContribuicaoInvalida("Tipo de contribuição inválido.")
    c = {k: " ".join(str(dados.get(k, "")).split())[:n] for k, n in LIMITES.items()}
    if not c["municipio"]:
        raise ContribuicaoInvalida("Informe o município.")
    if len(c["descricao"]) < 10:
        raise ContribuicaoInvalida("Descreva a contribuição em pelo menos 10 caracteres.")
    return {"tipo": tipo, **c, "data": datetime.now(timezone.utc).isoformat(timespec="seconds"), "situacao": "recebida"}


def linha(c: dict) -> bytes:
    return (json.dumps(c, ensure_ascii=False) + "\n").encode("utf-8")


def para_csv(jsonl: bytes) -> bytes:
    """Converte o arquivo JSON Lines em CSV (UTF-8 com BOM, abre direto no Excel)."""
    saida = io.StringIO()
    w = csv.DictWriter(saida, fieldnames=["data", "tipo", "municipio", "local", "descricao", "situacao"], extrasaction="ignore")
    w.writeheader()
    for l in jsonl.decode("utf-8").splitlines():
        if l.strip():
            try:
                w.writerow(json.loads(l))
            except ValueError:
                continue
    return ("﻿" + saida.getvalue()).encode("utf-8")
