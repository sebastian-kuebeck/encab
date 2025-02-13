# Example Dockerfile
FROM python:3.10.8-slim-bullseye

RUN apt-get -y -q update && apt-get install -y -q procps

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
ARG ENCAB_WHEEL=encab-1.0.1-py3-none-any.whl

ADD ${ENCAB_WHEEL} .
RUN pip install ${ENCAB_WHEEL} psutil humanize

# --------------------------------------------
# Add app user
# 
RUN addgroup runners
RUN adduser runner --gecos "" --disabled-login
RUN adduser runner runners

#
# Add generator
#
ADD zombie_generator.py .
ADD meter.py .

# --------------------------------------------
# Add encab config and entrypoint
# 
ADD encab.yml .

ENTRYPOINT ["encab"]