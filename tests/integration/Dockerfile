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
ARG ENCAB_WHEEL=encab-0.0.6-py3-none-any.whl

ADD ${ENCAB_WHEEL} .
RUN pip install ${ENCAB_WHEEL} psutil humanize

# --------------------------------------------
# Add app user
# 
RUN addgroup runners
RUN adduser runner --gecos "" --disabled-login
RUN adduser runner runners

#
# Add tests & co
#
ADD *_itest.py ./
ADD load.py .
ADD .env .

# --------------------------------------------
# Add encab config and entrypoint
# 
ADD encab.yml .

ENTRYPOINT ["encab"]