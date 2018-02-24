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

from utilitybelt import is_hex, is_valid_int
from binascii import hexlify, unhexlify
#from pybitcoin import ReddcoinPrivateKey, ReddcoinPublicKey, script_to_hex, make_pay_to_address_script, analyze_private_key
#from pyreddcoin.transactions.outputs import calculate_change_amount
from pyreddcoin import ReddcoinPrivateKey, ReddcoinPublicKey, script_to_hex, make_pay_to_address_script, analyze_private_key
from pyreddcoin.transactions.outputs import calculate_change_amount

import virtualchain
from virtualchain import getrawtransaction 

if not globals().has_key('log'):
    log = virtualchain.session.log

#import bitcoin
import pyreddcointools
import json
import time

try:
    from .config import *
    from .b40 import *
except:
    # hack around relative paths
    import sys 
    import os
    sys.path.append(os.path.dirname(__file__))
    from config import *
    from b40 import *

def add_magic_bytes(hex_script, testset=False):
    if not testset:
        magic_bytes = MAGIC_BYTES_MAINSET
    else:
        magic_bytes = MAGIC_BYTES_TESTSET
    return hexlify(magic_bytes) + hex_script


def is_name_valid( fqn ):
    """
    Is a fully-qualified name acceptable?
    Return True if so
    Return False if not
    """

    if fqn.count( "." ) != 1:
        return False

    name, namespace_id = fqn.split(".")

    if len(name) == 0 or len(namespace_id) == 0:
        return False 

    if not is_b40( name ) or "+" in name or "." in name:
        return False 

    if not is_b40( namespace_id ) or "+" in namespace_id or "." in namespace_id:
        return False
    
    name_hex = hexlify(name)
    if len(name_hex) > LENGTHS['blockchain_id_name'] * 2:
       # too long
       return False 

    return True


def blockstore_script_to_hex(script):
    """ Parse the readable version of a script, return the hex version.
    """
    hex_script = ''
    parts = script.split(' ')
    for part in parts:
       
        if part in NAME_OPCODES.keys():
            try:
                hex_script += '%0.2x' % ord(NAME_OPCODES[part])
            except:
                raise Exception('Invalid opcode: %s' % part)
        
        elif part.startswith("0x"):
            # literal hex string
            hex_script += part[2:]
            
        elif is_valid_int(part):
            hex_part = '%0.2x' % int(part)
            if len(hex_part) % 2 != 0:
               hex_part = '0' + hex_part
               
            hex_script += hex_part
         
        elif is_hex(part) and len(part) % 2 == 0:
            hex_script += part
            
        else:
            raise ValueError('Invalid script (at %s), contains invalid characters: %s' % (part, script))
         
    if len(hex_script) % 2 != 0:
        raise ValueError('Invalid script: must have an even number of chars (got %s).' % hex_script)
     
    return hex_script


# generate a pay-to-pubkeyhash script from a public key.
def get_script_pubkey( public_key ):
   
   hash160 = ReddcoinPublicKey(public_key).hash160()
   script_pubkey = script_to_hex( 'OP_DUP OP_HASH160 %s OP_EQUALVERIFY OP_CHECKSIG' % hash160)
   return  script_pubkey


def tx_deserialize( tx_hex ):
    """
    Given a serialized transaction, return its inputs, outputs, locktime, and version
    Each input will have:
    * transaction_hash: string 
    * output_index: int 
    * [optional] sequence: int 
    * [optional] script_sig: string
    
    Each output will have:
    * value: int 
    * script_hex: string 
    """
    
    tx = pyreddcointools.deserialize( tx_hex )
    inputs = tx["ins"]
    outputs = tx["outs"]
    
    ret_inputs = []
    ret_outputs = []
    
    for inp in inputs:
        ret_inp = {
            "transaction_hash": inp["outpoint"]["hash"],
            "output_index": int(inp["outpoint"]["index"]),
        }
        
        if "sequence" in inp:
            ret_inp["sequence"] = int(inp["sequence"])
            
        if "script" in inp:
            ret_inp["script_sig"] = inp["script"]
            
        ret_inputs.append( ret_inp )
        
    for out in outputs:
        ret_out = {
            "value": out["value"],
            "script_hex": out["script"]
        }
        
        ret_outputs.append( ret_out )
        
    return ret_inputs, ret_outputs, tx["locktime"], tx["version"]


