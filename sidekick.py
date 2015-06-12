#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: ahuynh
# @Date:   2015-06-10 16:51:36
# @Last Modified by:   ahuynh
# @Last Modified time: 2015-06-12 10:15:05
'''
    The sidekick should essentially replace job of the following typical
    bash script that is used to announce a service to ETCD.

        while true; do \
          curl -f -X GET 0.0.0.0:${PORT}; \
          if [ $? -eq 0 ]; then \
            echo "announcing to ${PREFIX}/${DOMAIN}/%m"; \
            etcdctl set ${PREFIX}/${DOMAIN}/%m "${COREOS_PRIVATE_IPV4}:${PORT}" --ttl 60; \
          else \
            echo "service not running"; \
            etcdctl rm ${PREFIX}/${DOMAIN}/%m; \
          fi; \
          sleep 45; \
        done'

    sidekick.py replaces this mess with a more maintable, flexible python module.
'''
import argparse
import etcd
import hashlib
import logging
import os
import time
import socket
import sys

from docker import Client
from docker.utils import kwargs_from_env

# Create logger
FORMAT = '%(asctime)s\t%(levelname)s \t %(module)s \t %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=FORMAT)
logger = logging.getLogger( __name__ )

# Parse arguments
parser = argparse.ArgumentParser( description='Announce a service to etcd' )

# REQUIRED PARAMETERS
parser.add_argument( '--name', action='store', required=True,
                     help='Name of the docker container to check and announce.' )

parser.add_argument( '--ip', action='store', required=True,
                     help='Private or public IP of the instance that is running this container.' )

# OPTIONAL PARAMETERS
parser.add_argument( '--prefix', action='store', default='/services',
                     help='ETCD folder where we\'ll announce services.' )

parser.add_argument( '--domain', action='store', default='example.com',
                     help='Domain name to announce this service as.' )

parser.add_argument( '--timeout', action='store', type=int, default=10,
                     help='Private or public IP of the instance that is running this container.' )


def check_name( container, name ):
    ''' Check the container names for a match '''

    name = '/' + name

    for cname in container[ 'Names' ]:
        if name == cname:
            return True

    return False


def public_ports( container ):
    ''' Return a list of public ports for <container> '''
    return list(filter( lambda x: 'PublicPort' in x, container['Ports'] ))


def main():
    args = parser.parse_args()
    kwargs = kwargs_from_env()

    # Connect to docker
    if len( kwargs.keys() ) == 0:
        logger.warning( 'Unable to discover Docker settings through env' )
        logger.info( 'Using /var/run/docker.sock' )
        kwargs['base_url'] = 'unix://var/run/docker.sock'

    docker_client = Client(**kwargs)

    # Connect to ECTD
    etcd_client = etcd.Client()

    etcd_folder = os.path.join( args.prefix, args.domain )
    logger.debug( 'Announcing to {}'.format( etcd_folder ) )

    # Find the matching container
    try:
        containers = docker_client.containers()
    except Exception:
        sys.exit( 'FAILURE - Unable to connect Docker. Is it running?' )

    # Find the matching container
    matching = {}
    for container in containers:
        if check_name( container, args.name ):
            ports = public_ports( container )

            # TODO: Handle multiple public ports
            # Right now we grab the first port in the list and announce the
            # server using that IP
            if len( ports ) == 0:
                raise Exception( 'Container has no public ports' )

            for port in ports:
                port = port[ 'PublicPort' ]

                # Create a UUID
                m = hashlib.md5()
                m.update( args.name.encode('utf-8') )
                m.update( args.ip.encode('utf-8') )
                m.update( str( port ).encode('utf-8') )
                uuid = m.hexdigest()

                # Store the details
                uri = '{}:{}'.format( args.ip, port )
                matching[ uuid ] = { 'ip': args.ip, 'port': port, 'uri': uri }

    # Main health checking loop
    while True:

        for key, value in matching.items():
            logger.info( 'Health check for {}'.format( key ) )

            full_key = os.path.join( etcd_folder, key )

            try:
                s = socket.socket()
                s.connect( ( value['ip'], value['port'] ) )
            except ConnectionRefusedError:
                logger.error( 'tcp://{ip}:{port} health check FAILED'.format(**value) )
                # Remove this server from ETCD if it exists
                etcd_client.delete( full_key )
            else:
                logger.error( 'tcp://{ip}:{port} health check SUCCEEDED'.format(**value) )
                s.close()

                # Announce this server to ETCD
                etcd_client.set( full_key, value['uri'] )

        logger.info( 'Sleeping for {} seconds'.format( args.timeout ) )
        time.sleep( args.timeout )

if __name__ == '__main__':
    main()
