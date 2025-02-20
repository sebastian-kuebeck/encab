Examples
========

Minimum Example
---------------

``Dockerfile``:

.. code:: dockerfile

    FROM python:3.10.8-slim-bullseye

    # --------------------------------------------
    # Install Encab 
    #
    ENV PATH=$PATH:/root/.local/bin
    RUN pip install encab --user

    # -------------------------------------------
    # add configuration file
    #
    ADD encab.yml .

    # -------------------------------------------
    # set encab as entrypoint
    ENTRYPOINT ["encab"]

``config.yml``:

.. code:: yaml

    programs:
        main:
            command: echo "Hello world!"

Pipx Example
------------

`pipx <https://pypa.github.io/pipx/>`__ is a great tool to install Python tools in a non Python container.

``Dockerfile``:

.. code:: dockerfile

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
    ENV PATH=$PATH:/root/.local/bin
    RUN pipx install encab

    # --------------------------------------------
    # Add app user
    # 
    RUN adduser runner --gecos "" --disabled-login

    # --------------------------------------------
    # Add encab config and entrypoint
    # 
    ADD encab.yml .

    ENTRYPOINT ["encab"]

As a general rule, applications inside a container should not run as root, 
especially if they communicate with the outside world.

In this example, the script is run under a different user...

``config.yml``:

.. code:: yaml

    programs:
        main:
            user: runner
            command: echo "Hello world!"

Uv Example
----------

`uv <https://github.com/astral-sh/uv>`__ is a fast, lightweight pip and pipx replacement written in rust.

``Dockerfile``:

.. code:: dockerfile

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

    RUN uv tool install encab

    # --------------------------------------------
    # Add app user
    # 
    RUN adduser runner --gecos "" --disabled-login

    # --------------------------------------------
    # Add encab config and entrypoint
    # 
    ADD encab.yml .

    ENTRYPOINT ["encab"]

Apache + Cron Job Example
-------------------------

This example uses a Debian based Apache image and
installs cron and tempreaper.
`tempreaper <https://manpages.ubuntu.com/manpages/jammy/man8/tmpreaper.8.html>`__ is a tool 
that removes temporary files on a regular basis. The tempreaper process itself is run by cron.

In addition to tempreaper, we want add the following entry to crontab...


``hello-cron``:

.. code:: text

    * * * * *   echo "Hello $(date)" > /proc/$(cat /var/run/crond.pid)/fd/1 2>&1

``Dockerfile``:

.. code:: dockerfile

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
    RUN pipx install encab

    # --------------------------------------------
    # Set up cron job

    COPY hello-cron /etc/cron.d/hello-cron
    RUN crontab /etc/cron.d/hello-cron

    # --------------------------------------------
    # Run encab

    ADD encab.yml .
    ENTRYPOINT ["encab"]

``config.yml``:

.. code:: yaml

    encab:
        halt_on_exit: False
        debug: False
    programs:
        cron:
            command: cron -f
        main:
            command: httpd-foreground

Output...

.. code:: text

    INFO  encab: encab 1.0.1
    INFO  encab: Using configuration file ./encab.yml, source: Default location.
    ERROR main: AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 172.17.0.2. Set the 'ServerName' directive globally to suppress this message
    ERROR main: AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 172.17.0.2. Set the 'ServerName' directive globally to suppress this message
    ERROR main: [Wed May 24 12:39:55.123607 2023] [mpm_event:notice] [pid 12:tid 140407144078656] AH00489: Apache/2.4.54 (Unix) configured -- resuming normal operations
    ERROR main: [Wed May 24 12:39:55.124088 2023] [core:notice] [pid 12:tid 140407144078656] AH00094: Command line: 'httpd -D FOREGROUND'
    INFO  cron: Hello Wed May 24 12:40:01 UTC 2023
    INFO  cron: Hello Wed May 24 12:41:01 UTC 2023