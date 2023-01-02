# see: https://hub.docker.com/_/httpd
FROM httpd:2.4

# --------------------------------------------
# Install cron

RUN apt-get -q update && apt-get -y -q install cron tmpreaper

# --------------------------------------------
# Install Encab 
RUN apt-get -y -q install python3-pip python3-venv

ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

ENV PATH=$PATH:/root/.local/bin
RUN python3 -m pip install pipx --user 
ADD ${ENCAB_WHEEL} .

RUN python3 -m pipx install ./${ENCAB_WHEEL}

# --------------------------------------------
# Set up cron job

COPY hello-cron /etc/cron.d/hello-cron
RUN crontab /etc/cron.d/hello-cron

# --------------------------------------------
# Run encab

ADD encab.yml .
ENTRYPOINT ["encab"]
