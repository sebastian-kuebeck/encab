# see: https://hub.docker.com/_/httpd
FROM httpd:2.4

# --------------------------------------------
# Install cron

RUN apt-get -q update && apt-get -y -q install cron tmpreaper

# --------------------------------------------
# Install Encab 
RUN apt-get -y -q install python3-pip

ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

ADD ${ENCAB_WHEEL} .

ENV PATH=$PATH:/root/.local/bin
RUN pip install ./${ENCAB_WHEEL} --user

# --------------------------------------------
# Set up cron job

COPY hello-cron /etc/cron.d/hello-cron
RUN crontab /etc/cron.d/hello-cron

# --------------------------------------------
# Run encab

ADD encab.yml .
ENTRYPOINT ["encab"]
