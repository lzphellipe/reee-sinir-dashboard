import os

import pytest

from reee import config as C

# testes sobem servidores em 127.0.0.1; garante que não passem por proxy
for v in ("NO_PROXY", "no_proxy"):
    os.environ[v] = ",".join(filter(None, [os.environ.get(v), "127.0.0.1", "localhost"]))

# Intervalo dos dados de teste (relatórios desde 2019 e planilhas de 2021 a 2025).
INTERVALO_TESTES = (2019, 2025)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "recorte(inicio, fim): roda o teste com ANO_INICIAL/ANO_FINAL nesse intervalo "
        "(padrão: 2019–2025, independente do config.py)")


@pytest.fixture(autouse=True)
def recorte_de_anos(request, monkeypatch):
    """Fixa o intervalo de anos de cada teste.

    O config.py pode ter outro recorte (ex.: ANO_INICIAL = 2023 para publicar só 2023–2025).
    Os testes usam dados de 2019 a 2025, então rodam nesse intervalo, a menos que peçam
    outro com @pytest.mark.recorte(inicio, fim).
    """
    marca = request.node.get_closest_marker("recorte")
    inicio, fim = marca.args if marca else INTERVALO_TESTES
    monkeypatch.setattr(C, "ANO_INICIAL", inicio)
    monkeypatch.setattr(C, "ANO_FINAL", fim)
    monkeypatch.setattr(C, "ANOS", list(range(inicio, fim + 1)))
    return inicio, fim
