# Example Dockerfile
FROM debian:bookworm

# --------------------------------------------
# Install uv
#

# The installer requires curl (and certificates) to download the release archive
RUN apt-get -q update && apt-get install -y -q --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

# --------------------------------------------
# Install Encab 
#
ARG ENCAB_WHEEL=encab-1.0.2-py3-none-any.whl

ADD ${ENCAB_WHEEL} .
RUN uv tool install ./${ENCAB_WHEEL}

# --------------------------------------------
# Add app user
# 
RUN adduser runner --gecos "" --disabled-login

# --------------------------------------------
# Add encab config and entrypoint
# 
ADD encab.yml .

ENTRYPOINT ["encab"]