# see: https://hub.docker.com/_/httpd
FROM httpd:2.4

# --------------------------------------------
# Install cron

RUN apt-get -q update && apt-get -y -q install cron tmpreaper

# --------------------------------------------
# Install pipx
#
RUN echo 'deb http://deb.debian.org/debian bullseye-backports main' > /etc/apt/sources.list.d/backports.list && \
    apt-get -q update && \
    apt-get -y -q install pipx/bullseye-backports
# --------------------------------------------
# Install Encab 
ARG ENCAB_WHEEL=encab-0.0.6-py3-none-any.whl

ADD ${ENCAB_WHEEL} .
ENV PATH=$PATH:/root/.local/bin
RUN pipx install ./${ENCAB_WHEEL}

# --------------------------------------------
# Set up cron job

COPY hello-cron /etc/cron.d/hello-cron
RUN crontab /etc/cron.d/hello-cron

# --------------------------------------------
# Run encab

ADD encab.yml .
ENTRYPOINT ["encab"]
