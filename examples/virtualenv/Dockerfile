# Example Dockerfile
FROM python:3.10.8-slim-bullseye

ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

ENV VIRTUAL_ENV=/opt/encabenv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip
ADD ${ENCAB_WHEEL} .

RUN pip install ${ENCAB_WHEEL}

RUN adduser runner --gecos "" --disabled-login

ADD encab.yml .

ENTRYPOINT ["encab"]