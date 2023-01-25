
Encab: A Docker Entrypoint Tool 
===============================

Encab is essentially a replacement for complex, hand-written Docker Container Entrypoint scripts,
especially when dockerizing complex legacy applications.

Add it as your `Dockerfile Entrypoint`_, 
together with the encab configuration file ``encab.yml``,

.. _`Dockerfile Entrypoint`: https://docs.docker.com/engine/reference/builder/#entrypoint

.. code-block:: dockerfile

   ...
   ADD encab.yml .
   ENTRYPOINT ["encab"]

define what you want to run in your container in ``encab.yml``,

.. code-block:: yaml

   programs:
   cron:
      command: cron -f
   main:
      command: httpd-foreground

and encab cares for the rest.
Run it and you'll always know who's logging what...

.. code-block::

   INFO  encab: encab 0.0.1
   INFO  encab: Using configuration file ./encab.yml, source: Default location.
   ERROR main: AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 172.17.0.2. Set the 'ServerName' directive globally to suppress this message
   ERROR main: AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 172.17.0.2. Set the 'ServerName' directive globally to suppress this message
   ERROR main: [Wed Jan 18 09:47:12.417275 2023] [mpm_event:notice] [pid 12:tid 140142563044672] AH00489: Apache/2.4.54 (Unix) configured -- resuming normal operations
   ERROR main: [Wed Jan 18 09:47:12.417830 2023] [core:notice] [pid 12:tid 140142563044672] AH00094: Command line: 'httpd -D FOREGROUND'
   INFO  cron: Hello Wed Jan 18 09:48:01 UTC 2023

It shares some similarities with `supervisord`_ which I've used before I wrote encab but
supervisord is a process controll system not designed to run in a Container environment.

.. _`supervisord`: http://supervisord.org/


.. note::

   This tool is still under development. Sufficient for local experiments but not mature enough for
   production use!

Features
~~~~~~~~

- run multiple programs in a container at a time with transparent logging
- run programs as different users
- handle environment variables in a more flexible way
- simplify container debugging
- simplify container debugging
- load, build, validate environment variables

Narrative Documentation
-----------------------

.. toctree::
   :maxdepth: 2

   installing.rst
   configuration.rst
   examples.rst

API Documentation
-----------------

.. toctree::
   :maxdepth: 2

   api.rst

Indices and Tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
