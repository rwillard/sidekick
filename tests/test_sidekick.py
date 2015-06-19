#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: ahuynh
# @Date:   2015-06-18 20:15:30
# @Last Modified by:   ahuynh
# @Last Modified time: 2015-06-19 10:36:06
import unittest

from collections import namedtuple
from sidekick import check_name, find_matching_container, health_check, public_ports

# Used to test command line arguments
Args = namedtuple('Args', ['name', 'ip'])


class TestSidekick( unittest.TestCase ):

    def setUp( self ):

        self.args = Args( name='test', ip='localhost' )

        self.container = {
            'Image': 'image:latest',
            'Ports': [{
                'PrivatePort': 9200,
                'IP': '0.0.0.0',
                'Type': 'tcp',
                'PublicPort': 9200 }, {
                'PrivatePort': 9300,
                'IP': '0.0.0.0',
                'Type': 'tcp',
                'PublicPort': 9300}],
            'Created': 1427906382,
            'Names': ['/test'],
            'Status': 'Up 2 days'}

    def test_check_name( self ):
        ''' Test `check_name` functionality '''
        self.assertTrue( check_name( self.container, 'test' ) )
        self.assertFalse( check_name( self.container, '/test' ) )

    def test_find_matching_container( self ):
        ''' Test `find_matching_container` functionality '''
        # Test a successful match
        results = find_matching_container( [self.container], self.args )
        self.assertEqual( len( results.items() ), 2 )

        # Test an unsuccessful match (no matching names)
        invalid_name = dict( self.container )
        invalid_name[ 'Names' ] = [ '/invalid_name' ]
        results = find_matching_container( [invalid_name], self.args )
        self.assertEqual( len( results.items() ), 0 )

        # Test an unsuccessful match (no public ports)
        no_open_ports = dict( self.container )
        no_open_ports['Ports'] = []
        with self.assertRaises( Exception ):
            find_matching_container( [no_open_ports], self.args )

    def test_health_check( self ):
        ''' Test `health_check` functionality '''
        results = find_matching_container( [self.container], self.args )
        for value in results.values():
            self.assertFalse( health_check( value ) )

    def test_public_ports( self ):
        ''' Test `public_ports` functionality '''
        self.assertEquals( len( public_ports( self.container ) ), 2 )
