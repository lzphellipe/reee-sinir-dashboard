import os

# testes sobem servidores em 127.0.0.1; garante que não passem por proxy
for v in ("NO_PROXY", "no_proxy"):
    os.environ[v] = ",".join(filter(None, [os.environ.get(v), "127.0.0.1", "localhost"]))
