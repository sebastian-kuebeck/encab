# Example Dockerfile
FROM python:3.10.8-slim-bullseye

# --------------------------------------------
# Install Venv 
#
ENV VIRTUAL_ENV=/opt/encabenv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python3 -m venv $VIRTUAL_ENV && \ 
    pip install --upgrade pip

# --------------------------------------------
# Install Encab 
#
ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

ADD ${ENCAB_WHEEL} .
RUN pip install ${ENCAB_WHEEL}

# --------------------------------------------
# Add app user
# 
RUN adduser runner --gecos "" --disabled-login

# --------------------------------------------
# Add encab config and entrypoint
# 
ADD encab.yml .

ENTRYPOINT ["encab"]