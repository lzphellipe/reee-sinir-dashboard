"""Atalho para abrir o painel sem configurar nada.

    python iniciar.py                      # abre o painel (atualiza os dados se preciso)
    python iniciar.py --sem-atualizar      # só abre, com os dados que já estão no projeto
    python iniciar.py pipeline --coletar   # roda só o pipeline

Funciona de qualquer pasta: o próprio script coloca src/ no caminho do Python.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pipeline":
        sys.argv.pop(1)
        from reee.pipeline import main
    else:
        from reee.servidor import main
    main()
