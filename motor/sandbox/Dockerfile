# Imagem de execução do sandbox do motor.
#
# Existe porque o sandbox roda com `--network none` -- e isso é deliberado, é o
# que faz o isolamento valer. A consequência é que `pip install` NÃO existe em
# tempo de execução: toda dependência que o código gerado precisar tem que estar
# aqui dentro, assada agora.
#
# Sem esta imagem, portão de processo só alcança biblioteca padrão, ou seja, a
# minoria do software que vale a pena construir. Com ela, "software verificado"
# passa a valer para código que fala HTTP e tem suíte de testes de verdade.
#
# A base é fixada por digest: tag é mutável, e trocar a base por baixo mudaria o
# que toda evidência de execução significa sem ninguém perceber.
FROM python@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Raiz read-only em runtime: o cache do Python não tem onde escrever e cada
# import pagaria a recompilação. Pré-compilar aqui evita isso e, de quebra,
# falha o BUILD se alguma dependência veio quebrada.
RUN python -m compileall -q /usr/local/lib/python3.13/site-packages

# `PYTHONDONTWRITEBYTECODE`: sem isso o interpretador tenta escrever .pyc em
# diretório read-only a cada execução e polui stderr de todo portão.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