def tx_serialize( inputs, outputs, locktime=0, version=TX_VERSION ):
    """
    Given (possibly signed) inputs and outputs, convert them 
    into a hex string.
    Each input must have:
    * transaction_hash: string 
    * output_index: int 
    * [optional] sequence: int 
    * [optional] script_sig: str 
    
    Each output must have:
    * value: int 
    * script_hex: string
    """
    
    tmp_inputs = []
    tmp_outputs = []

    timestamp = int(time.time())
    
    # convert to a format bitcoin understands
    for inp in inputs:
        tmp_inp = {
            "outpoint": {
                "index": inp["output_index"],
                "hash": inp["transaction_hash"]
            }
        }
        if "sequence" in inp:
            tmp_inp["sequence"] = inp["sequence"]
        else:
            tmp_inp["sequence"] = pyreddcoin.UINT_MAX 
            
        if "script_sig" in inp:
            tmp_inp["script"] = inp["script_sig"]
        else:
            tmp_inp["script"] = ""
            
        tmp_inputs.append( tmp_inp )
        
    for out in outputs:
        tmp_out = {
            "value": out["value"],
            "script": out["script_hex"]
        }
        
        tmp_outputs.append( tmp_out )
        
    txobj = {
        "time": timestamp,
        "locktime": locktime,
        "version": version,
        "ins": tmp_inputs,
        "outs": tmp_outputs
    }
    
    return pyreddcointools.serialize( txobj )
    

def tx_serialize_and_sign_multi( inputs, outputs, private_keys ):
    """
    Given a list of inputs, outputs, private keys, and optionally a partially-signed transaction:
    * make a transaction out of the inputs and outputs 
    * sign input[i] with private_key[i]
    
    Return the signed tx on success
    """
    
    if len(inputs) != len(private_keys):
        raise Exception("Must have the same number of private keys as inputs")
    
    private_key_objs = []
    for pk in private_keys:
        if isinstance( pk, pyreddcoin.ReddcoinPrivateKey ):
            private_key_objs.append( pk )
        else:
            private_key_objs.append( pyreddcoin.ReddcoinPrivateKey( pk ) )
            
    # make the transaction 
    unsigned_tx = tx_serialize( inputs, outputs )
    
    # sign with the appropriate private keys 
    for i in xrange(0, len(inputs)):
        signed_tx = pyreddcointools.sign( unsigned_tx, i, private_key_objs[i].to_hex() )
        unsigned_tx = signed_tx 
        
    return unsigned_tx 


def tx_serialize_and_sign( inputs, outputs, private_key ):
    """
    Create a serialized transaction and sign each input with the same private key.
    Useful for making a tx that is sent from one key.
    """
    return tx_serialize_and_sign_multi( inputs, outputs, [private_key] * len(inputs) )


def tx_extend( partial_tx_hex, new_inputs, new_outputs ):
    """
    Given an unsigned serialized transaction, add more inputs and outputs to it.
    """
    
    # recover tx
    inputs, outputs, locktime, version = tx_deserialize( partial_tx_hex )
    
    # new tx
    new_unsigned_tx = tx_serialize( inputs + new_inputs, outputs + new_outputs, locktime, version )
        
    return new_unsigned_tx

    
def tx_output_is_op_return( output ):
    """
    Is an output's script an OP_RETURN script?
    """
    return int( output["script_hex"][0:2], 16 ) == pyreddcoin.opcodes.OP_RETURN
    
    
def tx_output_is_burn( output ):
    """
    Is an output's script an OP_RETURN script to our burn address?
    """
    addr = pyreddcoin.script_hex_to_address( output['script_hex'], version_byte=61 )
    return (addr == BLOCKSTORE_BURN_ADDRESS)


def tx_make_subsidization_output( payer_utxo_inputs, payer_address, op_fee, dust_fee ):
    """
    Given the set of utxo inputs for both the client and payer, as well as the client's 
    desired tx outputs, generate the inputs and outputs that will cause the payer to pay 
    the operation's fees and dust fees.
    
    The client should send its own address as an input, with the same amount of BTC as the output.
    
    Return the payer output to include in the transaction on success, which should pay for the operation's
    fee and dust.
    """

    return {
        "script_hex": make_pay_to_address_script( payer_address ),
        "value": calculate_change_amount( payer_utxo_inputs, op_fee, dust_fee )
    }


def tx_analyze_inputs( inputs, bitcoind_opts ):
    """
    Given a set of client inputs (an array of {"transaction_hash": ..., "output_index": int}), go 
    and fetch the set of transactions for each input, and return the set of values for 
    each input.  Include "value", "addresses", and "script_pubkey"
    
    Return the updated input listing on success.
    """
    
    ret_inputs = []
    
    for i in xrange(0, len(inputs)):
        
        inp = inputs[i]
        ret_inp = {}
        ret_inp.update( inp )
        
        input_tx_hex = getrawtransaction( bitcoind_opts, ret_inp["transaction_hash"] )
        if input_tx_hex is None:
            raise Exception("No such transaction '%s'" % ret_inp["transaction_hash"])
        
        tx_inputs, tx_outputs, locktime, version = tx_deserialize( str(input_tx_hex) )
        
        prev_tx_output = tx_outputs[ ret_inp["output_index"] ]
        
        ret_inp["value"] = int(prev_tx_output['value'])
        ret_inp["script_pubkey"] = prev_tx_output['script_hex']
        
        ret_inputs.append( ret_inp )
        
    return ret_inputs
    
