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

``encab``: Mapping (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

contains general settings as well as settings common to all programs, see `Encab Settings`_ 
and `Common config for encab and programs section`_ for details. 

``extensions``: Mapping (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

maps **Extention Names** to **Extension Settings**.

There are two types of extension:

- Built in extensions

- External extensions

Build in are identified by the **extension** name whereas 
external extensions are identified by their **python module name**.

Currently, there are the following build in Extensions:

- ``log_satnitizer``
- ``startup_script``
- ``validation``

See `Extension Settings`_ for details.


``programs``: Mapping (Optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

maps **program names** to **Program Settings**, see `Program Settings`_ and `Common config for encab and programs section`_ for details. 

The program named ``main`` is the main program in the configuration. All
other programs are started *before* ``main`` and ended *after* ``main``.

The command in ``main`` can be overridden by command line arguments,
where the first arguments represents the command name and the following
its parameters.

Encab Settings
^^^^^^^^^^^^^^^^

General Settings
''''''''''''''''

-  ``halt_on_exit``: Boolean (optional)

   halt on exit: if ``true``, encab is halted after the main program
   ends. Default: ``false``

-  ``logformat``: String (optional)

   Custom log format
   `link <https://docs.python.org/3/library/logging.html#logrecord-attributes>`__.
   The attribute ``program`` contains the program name.

   Default: ``%(levelname)-5.5s %(program)s: %(message)s``

-  ``dry_run``: Boolean (optional)

   ``true``: the configuration is checked but no program is started.
   Default: ``false``

Common config for encab and programs section
''''''''''''''''''''''''''''''''''''''''''''

-  ``environment``: Mapping (optional)

   additional environmment variables speciefied as a map.

   Example:

   .. code:: yaml

       environment:
           PYTHONPATH: /opt/app
           PATH: /usr/bin:/usr/local/bin

-  ``debug``: Boolean (optional) if true, encab logs debug information.
   Default: false

-  ``loglevel``: Integer or String (optional)

   the log level. One of ``CRITICAL``, ``FATAL``, ``ERROR``, ``WARN``,
   ``WARNING``, ``INFO``, ``DEBUG``

-  ``umask``: Integer or String (optional)

   the
   `umask <https://pubs.opengroup.org/onlinepubs/9699919799/utilities/umask.html>`__,
   either as octal string (e.g. “077”) or integer

-  ``user``: Integer or String (optional)
   
   the user id or name

-  ``group``: Integer or String (optional)
   
   the group id or name

-  ``join_time``: Floating point (optional)

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




Extension Settings
^^^^^^^^^^^^^^^^^^

-  ``enabled``: Boolean (optional) true: the extension is enabled

    Wether or not an extension is enabled by default is determined by the extension itself.
    For built in extensions, only the log_satnitizer extension is enabled by default.

-  ``module``: String (optional) The extension module name

    Specifies the python module name for external extension.

-  ``settings``: Mapping (Optional) extension specific settings

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



Program Settings
^^^^^^^^^^^^^^^^

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

      INFO  encab: encab 0.1.1
      INFO  encab: Using configuration file ./encab.yml, source: Default location.
      INFO  main: Now this!
      INFO  main: Exited with rc: 0

Program Configuration
'''''''''''''''''''''

-  ``command``: String or Sequence (optional)

   the command to be execution as list in POSIX style.

   example:

   .. code:: yaml

      programs:
         main:
            command:
               echo "Test"

   …is identical to…

   .. code:: yaml

      programs:
         main:
            command:     
               - echo 
               - Test

-  ``sh``: String or Sequence (optional)

   programs can also be run as a shell script instead of a command.

   examples:

   .. code:: yaml

      programs:
         main:
            sh:
               echo "Test"

   Run multiple shell commands in a program:

   .. code:: yaml

      programs:
         main:
            sh:
               - echo “Test1”
               - echo “Test2”

-  ``startup_delay``: float, optional The startup delay for this program
   in seconds. Default: 0 seconds

-  ``environment``: Map, optional

   additional environmment variables speciefied as a map.

   Example:

   .. code:: yaml

       environment:
           PYTHONPATH: /opt/app
           PATH: /usr/bin:/usr/local/bin

-  ``debug``: Boolean (optional). If true, encab logs debug information.
   Default: false

-  ``loglevel``: String (optional)

   the log level. One of ``CRITICAL``, ``FATAL``, ``ERROR``, ``WARN``,
   ``WARNING``, ``INFO``, ``DEBUG``

-  ``umask``: Integer or String (optional)

   the
   `umask <https://pubs.opengroup.org/onlinepubs/9699919799/utilities/umask.html>`__,
   either as octal string (e.g. ``"077"``) or integer

-  ``user``: Integer or String (optional), optional the user id or user name

-  ``directory``: String (optional), the directory the program is executed in

-  ``join_time``: Floating Point (optional)

   The join time is the time in seconds encab waits for a program to
   start/shutdown before it continues with the next. Default: 1 seconds.

- ``reap_zombies``: bool (optional)
  
   ``true``: Zombie processes are reaped automatically. Default: ``false`` 
   see: `Zombie Process <https://en.wikipedia.org/wiki/Zombie_process>`_.


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
