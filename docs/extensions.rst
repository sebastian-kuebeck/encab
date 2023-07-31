Extensions
==========

log_sanitizer
-------------

    Simple log sanitizer for environment variable values.
    It looks for values of environment variables whose names match
    certain patterns and replaces them with asterics.
    
    Predefined patterns are:
    
    - ``*KEY*``
    - ``*SECRET*``
    - ``*PASSWORD*``

    For patterns, `UNIX file pattern rules <https://docs.python.org/3/library/fnmatch.html#module-fnmatch>`__ are used.
    They can be extended or overridden in the extension settings.
    
    Example:
    
    Suppose you have the variable ``MY_PASSWORD`` set like this:
    
    ``MY_PASSWORD=s3cR37``
    
    The name ``MY_PASSWORD`` matches the predifined pattern ``*PASSWORD*``,
    so if you run a program like ``echo $MY_PASSWORD``, 
    the output will be raplaced by ``******``.
    
    This extension is enabled by default and can be disabled in the extension settings.

The following example adds the additional pattern ``*MAGIC*`` such that variables like ``MAGIC_VALUE``` get sanitized as well. 

.. code:: yaml

   extensions:
       log_sanitizer:
           enabled: true
           settings:
               override: false
               patterns: 
                   - "*MAGIC*"


Parameters
^^^^^^^^^^

``patterns`` (List, Optional)

set sensitive environmen variable name patterns whose values will be masked.
UNIX file pattern rules are used (see https://docs.python.org/3/library/fnmatch.html#module-fnmatch)       
    
example:

``*MAGIC*`` -- all variable names containing the string MAGIC 

``override``: Boolean (optional)

if true, builtin patterns are overriden

startup_script
--------------

Run scripts before the actual programs are started.
In addition, environman variables can be loaded from a file or generated using a script.

Example:

.. code:: yaml

   extensions:
       startup_script:
           enabled: true
           settings:
               buildenv: 
                   - echo 'X=1' 
                   - echo 'Z=3'

Parameters
^^^^^^^^^^

``loadenv``: String (optional)

the path of the file in dotenv format from which environment variables are loaded.
The format is similar to Bash files.

Example:

.. code-block:: bash

    FOO="first line"
    BAR=2

see: https://pypi.org/project/python-dotenv/

``buildenv``: String or Sequence (optional)

executes a shell command that generates environment variables in dotenv format.

Example:

.. code-block:: yaml

    buildenv:
    - echo "X=1"
    - echo "Z=3"

``sh``: String or Sequence (optional)

executes a shell command before the programs specified in the programs section of the encab file are run

Sequence of execution
^^^^^^^^^^^^^^^^^^^^^

Note that the actions specified before are performed in the sequence ``loadenv``, ``buildenv``, ``sh`` and can affect each other.
Hence, the following settings would output ``1 2 3``, as ``Y`` is defined in the file ``.env`` prior to ``X`` and ``Z``,
which are generated using ``buildenv``. 

.. code-block:: yaml

    startup_script:
        enabled: true
        settings:
            loadenv: .env
            buildenv: 
                - echo 'X=1' 
                - echo 'Z=3'
            sh:
                echo $X $Y $Z 

contents of file ``.env``:

.. code-block:: bash

    Y=2



validation
----------

Validates environment variables, sets default values and stops program execution if one or more variables
do not conform to the specification. The validation happens *after* the **startup_script** extension
is run such that validation is guaranteed no matter where the variable comes from.

Example:

.. code:: yaml

    validation:
        enabled: true
        settings:
            variables:
                X:
                    required: true
                    default: "1"
                    min_length: 1
                    max_length: 5
                    regex: "0|1"
                Y:
                    min_value: 0
                    max_value: 10

Parameters
^^^^^^^^^^

``variables``: Mapping (optional)

maps **variable names** to **Variable Specifications**, see **Variable Specification** for details.

``include``: String (optional)

include additional environment variable specifications (see below) from file 
    
example settings:

.. code-block:: yaml

    settings:
        include: validation.yml
                        
example file ``validation.yml``:

.. code-block:: yaml

    X:
        required: true
        default: "1"
        min_length: 1
        max_length: 5
        regex: "0|1"
    Y:
        min_value: 0
        max_value: 10


Variable Specifications
^^^^^^^^^^^^^^^^^^^^^^^

``required``: Boolean (optional)

True: this variable is required

``format``: String (optional) 

Variable format. One of ``string``, ``float``, ``int``. Default: ``string``  

``default``: String or Floating point or Integer (optional)

Default value of this variable. It will be set if this variable is missing or empty

``min_length``: Integer (Optional)

Minimum length

``max_length``: Integer (Optional)

Maximum length

``min_value``: Integer or Floating point (optional)

Minimum value

``max_value``: Integer or Floating point (optional)

Maximum value

``regex``: String (optional)

If set, the value must match the `Regular expression <https://docs.python.org/3/howto/regex.html>`__ given.

``program``: String (optional)

    Validation is limited to the given program. Default: no limitation.

    Use ``programs`` if validation should be limited to multiple programs.

``programs``: Sequence (Optional)

Validation is limited to the given programs. Default: no limitation.

