# Encab: A Simple Process Manager

**Encab** is a process manager that simplifies running multiple services in a container or from the command line.

It's essentially a replacement for complex, hand-written Docker Container Entrypoint scripts,
especially when dockerizing complex legacy applications.

1. Add it as your [Dockerfile Entrypoint][1],
together with the encab configuration file `encab.yml`,

```dockerfile
   ...
   ADD encab.yml .
   ENTRYPOINT ["encab"]
```

[1]: https://docs.docker.com/engine/reference/builder/#entrypoint

2. Define what you want to run in your container in `encab.yml`,

```yaml
   programs:
      cron:
         command: cron -f
      main:
         command: httpd-foreground
```

and encab cares for the rest.
Run it and you'll always know who's logging what...

```text
   INFO  encab: encab 0.0.6
   INFO  encab: Using configuration file ./encab.yml, source: Default location.
   ERROR main: AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 172.17.0.2. Set the 'ServerName' directive globally to suppress this message
   ERROR main: AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 172.17.0.2. Set the 'ServerName' directive globally to suppress this message
   ERROR main: [Wed Jan 18 09:47:12.417275 2023] [mpm_event:notice] [pid 12:tid 140142563044672] AH00489: Apache/2.4.54 (Unix) configured -- resuming normal operations
   ERROR main: [Wed Jan 18 09:47:12.417830 2023] [core:notice] [pid 12:tid 140142563044672] AH00094: Command line: 'httpd -D FOREGROUND'
   INFO  cron: Hello Wed Jan 18 09:48:01 UTC 2023
```

It shares some similarities with [supervisord](http://supervisord.org/) which I've used before I wrote encab but
supervisord is a process controll system not designed to run in a Container environment.

## Note

_**This tool is still under development. Sufficient for local experiments but not mature enough for production use!**_

## Features

- run multiple programs in a container at a time with transparent logging
- run programs as different users
- handle environment variables in a flexible way
- simplify container debugging
- load, build, validate environment variables

## Documentation

[Encab Documentation](https://encab.readthedocs.io)

## Installation

### Install locally

#### Prerequisites

- [Python](https://www.python.org/) Version >= 3.9
- activated Python virtual environment such as [miniconda][2] or [virtualenv][3]

```sh
   pip install -U encab
```

#### Run locally

1. Create sample encab file `encab.yml`

```yml
   encab:
      dry_run: false
   programs:
      main:
         sh:
            - echo "Hello Encab!"
```

2. Run locally:

```sh
   encab
```

The result will be something like this:

```text
INFO  encab: encab 0.0.6
INFO  encab: Using configuration file ./encab.yml, source: Default location.
INFO  main: Hello Encab!
INFO  main: Exited with rc: 0
   ```

### Install in Container

#### Prerequisites

- [Docker](https://www.docker.com/) from your Linux distribution or Docker Desktop.

#### Run in Container

1. Create sample encab file `encab.yml`

```yml
   encab:
      dry_run: false
   programs:
      main:
         sh:
            - echo "Hello Encab!"
```

2. Add Encab to your [Docker file][4].

   ```dockerfile

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

   ```

   [4]: https://docs.docker.com/engine/reference/builder/

2. Build container

   ```sh
   docker build -t encab_minimum .
   ```

3. Run container

   ```sh
   docker run encab_minimum
   ```

   Result:

   ```text
   INFO  encab: encab 0.0.6
   INFO  encab: Using configuration file ./encab.yml, source: Default location.
   INFO  main: Hello world!
   INFO  main: Exited with rc: 0
   ```

## Similar Projects

- [supervisord](http://supervisord.org/)
- [supervisord Github](https://github.com/Supervisor/supervisor)