def best_fit_selection(amount, unspents):
    print ("in Best Fit")
    value = 0
    unspent_candidates = []

    if amount is not None:
        amount = max( amount, DEFAULT_DUST_FEE ) + DEFAULT_DUST_FEE
    else:
        #use DEFAULT_DUST_FEE as the amount we need
        amount = DEFAULT_DUST_FEE


    while value < amount:
        difference = amount - value
        print ("Amount - Difference = %i" % difference)
        # find first the smaller transactions
        for tx in unspents:
            tx_amount = tx['value']
            if tx_amount < difference:
                print ("looking for smaller tx candidates")
                print ("tx amount = %i" % tx_amount)
                value += tx_amount
                unspent_candidates.append(tx)
                unspents.remove(tx)
                break
        # find the first bigger transaction
        for tx in unspents:
            tx_amount = tx['value']
            if tx_amount > difference:
                print ("looking for larger tx candidates")
                print ("tx amount = %i" % tx_amount)
                value += tx_amount
                unspent_candidates.append(tx)
                unspents.remove(tx)
                break

    print ("Bestfit candidates = %s" % unspent_candidates)

    return unspent_candidates

def tx_dust_fee( tx_hex ):
    """
    Given a serialized transaction, calculate a minimum dust fee
    """

    # fee in BTC is 0.0001 * num_kilobytes
    # fee in satoshis:
    # 10**8 * 0.0001 * (len(tx_hex) / 1000) == 10**4 * len(tx_hex) / 1000 == 10 * len(tx_hex)
    return 10 * len(tx_hex)


def tx_dust_fee_from_inputs_and_outputs( inputs, outputs ):
    """
    Calculate (about) how much dust to provide, given a list of inputs and outputs
    """

    # throw-away key to use as a place-holder
    pk = pyreddcoin.ReddcoinPrivateKey('5HsbxjxLx1gTzvhWTPZ7DZ91xbGvHHuVxCXJqfruCc6tEog3M2k')
    serialized_tx = tx_serialize_and_sign( inputs, outputs, pk )
    return tx_dust_fee( serialized_tx )
    
   
def tx_serialize_subsidized_tx( blockstore_tx, payer_privkey_hex, payer_utxo_inputs, payer_address, dust_fee, op_fee ):
    """
    Make a signed serialized transaction with the given operation and dust fees
    """
    tx_inputs, tx_outputs, locktime, version = tx_deserialize( blockstore_tx )

    subsidy_output = tx_make_subsidization_output( payer_utxo_inputs, payer_address, op_fee, dust_fee )
    
    # add our inputs and output
    subsidized_tx = tx_extend( blockstore_tx, payer_utxo_inputs, [subsidy_output] )
   
    # sign each of our inputs with our key, but use SIGHASH_ANYONECANPAY so the client can sign its inputs
    for i in xrange( 0, len(payer_utxo_inputs)):
        idx = i + len(tx_inputs)
        subsidized_tx = pyreddcointools.sign( subsidized_tx, idx, payer_privkey_hex, hashcode=pyreddcointools.SIGHASH_ANYONECANPAY )
    
    return subsidized_tx


def tx_make_subsidizable( blockstore_tx, fee_cb, max_fee, subsidy_key, utxo_client ):
    """
    Given an unsigned serialized transaction from Blockstore, make it into a subsidized transaction 
    for the client to go sign off on.
    * Add subsidization inputs/outputs
    * Make sure the subsidy does not exceed the maximum subsidy fee
    * Sign our inputs with SIGHASH_ANYONECANPAY
    """
   
    # get subsidizer key info
    private_key_obj, payer_address, payer_utxo_inputs = analyze_private_key(subsidy_key, utxo_client)
    
    tx_inputs, tx_outputs, locktime, version = tx_deserialize( blockstore_tx )

    # what's the fee?  does it exceed the subsidy?
    dust_fee, op_fee = fee_cb( tx_inputs, tx_outputs )
    if dust_fee is None or op_fee is None:
        log.error("Invalid fee structure")
        return None 
    
    if dust_fee + op_fee > max_fee:
        log.error("Op fee (%s) + dust fee (%s) exceeds maximum subsidy %s" % (dust_fee, op_fee, max_fee))
        return None
    
    else:
        log.debug("%s will subsidize %s satoshi" % (pyreddcoin.ReddcoinPrivateKey( subsidy_key ).public_key().address(), dust_fee + op_fee ))
    
    # calculate how much the dust fee needs to be 
    subsidized_tx = tx_serialize_subsidized_tx( blockstore_tx, private_key_obj.to_hex(), payer_utxo_inputs, payer_address, 0, op_fee )
    dust_fee = tx_dust_fee( subsidized_tx )

    # *now* make the transaction
    subsidized_tx = tx_serialize_subsidized_tx( blockstore_tx, private_key_obj.to_hex(), payer_utxo_inputs, payer_address, dust_fee, op_fee )
    return subsidized_tx

