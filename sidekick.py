#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: ahuynh
# @Date:   2015-06-10 16:51:36
# @Last Modified by:   ahuynh
# @Last Modified time: 2016-02-11 16:36:44
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
import json

from docker import Client
from docker.utils import kwargs_from_env

# Create logger
FORMAT = '%(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=FORMAT)
logger = logging.getLogger( __name__ )


def parse_args( args ):
    """ Handle parsing command line arguments """
    parser = argparse.ArgumentParser( description='Announce a service to etcd' )
    # REQUIRED PARAMETERS
    parser.add_argument( '--name', action='store', required=True,
                         help='Name of the docker container to check and announce.' )

    parser.add_argument( '--ip', action='store', required=True,
                         help='Private or public IP of the instance that is running this container.' )

    # OPTIONAL PARAMETERS
    parser.add_argument( '--check-ip', action='store', default='0.0.0.0',
                         help='IP used for health checks.' )

    parser.add_argument( '--docker', action='store', default='unix:///var/run/docker.sock',
                         help='Docker base URI.' )

    parser.add_argument( '--etcd-host', action='store', default='localhost',
                         help='ETCD host' )

    parser.add_argument( '--etcd-port', action='store', type=int, default=2379,
                         help='ETCD port' )

    parser.add_argument( '--prefix', action='store', default='/services',
                         help='ETCD folder where we\'ll announce services. Ignored if vulcand flag is true.' )

    parser.add_argument( '--domain', action='store', default='example.com',
                         help='Domain name to announce this service as.' )

    parser.add_argument( '--timeout', action='store', type=int, default=10,
                         help='Private or public IP of the instance that is running this container.' )

    parser.add_argument( '--ttl', action='store', type=int, default=60,
                         help='ETCD ttl for the service announcement' )

    parser.add_argument( '--vulcand', action='store', type=bool, default=False,
                         help='Selector for LB')

    parser.add_argument( '--type', action='store', default='http',
                         help='type for Vulcand')

    return parser.parse_args( args )


def announce_services( services, etcd_folder, etcd_client, timeout, ttl, vulcand ):
    for key, value in services:
        logger.info( 'Health check for {}'.format( key ) )
        healthy = check_health( value )

        # Keys to write to etcd
        announcement = {}
        if vulcand:
            backend  = "/vulcand/backends/{domain}/backend".format( domain=value['domain'] )
            server   = "/vulcand/backends/{domain}/servers/{uuid}".format( domain=value['domain'], uuid=key )
            frontend = "/vulcand/frontends/{domain}/frontend".format( domain=value['domain'] )
            try:
                if not healthy:
                    # Remove this server from ETCD if it exists
                    etcd_client.delete( backend )
                    etcd_client.delete( server )
                    etcd_client.delete( frontend )
                else:
                    # Announce this server to ETCD
                    etcd_client.write( backend, json.dumps({ 'Type': value['type'] }), ttl=ttl)
                    etcd_client.write( server, json.dumps({ 'URL': 'http://{uri}'.format( **value ) }), ttl=ttl)
                    etcd_client.write( frontend, json.dumps({
                        'Type': value['type'],
                        'BackendId': value['domain'],
                        'Route': 'Host(`{0}`)'.format( value['domain'] )
                    }), ttl=ttl)

            except etcd.EtcdException as e:
                logging.error( e )
        else:
            announcement[ os.path.join( etcd_folder, key ) ] = value[ 'uri' ]

        try:
            if not healthy:
                # Remove keys from server if not healthy
                for k in announcement.keys():
                    etcd_client.delete( k )
            else:
                # Annouce service to etcd
                for ( k, v ) in announcement.items():
                    etcd_client.write( k, v, ttl=ttl )
        except etcd.EtcdException as e:
            logging.error( e )

    logger.info( 'Sleeping for {} seconds'.format( timeout ) )
    time.sleep( timeout )


def check_health( service ):
    '''
        Check the health of `service`.

        This is done using a socket to test if the specified PublicPort is
        responding to requests.
    '''
    healthy = False

    try:
        s = socket.socket()
        s.connect( ( service['check_ip'], service['port'] ) )
    except ConnectionRefusedError:
        logger.error( 'tcp://{check_ip}:{port} health check FAILED'.format(**service) )
        healthy = False
    else:
        s.close()
        logger.info( 'tcp://{check_ip}:{port} health check SUCCEEDED'.format(**service) )
        healthy = True
        s.close()

    return healthy


def check_name( container, name ):
    ''' Check the container names for a match '''

    name = '/' + name

    for cname in container[ 'Names' ]:
        if name == cname:
            return True

    return False


def find_matching_container( containers, args ):
    '''
        Given the name of the container:
            - Find the matching container
            - Note the open ports for that container
            - Generate a UUID based on the name, ip, and port

        Return a dictionary of generated URIs mapped to the UUID for each open
        port, using the following format:

            UUID: {
                'ip':       IP that was passed in via args.ip,
                'port':     Open port,
                'uri':      IP:PORT
            }
    '''
    # Find the matching container
    matching = {}
    for container in containers:
        if not check_name( container, args.name ):
            continue

        ports = public_ports( container )

        # TODO: Handle multiple public ports
        # Right now we grab the first port in the list and announce the
        # server using that IP
        if len( ports ) == 0:
            raise Exception( 'Container has no public ports' )

        for port in ports:
            port = port[ 'PublicPort' ]

            # Create a UUID to uniquely identify a service that is running on
            # a particular machine with a particular port.
            m = hashlib.md5()
            m.update( args.name.encode('utf-8') )
            m.update( args.ip.encode('utf-8') )
            m.update( str( port ).encode('utf-8') )
            uuid = m.hexdigest()

            # Store the details
            uri = '{}:{}'.format( args.ip, port )
            matching[ uuid ] = {
                'ip': args.ip,
                'check_ip': args.check_ip,
                'port': port,
                'uri': uri,
                'domain': args.domain,
                'type': args.type
            }

    return matching


def public_ports( container ):
    ''' Return a list of public ports for <container> '''
    return list(filter( lambda x: 'PublicPort' in x, container['Ports'] ))


def main():
    args = parse_args( sys.argv[1:] )
    kwargs = kwargs_from_env()

    # Connect to docker
    if len( kwargs.keys() ) == 0:
        logger.warning( 'Unable to discover Docker settings through env' )
        logger.info( 'Using {}'.format( args.docker ) )
        kwargs['base_url'] = args.docker

    # Connect to ECTD
    etcd_client = etcd.Client( host=args.etcd_host, port=args.etcd_port )
    etcd_folder = os.path.join( args.prefix, args.domain )
    logger.debug( 'Announcing to {}'.format( etcd_folder ) )

    # Find the matching container
    docker_client = Client(**kwargs)
    try:
        containers = docker_client.containers()
        logger.error( containers )
    except Exception as e:
        logger.error( e )
        sys.exit( 'FAILURE - Unable to connect Docker. Is it running?' )

    # Find the matching container
    matching = find_matching_container( containers, args )

    # Main health checking loop
    while True:
        announce_services( matching.items(),
                           etcd_folder,
                           etcd_client,
                           args.timeout,
                           args.ttl,
                           args.vulcand )

if __name__ == '__main__':
    main()
