# Example Dockerfile
FROM debian:trixie

# --------------------------------------------
# Install pipx
#
RUN apt-get -q update && apt-get -y -q install pipx
# --------------------------------------------
# Install Encab 
#
ARG ENCAB_WHEEL=encab-1.0.5-py3-none-any.whl

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