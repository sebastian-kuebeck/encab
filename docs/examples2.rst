Real World Example
==================

The `Sample Wordpress Docker Container <https://github.com/sebastian-kuebeck/wordpress-container>`__
is a real world example of containerizing Wordpress for small web sites.

It runs Wordpress, Wordpress CLI, PHP-FPM and nginx in one container.

As a plus, it sets up the database, the secrets and an initial set of plugins during the first start,
which eliminates security headaches during startup.

The `encab configuration file <https://github.com/sebastian-kuebeck/wordpress-container/blob/main/nginx-fpm/configs/encab.yml>`__ shows how encab and its plugins work together:

``config.yml``:

.. code:: yaml

    # see: https://encab.readthedocs.io/en/latest/configuration.html
    encab:
        halt_on_exit: false # halt execution if main exits
        logformat: "%(program)s %(levelname)-5.5s: %(message)s" # custom log format
        dry_run: false # dry run
        debug: false # no debug output
    extensions:
        # We want to make sure that all mandatory environment variables are set
        # before the container starts up to avoid unforseable consequences. 
        validation:
            enabled: true
            settings:
                variables:
                WORDPRESS_DB_NAME:
                    required: true
                WORDPRESS_DB_USER:
                    required: true
                WORDPRESS_DB_PASSWORD:
                    required: true
                WORDPRESS_DB_USER:
                    required: true
                WORDPRESS_DB_HOST:
                    required: true
                WP_ADMIN_USER:
                    required: true
                WP_ADMIN_PASSWORD:
                    required: true
                WP_ADMIN_EMAIL:
                    required: true
                WP_TITLE:
                    required: true
                WP_URL:
                    required: true
                WP_LOCALE:
                    required: true
        # We want to make sure that confidential information in environmenmt variables
        # are sanitized so leaks from log messages are plugged.
        log_sanitizer:
            enabled: true
            settings:
            override: true
            patterns:
                - WP_ADMIN_PASSWORD
                - WORDPRESS_DB_PASSWORD
                - WORDPRESS_AUTH_KEY
                - SECURE_AUTH_KEY
                - WORDPRESS_SECURE_AUTH_KEY
                - LOGGED_IN_KEY
                - WORDPRESS_NONCE_KEY

        # The startup scrips does the auto installation if necessary before the programs are started
        # 
        startup_script:
            enabled: true
            settings:
            sh:
                startup.sh

    programs:
        # The cron job uses curl to trigger the Wordpress cron script.
        # It also calls tmpreaper to clean up leftover temporary files.
        #
        # Wordpress cron script: https://github.com/sebastian-kuebeck/wordpress-container/blob/main/nginx-fpm/configs/wordpress.cron
        cron:
            restart_delay: 1
            command:
                cron -f -l -L 15
        # Runs the PHP Interpreter as its own process
        # PHP-FPM log settings: https://github.com/sebastian-kuebeck/wordpress-container/blob/main/nginx-fpm/configs/error-logging.ini
        fpm:
            restart_delay: 1
            command:
                php-fpm -F
        # Finally, the nginx web server
        # nginx configuration: https://github.com/sebastian-kuebeck/wordpress-container/blob/main/nginx-fpm/configs/nginx.conf
        main:
            command:
                nginx -g 'daemon off;'

