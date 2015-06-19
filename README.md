# sidekick

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

    docker run -it \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --net=host --name sidekick \
        sidekick:latest \
        --name nginx \
        --prefix /services \
        --domain example.com \
        --ip localhost

### `sidekick` Command Line Arguments

| Argument  | Description
|-----------|-----------------------------------------
| --name    | Name of the Docker container to inspect.
| --prefix  | The etcd folder in which to announce running services.
| --domain  | The domain/service name for this service.
| --ip      | The IP to use in the URI for the presence announcement.
| --timeout | The number of seconds to wait until the next health check.

