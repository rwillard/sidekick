# sidekick

[![Build Status](https://travis-ci.org/a5huynh/sidekick.svg?branch=master)](https://travis-ci.org/a5huynh/sidekick)

If you're running services on CoreOS or using etcd as a way to keep track of
different services that are running across your cluster, `sidekick` is a
flexible presence service that was built for you.


## Dependencies

Some system dependencies that are expected to run `sidekick`:

- Python >= 3.4.3
- etcd >= 2.0

Python dependencies can be installed by running the following:

    pip install -r requirements.txt


## Usage

`sidekick` is intended to be used as a Docker container, linked to the host's networking stack and Docker daemon. 

Linking the host's networking stack allows `sidekick` to easily check the health of the service without any networking complexities. Linking to the host's Docker daemon allows us to easily check for a service's publicly binded ports and announce those to etcd.

Enough talk! Let's go through an example. Let's start up a simple NGINX service:

    docker run -d --name nginx -p 80 -p 443 nginx:1.9

Notice that we don't have to explicitly say the local host port for NGINX. We'll let Docker figure out an open port and simply announce that port after inspection. Now we can run our `sidekick`:

    python sidekick.py --name nginx --ip localhost

If you're running on OSX and using boot2docker, you'll need to add 
`--check-ip $(boot2docker ip)` to the list of arguments since `sidekick` expects
the service to be accessible locally.

## `sidekick` Command Line Arguments

`sidekick` is very flexible and takes a number of command line arguments to fit
customized deployment onto clusters.

#### Mandatory Arguments
| Argument | Description
|----------|-----------------------------------------------------------
| --name   | Name of the Docker container to inspect.
| --ip     | The IP to use in the URI for the presence announcement.

#### Optional Arguments

| Argument    | Description
|-------------|-----------------------------------------
| --check-ip  | IP used to check a service's health. By default, services are expected to run locally. **Default:** 0.0.0.0
| --docker    | Docker server URI. **Default:** unix:///var/run/docker.sock
| --domain   | The domain/service name for this service. **Default:** example.com
| --etcd-host | ETCD cluster peer host. **Default:** localhost
| --etcd-port | ETCD cluster peer port. **Default:** 4001
| --prefix   | The etcd folder in which to announce running services. **Default:** /services
| --timeout  | The number of seconds to wait until the next health check. **Default:** 10
| --ttl      | ETCD ttl in seconds for the service announcement. **Default:** 60


