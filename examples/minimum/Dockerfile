FROM python:3.10.8-slim-bullseye

# --------------------------------------------
# Install Encab 
#
ENV PATH=$PATH:/root/.local/bin
ARG ENCAB_WHEEL=encab-1.0.2-py3-none-any.whl
ADD ${ENCAB_WHEEL} .
RUN pip install ./${ENCAB_WHEEL} --user

# -------------------------------------------
# add configuration file
#
ADD encab.yml .

# -------------------------------------------
# set encab as entrypoint
ENTRYPOINT ["encab"]
