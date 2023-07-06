Configuration
=============

Location
~~~~~~~~

At first, encab tries to load the configuration from the environment
variable ``ENCAB_CONFIG``. If this variable is not set, it looks at the
following locations in the file system:

-  ``./encab.yml``
-  ``./encab.yaml``
-  ``/etc/encab.yml``
-  ``/etc/encab.yaml``

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

All Variables are optional.

-  ``ENCAB_CONFIG``: the encab configuration
-  ``ENCAB_DRY_RUN``: overrides ``encab/dry_run`` in the encab
   configuration. 0: Dry run is disbaled 1: Dry run is enabled

Contents
~~~~~~~~

``encab`` (Map, optional)
^^^^^^^^^^^^^^^^^^^^^^^^^

Contains all static settings to start a program

-  ``halt_on_exit``: bool, optional

   halt on exit: if ``true``, encab is halted after the main program
   ends. Default: ``false``

-  ``logformat``: string, optional

   Custom log format
   `link <https://docs.python.org/3/library/logging.html#logrecord-attributes>`__.
   The attribute ``program`` contains the program name.

   Default: ``%(levelname)-5.5s %(program)s: %(message)s``

-  ``dry_run``: bool, optional

   ``true``: the configuration is checked but no program is started
   Default: ``false``

Common config for encab and programs section

-  ``environment``: Map, optional

   additional environmment variables speciefied as a map.

   Example:

   .. code:: yaml

       environment:
           PYTHONPATH: /opt/app
           PATH: /usr/bin:/usr/local/bin

-  ``debug``: Optional[bool] if true, encab logs debug information.
   Default: false

-  ``loglevel``: Optional[Union[str, int]]

   the log level. One of ``CRITICAL``, ``FATAL``, ``ERROR``, ``WARN``,
   ``WARNING``, ``INFO``, ``DEBUG``

-  ``umask``: Optional[Union[str, int]]

   the
   `umask <https://pubs.opengroup.org/onlinepubs/9699919799/utilities/umask.html>`__,
   either as octal string (e.g. “077”) or integer

-  ``user``: Optional[Union[str, int]] the user id or user name

-  ``join_time``: Optional[float]

   The join time is the time in seconds encab waits for a program to
   start/shutdown before it continues with the next. Default: 1 seconds.

Example:

.. code:: yaml

   encab:
       halt_on_exit: false # halt execution if main exits
       logformat: "%(levelname)-5.5s %(program)s: %(message)s" # custom log format
       dry_run: true # dry run only
       debug: false # no debug output
       environment: # additional environment variables
           PYTHONPATH: /opt/app

``extensions`` (Map, optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

maps **extension names** to **extension configurations**.

There are two types of extension:

- Built in extensions

- External extensions

Build in are identified by the **extension** name whereas 
external extensions are identified by their **python module name**.

Currently, there are the following build in Extensions:

- log_satnitizer
- startup_script
- validation

Extension Configuration (Map, optional)
'''''''''''''''''''''''''''''''''''''''

-  ``enabled``: Optional[bool] True: the extension is enabled

    Wether or not an extension is enabled by default is determined by the extension itself.
    For built in extensions, only the log_satnitizer extension is enabled by default.

-  ``module``: Optional[str] The extension module name

    Specifies the python module name for external extension.

-  ``settings``: Optional[Dict[str, Any]] Map with extension specific settings

Example:

.. code:: yaml

   extensions:
       log_sanitizer:
           enabled: true
           settings:
               override: false
               patterns: 
                   - "*MAGIC*"
       startup_script:
           enabled: true
           settings:
               buildenv: 
                   - echo 'X=1' 
                   - echo 'Z=3'
       validation:
           enabled: true
           settings:
               variables:
                   secret_a:
                       required: true

``programs`` (Map, optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

maps **program names** to **program configurations**.

The program named ``main`` is the main program in the configuration. All
other programs are started *before* ``main`` and ended *after* ``main``.

The command in ``main`` can be overridden by command line arguments,
where the first arguments represents the command name and the following
it’s parameters.

Example:

``encab.yml``:

.. code:: yaml

      programs:
         main:
            command: echo "Hello world"

Execution:

.. code:: sh

      docker run encab_minimum echo "Now this!"

Output:

.. code:: text

      INFO  encab: encab 0.0.1
      INFO  encab: Using configuration file ./encab.yml, source: Default location.
      INFO  main: Now this!
      INFO  main: Exited with rc: 0

Program Configuration (Map, optional)
'''''''''''''''''''''''''''''''''''''

-  ``command``: string or List of strings, optional

   the command to be execution as list in POSIX style.

   example:

   .. code:: yaml

      programs:
         command:
            echo "Test"

   …is identical to…

   .. code:: yaml

      programs:
         comand:     
            - echo 
            - Test

-  ``sh``: string or List of strings, optional

   programs can also be run as a shell script instead of a command.

   examples:

   .. code:: yaml

      programs:
         sh:
            echo "Test"

   Run multiple shell commands in a program:

   | \```yaml programs: sh:
   | - echo “Test1” - echo “Test2”

-  ``startup_delay``: float, optional The startup delay for this program
   in seconds. Default: 0 seconds

-  ``environment``: Map, optional

   additional environmment variables speciefied as a map.

   Example:

   .. code:: yaml

       environment:
           PYTHONPATH: /opt/app
           PATH: /usr/bin:/usr/local/bin

-  ``debug``: bool, optional if true, encab logs debug information.
   Default: false

-  ``loglevel``: string, optional

   the log level. One of ``CRITICAL``, ``FATAL``, ``ERROR``, ``WARN``,
   ``WARNING``, ``INFO``, ``DEBUG``

-  ``umask``: int or string, optional

   the
   `umask <https://pubs.opengroup.org/onlinepubs/9699919799/utilities/umask.html>`__,
   either as octal string (e.g. ``"077"``) or integer

-  ``user``: int or string, optional the user id or user name

-  ``join_time``: float, optional

   The join time is the time in seconds encab waits for a program to
   start/shutdown before it continues with the next. Default: 1 seconds.

Example:

The following configuration will start the program ``sleep`` first, then
it runs the scripts in main with the additionasl environment variables
``X`` and ``Y``.

.. code:: yaml

   programs:
       sleep:
           command: sleep 10
       main:
           environment:
               X: "1"
               Y: "2"
           sh: 
               - echo $X
               - echo $Y
