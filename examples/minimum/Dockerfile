FROM python:3.10.8-slim-bullseye

# --------------------------------------------
# Install Encab 
#
ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

ENV PATH=$PATH:/root/.local/bin
RUN python3 -m pip install --user pipx
ADD ${ENCAB_WHEEL} .
RUN python3 -m pipx install ./${ENCAB_WHEEL}

# -------------------------------------------
# add configuration file
#
ADD encab.yml .

# -------------------------------------------
# set encab as entrypoint
ENTRYPOINT ["encab"]
