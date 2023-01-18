Examples
========


Python Virtualenv
-----------------

Encab config ``encab.yaml``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    programs:
        sleep:
            command: sleep 10
        main:
            user: runner
            command: echo "Test"


Docker file ``Dockerfile``
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: dockerfile

    FROM python:3.10.8-slim-bullseye

    ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

    # --------------------------------------------
    # Create virtual environment

    ENV VIRTUAL_ENV=/opt/encabenv
    RUN python3 -m venv $VIRTUAL_ENV
    ENV PATH="$VIRTUAL_ENV/bin:$PATH"

    RUN pip install --upgrade pip

    # --------------------------------------------
    # Install Encab 

    ADD ${ENCAB_WHEEL} .

    RUN pip install ${ENCAB_WHEEL}

    # --------------------------------------------
    # Add app user

    RUN adduser runner --gecos "" --disabled-login

    # --------------------------------------------
    # Run encab

    ADD encab.yml .

    ENTRYPOINT ["encab"]



Apache + Cron
-------------

Cron File ``hello-cron``
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block::

    * * * * *   echo "Hello $(date)" > /proc/$(cat /var/run/crond.pid)/fd/1 2>&1
    #

Encab config ``encab.yaml``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    programs:
    cron:
        command: cron -f
    main:
        command: httpd-foreground

Docker file ``Dockerfile``
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: dockerfile

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

