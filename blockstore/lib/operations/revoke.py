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

#from pybitcoin import embed_data_in_blockchain, make_op_return_tx, make_op_return_outputs, \
from pyreddcoin import embed_data_in_blockchain, make_op_return_tx, make_op_return_outputs, \
        make_op_return_script, broadcast_transaction, serialize_transaction, \
        script_hex_to_address, get_unspents
from utilitybelt import is_hex
from binascii import hexlify, unhexlify

from ..b40 import b40_to_hex, bin_to_b40, is_b40
from ..config import *
from ..scripts import *

from ..nameset import NAMEREC_FIELDS

# consensus hash fields (ORDER MATTERS!)
FIELDS = NAMEREC_FIELDS


def build(name, testset=False):
    """
    Takes in the name, including the namespace ID (but not the id: scheme)
    Returns a hex string representing up to LENGTHS['blockchain_id_name'] bytes.
    
    Record format:
    
    0    2  3                             39
    |----|--|-----------------------------|
    magic op   name.ns_id (37 bytes)
    
    """
    
    if not is_name_valid( name ):
       raise Exception("Invalid name '%s'" % name)

    readable_script = "NAME_REVOKE 0x%s" % (hexlify(name))
    hex_script = blockstore_script_to_hex(readable_script)
    packaged_script = add_magic_bytes(hex_script, testset=testset)
    
    return packaged_script 


def make_outputs( data, inputs, change_address, pay_fee=True ):
    """
    Make outputs for a revoke.
    """

    outputs = [
        # main output
        {"script_hex": make_op_return_script(data, format='hex'),
         "value": 0},
        
        # change output
        {"script_hex": make_pay_to_address_script(change_address),
         "value": calculate_change_amount(inputs, 0, 0)}
    ]

    if pay_fee:
        dust_fee = tx_dust_fee_from_inputs_and_outputs( inputs, outputs )
        outputs[1]['value'] = calculate_change_amount( inputs, 0, dust_fee )

    return outputs


def broadcast(name, private_key, blockchain_client, testset=False, blockchain_broadcaster=None, user_public_key=None, tx_only=False):
    
    # sanity check 
    pay_fee = True
    if user_public_key is not None:
        pay_fee = False
        tx_only = True

    if user_public_key is None and private_key is None:
        raise Exception("Missing both public and private key")
    
    if not tx_only and private_key is None:
        raise Exception("Need private key for broadcasting")
    
    if blockchain_broadcaster is None:
        blockchain_broadcaster = blockchain_client 
    
    from_address = None 
    inputs = None
    private_key_obj = None
    
    if user_public_key is not None:
        # subsidizing 
        pubk = ReddcoinPublicKey( user_public_key )

        from_address = pubk.address()
        inputs = get_unspents( from_address, blockchain_client )

    elif private_key is not None:
        # ordering directly 
        pubk = ReddcoinPrivateKey( private_key ).public_key()
        public_key = pubk.to_hex()
        
        private_key_obj, from_address, inputs = analyze_private_key(private_key, blockchain_client)
         
    nulldata = build(name, testset=testset)
    outputs = make_outputs( nulldata, inputs, from_address, pay_fee=pay_fee )
   
    if tx_only:
       
        unsigned_tx = serialize_transaction( inputs, outputs )
        return {'unsigned_tx': unsigned_tx}

    else:
       
        signed_tx = tx_serialize_and_sign( inputs, outputs, private_key_obj )
        response = broadcast_transaction( signed_tx, blockchain_broadcaster )
        response.update({'data': nulldata})
        return response


def parse(bin_payload):    
    """
    Interpret a block's nulldata back into a name.  The first three bytes (2 magic + 1 opcode)
    will not be present in bin_payload.
    
    The name will be directly represented by the bytes given.
    """
    
    fqn = bin_payload
    if not is_name_valid( fqn ):
        return None 

    return {
       'opcode': 'NAME_REVOKE',
       'name': fqn
    }


def get_fees( inputs, outputs ):
    """
    Given a transaction's outputs, look up its fees:
    * there should be two outputs: the OP_RETURN and change address
    
    Return (dust fees, operation fees) on success 
    Return (None, None) on invalid output listing
    """
    if len(outputs) != 2:
        return (None, None)
    
    # 0: op_return
    if not tx_output_is_op_return( outputs[0] ):
        return (None, None) 
    
    if outputs[0]["value"] != 0:
        return (None, None) 
    
    # 1: change address 
    if script_hex_to_address( outputs[1]["script_hex"], version_byte=61 ) is None:
        return (None, None)
    
    dust_fee = (len(inputs) + 1) * DEFAULT_DUST_FEE + DEFAULT_OP_RETURN_FEE
    op_fee = 0
    
    return (dust_fee, op_fee)

