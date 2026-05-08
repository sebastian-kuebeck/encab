FROM python:3.14.4-slim-trixie

# --------------------------------------------
# Install Encab 
#
ENV PATH=$PATH:/root/.local/bin
ARG ENCAB_WHEEL=encab-1.0.5-py3-none-any.whl
ADD ${ENCAB_WHEEL} .
RUN pip install ./${ENCAB_WHEEL} --user

# -------------------------------------------
# add configuration file
#
ADD encab.yml .

# -------------------------------------------
# set encab as entrypoint
ENTRYPOINT ["encab"]
