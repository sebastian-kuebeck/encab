# Example Dockerfile
FROM python:3.10.8-slim-bullseye

ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

ENV PATH=$PATH:/root/.local/bin
RUN python3 -m pip install --user pipx
ADD ${ENCAB_WHEEL} .

RUN python3 -m pipx install ./${ENCAB_WHEEL}

RUN adduser runner --gecos "" --disabled-login

ADD encab.yml .

ENTRYPOINT ["encab"]