Extensions
==========

Log Sanitizer
-------------

``encab.yml``:

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

