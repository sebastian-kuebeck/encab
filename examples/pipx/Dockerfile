# Example Dockerfile
FROM debian:bullseye

# --------------------------------------------
# Install pipx
#
RUN echo 'deb http://deb.debian.org/debian bullseye-backports main' > /etc/apt/sources.list.d/backports.list && \
    apt-get -q update && \
    apt-get -y -q install pipx/bullseye-backports
# --------------------------------------------
# Install Encab 
#
ARG ENCAB_WHEEL=encab-1.0.2-py3-none-any.whl

ADD ${ENCAB_WHEEL} .
ENV PATH=$PATH:/root/.local/bin
RUN pipx install ./${ENCAB_WHEEL}

# --------------------------------------------
# Add app user
# 
RUN adduser runner --gecos "" --disabled-login

# --------------------------------------------
# Add encab config and entrypoint
# 
ADD encab.yml .

ENTRYPOINT ["encab"]