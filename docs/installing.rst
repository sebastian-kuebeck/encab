Installing
==========

Install locally
~~~~~~~~~~~~~~~

1. Prerequisites

-  activated Python virtual environment such as
   `miniconda <https://docs.conda.io/en/latest/miniconda.html>`__ or
   `virtualenv <https://virtualenv.pypa.io/en/latest/>`__,
   Python Version 3.9 or higher.

2. Create sample encab file `encab.yml`

.. code:: yaml

   encab:
      dry_run: false
   programs:
      main:
         sh:
            - echo "Hello Encab!"

3. Run locally:

.. code:: sh

   encab

The result will be something like this:

.. code:: text

   INFO  encab: encab 1.0.1
   INFO  encab: Using configuration file ./encab.yml, source: Default location.
   INFO  main: Hello Encab!
   INFO  main: Exited with rc: 0

Install in Container
~~~~~~~~~~~~~~~~~~~~

1. Prerequisites

-  `Docker <https://www.docker.com/>`__ from your Linux distribution or
   Docker Desktop.

2. Create sample encab file `encab.yml`

.. code:: yaml

   encab:
      dry_run: false
   programs:
      main:
         sh:
            - echo "Hello Encab!"

3. Add Encab to your `Dockerfile`.

.. code:: dockerfile

   FROM python:3.10.8-slim-bullseye
   # --------------------------------------------
   # Install Venv 
   #
   ENV VIRTUAL_ENV=/opt/encabenv
   ENV PATH="$VIRTUAL_ENV/bin:$PATH"
   RUN python3 -m venv $VIRTUAL_ENV && \
      pip install --upgrade pip
   # --------------------------------------------
   # Install Encab 
   #
   RUN pip install encab

   # -------------------------------------------
   # add configuration file
   #
   ADD encab.yml .

   # -------------------------------------------
   # set encab as entrypoint
   ENTRYPOINT ["encab"]

4. Build container

.. code:: sh

   docker build -t encab_minimum .


1. Run container

.. code:: sh

   docker run encab_minimum

Result:

.. code:: text

   INFO  encab: encab 1.0.1
   INFO  encab: Using configuration file ./encab.yml, source: Default location.
   INFO  main: Hello world!
   INFO  main: Exited with rc: 0


From Source
~~~~~~~~~~~

Prerequisites
^^^^^^^^^^^^^

-  `Docker <https://www.docker.com/>`__ from your Linux distribution or
   Docker Desktop.
-  `git <https://git-scm.com/>`__ distributed version control system
-  `Python <https://www.python.org/>`__ Version >= 3.7
-  activated Python virtual environment such as
   `miniconda <https://docs.conda.io/en/latest/miniconda.html>`__ or
   `virtualenv <https://virtualenv.pypa.io/en/latest/>`__


Download
^^^^^^^^

.. code:: sh

      git clone https://github.com/sebastian-kuebeck/encab.git
      cd encab
      pip install -r requirements.txt

Build Wheel
^^^^^^^^^^^

.. code:: sh

      make dist

If all goes well, the encab `wheel
file <https://packaging.python.org/en/latest/tutorials/installing-packages/#source-distributions-vs-wheels>`__
will be in the ``dist`` directory.

It’s named ``encab-<version>-py3-none-any.whl``

Testing (optional)
^^^^^^^^^^^^^^^^^^

Run unit tests:

.. code:: sh

      make test

Running
^^^^^^^

Run localy:

.. code:: sh

      python -m encab

It’ll use the sample ``encab.yml`` file. The result will be something
like this:

.. code:: text

   INFO  encab: encab 1.0.1
   INFO  encab: Using configuration file ./encab.yml, source: Default location.
   INFO  encab: Dry run. No program will be started.
   INFO  encab: settings are valid.
   INFO  encab: settings are valid.
   INFO  encab: settings are valid.
   INFO  encab: Dry run succeeded. Exiting.

Deployment
----------

1. Copy the generated wheel file into your Docker project directory.

2. Create a configuration file ``encab.yml``\ (see Configuration section
   for details).

   .. code:: yaml

         programs:
            main:
               sh: echo 'Hello World'

3. Add Encab to your `Docker
   file <https://docs.docker.com/engine/reference/builder/>`__.

   .. code:: dockerfile

      FROM python:3.10.8-slim-bullseye

      # --------------------------------------------
      # Install Encab 
      #
      ARG ENCAB_WHEEL=encab-1.0.1-py3-none-any.whl

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

4. Build container

   .. code:: sh

      docker build --build-arg ENCAB_WHEEL=`ls encab-*.whl` -t encab_minimum .

5. Run container

   .. code:: sh

      docker run encab_minimum

   Result:

   .. code:: text

      INFO  encab: encab 1.0.1
      INFO  encab: Using configuration file ./encab.yml, source: Default location.
      INFO  main: Hello world!
      INFO  main: Exited with rc: 0
