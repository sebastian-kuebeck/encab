# Encab: A Docker Entrypoint Tool

**Encab** is essentially a replacement for complex, hand-written Docker Container Entrypoint scripts,
especially when dockerizing complex legacy applications.

Add it as your [Dockerfile Entrypoint][1],
together with the encab configuration file `encab.yml`,

```dockerfile
   ...
   ADD encab.yml .
   ENTRYPOINT ["encab"]
```

[1]: https://docs.docker.com/engine/reference/builder/#entrypoint

define what you want to run in your container in `encab.yml`,

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
   INFO  encab: encab 0.0.1
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

## Installation

### From Source

Encab is not yet at pypi so installation from source is the only option right now.

#### Prerequisites

- [Docker](https://www.docker.com/) from your Linux distribution or Docker Desktop.
- [git](https://git-scm.com/) distributed version control system
- [Python](https://www.python.org/) Version >= 3.7
- activated Python virtual environment such as [miniconda][2] or [virtualenv][3]

[2]: https://docs.conda.io/en/latest/miniconda.html
[3]: https://virtualenv.pypa.io/en/latest/

#### Download

```sh
   git clone https://github.com/skuebeck/encab.git
   cd encab
   pip install -r requirements.txt
```

#### Build Wheel

```sh
   make dist
```

If all goes well, the encab [wheel file](https://packaging.python.org/en/latest/tutorials/installing-packages/#source-distributions-vs-wheels) will be in the `dist` directory.

It's named `encab-<version>-py3-none-any.whl`

#### Testing (optional)

run unit tests:

```sh
   make test
```

run localy:

```sh
   python -m encab
```

It'll use the sample `encab.yml` file.
The result will be something like this:

```text
INFO  encab: encab 0.0.1
INFO  encab: Using configuration file ./encab.yml, source: Default location.
INFO  encab: Dry run. No program will be started.
INFO  encab: settings are valid.
INFO  encab: settings are valid.
INFO  encab: settings are valid.
INFO  encab: Dry run succeeded. Exiting.
```

## Deployment

1. Copy the generated wheel file into your Docker project directory.
2. Create a configuration file `encab.yml`(see Configuration section for details).

   ```yaml
      programs:
         main:
            sh: echo 'Hello World'
   ```

3. Add Encab to your [Docker file][4].

   ```dockerfile
   FROM python:3.10.8-slim-bullseye

   # --------------------------------------------
   # Install Encab 
   #
   ARG ENCAB_WHEEL=encab-0.0.1-py3-none-any.whl

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
   ```

   [4]: https://docs.docker.com/engine/reference/builder/

4. Build container

   ```sh
   docker build --build-arg ENCAB_WHEEL=`ls encab-*.whl` -t encab_minimum .
   ```

5. Run container

   ```sh
   docker run encab_minimum
   ```

   Result:

   ```text
   INFO  encab: encab 0.0.1
   INFO  encab: Using configuration file ./encab.yml, source: Default location.
   INFO  main: Hello world!
   INFO  main: Exited with rc: 0
   ```

## Similar Projects

- [supervisord](http://supervisord.org/)
- [supervisord Github](https://github.com/Supervisor/supervisor)
