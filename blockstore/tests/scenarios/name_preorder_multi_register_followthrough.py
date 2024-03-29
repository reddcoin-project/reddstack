#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Blockstore
    ~~~~~
    copyright: (c) 2014-2015 by Halfmoon Labs, Inc.
    copyright: (c) 2016 by Blockstack.org

    This file is part of Blockstore

    Blockstore is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Blockstore is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with Blockstore. If not, see <http://www.gnu.org/licenses/>.
""" 

import testlib
import pyreddcoin
import json
import sys
import blockstore.blockstored as blockstored

wallets = [
    testlib.Wallet( "5JesPiN68qt44Hc2nT8qmyZ1JDwHebfoh9KQ52Lazb1m1LaKNj9", 100000000000 ),
    testlib.Wallet( "5KHqsiU9qa77frZb6hQy9ocV7Sus9RWJcQGYYBJJBb2Efj1o77e", 100000000000 ),
    testlib.Wallet( "5Kg5kJbQHvk1B64rJniEmgbD83FpZpbw2RjdAZEzTefs9ihN3Bz", 100000000000 ),
    testlib.Wallet( "5JuVsoS9NauksSkqEjbUZxWwgGDQbMwPsEfoRBSpLpgDX1RtLX7", 100000000000 ),
    testlib.Wallet( "5KEpiSRr1BrT8vRD7LKGCEmudokTh1iMHbiThMQpLdwBwhDJB1T", 100000000000 ),
    testlib.Wallet( "5K6Nou64uUXg8YzuiVuRQswuGRfH1tdb9GUC9NBEV1xmKxWMJ54", 100000000000 )
]

consensus = "17ac43c1d8549c3181b200f1bf97eb7d"
preorder_consensus = None

def scenario( wallets, **kw ):

    global final_consensus

    testlib.blockstore_namespace_preorder( "test", wallets[1].addr, wallets[0].privkey )
    testlib.next_block( **kw )

    testlib.blockstore_namespace_reveal( "test", wallets[1].addr, 52595, 250, 4, [6,5,4,3,2,1,0,0,0,0,0,0,0,0,0,0], 10, 10, wallets[0].privkey )
    testlib.next_block( **kw )

    testlib.blockstore_namespace_ready( "test", wallets[1].privkey )
    testlib.next_block( **kw )

    resp = testlib.blockstore_name_preorder_multi( ["foo.test", "bar.test", "baz.test"], wallets[2].privkey, [wallets[3].addr, wallets[4].addr, wallets[5].addr] )
    if 'error' in resp:
        print json.dumps( resp, indent=4 )
        sys.exit(1)
        
    testlib.next_block( **kw )
    preorder_consensus = testlib.get_consensus_at( testlib.get_current_block() )

    resp = testlib.blockstore_name_register( "foo.test", wallets[2].privkey, wallets[3].addr )
    if 'error' in resp:
        print json.dumps( resp, indent=4 )
        sys.exit(1)
        
    resp = testlib.blockstore_name_register( "bar.test", wallets[2].privkey, wallets[4].addr )
    if 'error' in resp:
        print json.dumps( resp, indent=4 )
        sys.exit(1)

    testlib.next_block( **kw )

    # should cause the whole thing to fail, since we didn't preorder this separately 
    resp = testlib.blockstore_name_register( "goo.test", wallets[2].privkey, wallets[5].addr )
    if 'error' in resp:
        print json.dumps( resp, indent=4 )
        sys.exit(1)

    resp = testlib.blockstore_name_register( "baz.test", wallets[2].privkey, wallets[5].addr )
    if 'error' in resp:
        print json.dumps( resp, indent=4 )
        sys.exit(1)

    testlib.next_block( **kw )


def check( state_engine ):

    global preorder_consensus

    # not revealed, but ready 
    ns = state_engine.get_namespace_reveal( "test" )
    if ns is not None:
        return False 

    ns = state_engine.get_namespace( "test" )
    if ns is None:
        return False 

    if ns['namespace_id'] != 'test':
        return False 

    # there will be a multi-preorder 
    preorder = state_engine.get_name_multi_preorder( ['foo.test', 'bar.test', 'baz.test'], \
                                                     pyreddcoin.make_pay_to_address_script(wallets[2].addr), \
                                                     [wallets[3].addr, wallets[4].addr, wallets[5].addr])

    if preorder is None:
        print "no preorder found for foo.test, bar.test, baz.test"
        return False

    if preorder['op_fee'] < blockstored.get_name_cost( 'foo.test' ) + blockstored.get_name_cost( 'bar.test' ) + blockstored.get_name_cost( 'baz.test' ):
        print "Insufficient fee"
        return False 

    if not state_engine.is_sender_multi_preordering( pyreddcoin.make_pay_to_address_script(wallets[2].addr) ):
        print "Inconsistent state: preorder exists, but not preordering"
        return False 

    # our names should not be registered 
    for n in ['foo.test', 'bar.test', 'baz.test']:
        name_rec = state_engine.get_name( n )
        if name_rec is not None:
            print "Name registered: %s" % n
            return False 

    return True
