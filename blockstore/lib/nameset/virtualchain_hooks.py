#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Blockstore
    ~~~~~
    copyright: (c) 2014 by Halfmoon Labs, Inc.
    copyright: (c) 2015 by Blockstack.org
    
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
    along with Blockstore.  If not, see <http://www.gnu.org/licenses/>.
"""

# Hooks to the virtual chain's state engine that bind our namedb to the virtualchain package.

import os
from binascii import hexlify, unhexlify
import time

import pyreddcoin 
import traceback
import json
import copy
import threading

from .namedb import BlockstoreDB

from ..config import *
from ..operations import parse_preorder, parse_registration, parse_update, parse_transfer, parse_revoke, \
    parse_name_import, parse_namespace_preorder, parse_namespace_reveal, parse_namespace_ready, parse_announce, \
    get_transfer_recipient_from_outputs, get_import_update_hash_from_outputs, get_registration_recipient_from_outputs, \
    parse_preorder_multi, \
    SERIALIZE_FIELDS

import virtualchain

if not globals().has_key('log'):
    log = virtualchain.session.log

blockstore_db = None
blockstore_db_lock = threading.Lock()
last_load_time = 0
last_load_time_diff = 0

def get_burn_fee_from_outputs( outputs ):
    """
    Given the set of outputs, find the fee sent 
    to our burn address.
    
    Return the fee on success
    Return None if not found
    """
    
    ret = None
    for output in outputs:
       
        output_script = output['scriptPubKey']
        output_asm = output_script.get('asm')
        output_hex = output_script.get('hex')
        output_addresses = output_script.get('addresses')
        
        if output_asm[0:9] != 'OP_RETURN' and BLOCKSTORE_BURN_ADDRESS == output_addresses[0]:
            
            # recipient's script_pubkey and address
            ret = int(output['value']*(10**8))
            break
    
    return ret 
    

def get_public_key_hex_from_tx( inputs, address ):
    """
    Given a list of inputs and the address of one of the inputs,
    find the public key.

    This only works for p2sh and p2pkh scripts.
    """
    
    ret = None 
    
    for inp in inputs:
        
        input_scriptsig = inp.get('scriptSig', None )
        if input_scriptsig is None:
            continue 
        
        input_asm = input_scriptsig.get("asm")
        
        if len(input_asm.split(" ")) >= 2:
            
            # public key is the second hex string.  verify it matches the address
            pubkey_hex = input_asm.split(" ")[1]
            pubkey = None 
            
            try:
                pubkey = pyreddcoin.ReddcoinPublicKey( str(pubkey_hex) ) 
            except Exception, e: 
                traceback.print_exc()
                log.warning("Invalid public key '%s'" % pubkey_hex)
                continue 
            
            if address != pubkey.address():
                continue 
            
            ret = pubkey_hex
            break
        
    return ret 


def parse_blockstore_op_data( opcode, payload, sender, recipient=None, recipient_address=None, import_update_hash=None ):
    """
    Parse a string of binary data (nulldata from a blockchain transaction) into a blockstore operation.
    
    full OP_RETURN data format (once unhex'ed):
    
    0           2      3                                   40
    |-----------|------|-----------------------------------|
    magic bytes opcode  payload
    (consumed)  (arg)   (arg)
    
    We are given opcode and payload as arguments.
    
    Returns a parsed operation on success
    Returns None if no operation could be parsed.
    """

    op = None 
    data = hexlify(payload)

    if len(payload) > LENGTHS['max_op_length'] - 3:
        log.error("Data too long: %s" % len(payload))
        return None
    
    if opcode == NAME_PREORDER:
        if len(payload) >= MIN_OP_LENGTHS['preorder']:

            op = parse_preorder(payload)
            if op is not None:
                # singular preorder
                log.debug( "Parse NAME_PREORDER: %s" % data )

            else:
                # might be a multi-preorder
                log.debug( "Parse NAME_PREORDER_MULTI: %s" % data )
                op = parse_preorder_multi( payload )

        else:
            log.error( "NAME_PREORDER: invalid length %s" % len(payload) )
        
    elif opcode == NAME_REGISTRATION:
        if len(payload) >= MIN_OP_LENGTHS['registration']:
            log.debug( "Parse NAME_REGISTRATION: %s" % data )
            op = parse_registration(payload)
        else:
            log.error( "NAME_REGISTRATION: invalid length %s" % len(payload) )
        
    elif opcode == NAME_UPDATE:
        if len(payload) >= MIN_OP_LENGTHS['update']:
            log.debug( "Parse NAME_UPDATE: %s" % data )
            op = parse_update(payload)
        else:
            log.error( "NAME_UPDATE: invalid length %s" % len(payload))
        
    elif opcode == NAME_TRANSFER:
        if len(payload) >= MIN_OP_LENGTHS['transfer']:
            log.debug( "Parse NAME_TRANSFER: %s" % data )
            op = parse_transfer(payload, recipient )
        else:
            log.error( "NAME_TRANSFER: invalid length %s" % len(payload))
    
    elif opcode == NAME_REVOKE:
        if len(payload) >= MIN_OP_LENGTHS['revoke']:
            log.debug( "Parse NAME_REVOKE: %s" % data )
            op = parse_revoke(payload)
        else:
            log.error( "NAME_REVOKE: invalid length %s" % len(payload))
        
    elif opcode == NAME_IMPORT:
        if len(payload) >= MIN_OP_LENGTHS['name_import']:
            log.debug( "Parse NAME_IMPORT: %s" % data )
            op = parse_name_import( payload, recipient, import_update_hash )
        else:
            log.error( "NAME_IMPORT: invalid length %s" % len(payload))
        
    elif opcode == NAMESPACE_PREORDER:
        if len(payload) >= MIN_OP_LENGTHS['namespace_preorder']:
            log.debug( "Parse NAMESPACE_PREORDER: %s" % data)
            op = parse_namespace_preorder( payload )
        else:
            log.error( "NAMESPACE_PREORDER: invalid length %s" % len(payload))
        
    elif opcode == NAMESPACE_REVEAL:
        if len(payload) >= MIN_OP_LENGTHS['namespace_reveal']:
            log.debug( "Parse NAMESPACE_REVEAL: %s" % data )
            op = parse_namespace_reveal( payload, sender, recipient_address )
        else:
            log.error( "NAMESPACE_REVEAL: invalid length %s" % len(payload))
         
    elif opcode == NAMESPACE_READY:
        if len(payload) >= MIN_OP_LENGTHS['namespace_ready']:
            log.debug( "Parse NAMESPACE_READY: %s" % data )
            op = parse_namespace_ready( payload )
        else:
            log.error( "NAMESPACE_READY: invalid length %s" % len(payload))
   
    elif opcode == ANNOUNCE:
        if len(payload) == MIN_OP_LENGTHS['announce']:
            log.debug( "Parse ANNOUNCE: %s" % data )
            op = parse_announce( payload )
        else:
            log.error( "ANNOUNCE: invalid length %s" % (len(payload)))

    else:
        log.warning("Unrecognized op: code='%s', data=%s, len=%s" % (opcode, data, len(payload)))
        
    return op


def get_virtual_chain_name(testset=False):
   """
   (required by virtualchain state engine)
   
   Get the name of the virtual chain we're building.
   """
   
   if testset:
       return "blockstore-test"
   
   else:
       return "blockstore"


def get_virtual_chain_version():
   """
   (required by virtualchain state engine)
   
   Get the version string for this virtual chain.
   """
   return VERSION


def get_opcodes():
   """
   (required by virtualchain state engine)
   
   Get the list of opcodes we're looking for.
   """
   return OPCODES 


def get_op_processing_order():
   """
   (required by virtualchain state engine)
   
   Give a hint as to the order in which we process operations 
   """
   return OPCODES 


def get_magic_bytes():
   """
   (required by virtualchain state engine)
   
   Get the magic byte sequence for our OP_RETURNs
   """
   blockstore_opts = default_blockstore_opts( virtualchain.get_config_filename() )
   if blockstore_opts['testset']:
       return MAGIC_BYTES_TESTSET
   
   else:
       return MAGIC_BYTES_MAINSET


def get_first_block_id():
   """
   (required by virtualchain state engine)
   
   Get the id of the first block to start indexing.
   """ 
   blockstore_opts = default_blockstore_opts( virtualchain.get_config_filename() )
   start_block = None
   
   if TESTNET:
       if blockstore_opts['testset']:
           start_block = FIRST_BLOCK_TESTNET_TESTSET
       else:
           start_block = FIRST_BLOCK_TESTNET
   else:
       if blockstore_opts['testset']:
           start_block = FIRST_BLOCK_MAINNET_TESTSET
       else:
           start_block = FIRST_BLOCK_MAINNET

   return start_block


def get_db_state(disposition=None):
   """
   (required by virtualchain state engine)
   
   Callback to the virtual chain state engine.
   
   Get a handle to our state engine implementation
   (i.e. our name database)

   @disposition is for compatibility.  It is ignored
   """
   
   global blockstore_db
   global last_load_time
   global last_load_time_diff

   mtime = None
   db_filename = virtualchain.get_db_filename()
   tmp_db_filename = virtualchain.get_db_filename() + ".tmp"
   tmp_snapshot_filename = virtualchain.get_snapshots_filename() + ".tmp"
   tmp_lastblock_filename = virtualchain.get_lastblock_filename() + ".tmp"

   load_time_diff = int(time.time()) - last_load_time_diff
   if (load_time_diff % 10) == 0:
       log.info("DB last loaded %s sec ago" % load_time_diff )

   if os.path.exists(db_filename):
       sb = os.stat(db_filename)
       mtime = sb.st_mtime 

   if os.path.exists( tmp_lastblock_filename ) or (os.path.exists(tmp_db_filename) or os.path.exists(tmp_snapshot_filename)):
       log.debug("Temp lastblock exists = %s" % os.path.exists( tmp_lastblock_filename ))
       log.debug("Temp DB exists = %s" % os.path.exists( tmp_db_filename ))
       log.debug("Temp Snapshot exists = %s" % os.path.exists( tmp_snapshot_filename ))
       log.info("Skip (Re)Loading blockstore state from '%s', Saving state in progress" % db_filename )

   elif blockstore_db is None or mtime is None or not os.path.exists(db_filename) or sb.st_mtime != last_load_time or load_time_diff > DB_LOAD_AGE:
       log.info("(Re)Loading blockstore state from '%s'" % db_filename )
       blockstore_db = BlockstoreDB( db_filename )

       if mtime is not None:
          last_load_time = mtime

       last_load_time_diff = int(time.time())

   return blockstore_db


def db_parse( block_id, opcode, data, senders, inputs, outputs, fee, db_state=None ):
   """
   (required by virtualchain state engine)
   
   Parse a blockstore operation from a transaction's nulldata (data) and a list of outputs, as well as 
   optionally the list of transaction's senders and the total fee paid.
   
   Return a parsed operation, and will also optionally have:
   * "sender": the first (primary) sender's script_pubkey.
   * "address": the sender's bitcoin address
   * "fee": the total fee paid for this record.
   * "recipient": the first non-OP_RETURN output's script_pubkey.
   * "sender_pubkey": the sender's public key (hex string), if this is a p2pkh transaction

   Return None on error
   
   NOTE: the transactions that our tools put have a single sender, and a single output address.
   This is assumed by this code.
   """

   sender = None 
   recipient = None
   recipient_address = None
   import_update_hash = None
   address = None
   sender_pubkey_hex = None
   
   if len(senders) == 0:
      raise Exception("No senders for (%s, %s)" % (opcode, hexlify(data)))
  
   # the first sender is always the first non-nulldata output script hex, and by construction
   # of Blockstore, this is always the principal that issued the operation.
   if 'script_pubkey' not in senders[0].keys():
      raise Exception("No script_pubkey in sender of (%s, %s)" % (opcode, hexlify(data)))
   
   if 'addresses' not in senders[0].keys():
      log.error("No addresses in sender of (%s, %s)" % (opcode, hexlify(data)))
      return None
   
   if len(senders[0]['addresses']) != 1:
      log.error("Multisig transactions are unsupported for (%s, %s)" % (opcode, hexlify(data)))
      return None
   
   sender = str(senders[0]['script_pubkey'])
   address = str(senders[0]['addresses'][0])

   if str(senders[0]['script_type']) == 'pubkeyhash':
      sender_pubkey_hex = get_public_key_hex_from_tx( inputs, address )
   
   if sender_pubkey_hex is None:
      log.warning("No public key found for (%s, %s)" % (opcode, hexlify(data)))
   
   
   # Reddcoin is not burning fees
   # op_fee = get_burn_fee_from_outputs( outputs )
   op_fee = fee
   
   if opcode in [NAME_REGISTRATION, NAMESPACE_REVEAL]:
      # these operations have a designated recipient that is *not* the sender
      try:
         recipient = get_registration_recipient_from_outputs( outputs )
         recipient_address = pyreddcoin.script_hex_to_address( recipient, version_byte=61 )
      except Exception, e:
         log.exception(e)
         raise Exception("No registration address for (%s, %s)" % (opcode, hexlify(data)))
     
   
   if opcode in [NAME_IMPORT, NAME_TRANSFER]:
      # these operations have a designated recipient that is *not* the sender
      try:
         recipient = get_transfer_recipient_from_outputs( outputs )
         recipient_address = pyreddcoin.script_hex_to_address( recipient, version_byte=61 )
      except Exception, e:
         log.exception(e)
         raise Exception("No recipient for (%s, %s)" % (opcode, hexlify(data)))
      
      
   if opcode in [NAME_IMPORT]:
      # this operation has an update hash embedded as a phony recipient 
      try:
         import_update_hash = get_import_update_hash_from_outputs( outputs, recipient )
      except Exception, e:
         log.exception(e)
         raise Exception("No update hash for (%s, %s)" % (opcode, hexlify(data)))
     
         
   op = parse_blockstore_op_data(opcode, data, sender, recipient=recipient, recipient_address=recipient_address, import_update_hash=import_update_hash )
   
   if op is not None:
      
      # store the above ancillary data with the opcode, so our namedb can look it up later 
      if fee is not None:
         op['fee'] = fee 
         
      if op_fee is not None:
         op['op_fee'] = op_fee 
      
      op['sender'] = sender 
      op['address'] = address 
      
      if recipient is not None:
         op['recipient'] = recipient
      
      if recipient_address is not None:
         op['recipient_address'] = recipient_address
      
      if sender_pubkey_hex is not None:
         op['sender_pubkey'] = sender_pubkey_hex
      
   else:
       log.error("Invalid opcode '%s'" % opcode)
 
   return op


def db_check( block_id, checked_ops, opcode, op, txid, vtxindex, db_state=None ):
   """
   (required by virtualchain state engine)
   
   Given the block ID and a parsed operation, check to see if this is a *valid* operation.
   Is this operation consistent with blockstore's rules?
   
   checked_ops is a dict that maps opcodes to operations already checked by
   this method for this block.
   
   A name or namespace can be affected at most once per block.  If it is 
   affected more than once, then the opcode priority rules take effect, and
   the lower priority opcodes are rejected.

   Return True if it's valid; False if not.
   """

   if db_state is not None:
    
      db = db_state
      rc = False
    
      all_ops = checked_ops['virtualchain_all_ops']

      # find any collisions and mark them
      colliding_names, colliding_namespaces = db.log_prescan_find_collisions( checked_ops, all_ops, block_id )
      
      # sanity check...
      if opcode not in OPCODES:
         log.error("Unrecognized opcode '%s'" % (opcode))
         return False 
      
      # propagate txid and vtxindex data
      if not op.has_key('txid'):
          op['txid'] = str(txid)
     
      if not op.has_key('vtxindex'):
          op['vtxindex'] = vtxindex

      # check op for correctness
      if opcode == NAME_PREORDER:
         rc = db.log_preorder( checked_ops, op, block_id )

      elif opcode == NAME_REGISTRATION:
         if op['name'] not in colliding_names:
             rc = db.log_registration( checked_ops, op, block_id )
         else:
             rc = False
             log.error("COLLISION %s" % op['name'])

      elif opcode == NAME_UPDATE:
         rc = db.log_update( checked_ops, op, block_id )
      
      elif opcode == NAME_TRANSFER:
         rc = db.log_transfer( checked_ops, op, block_id )
      
      elif opcode == NAME_REVOKE:
         rc = db.log_revoke( checked_ops, op, block_id )
      
      elif opcode == NAME_IMPORT:
         rc = db.log_name_import( checked_ops, op, block_id )
         
      elif opcode == NAMESPACE_PREORDER:
         rc = db.log_namespace_preorder( checked_ops, op, block_id )
      
      elif opcode == NAMESPACE_REVEAL:
         if op['namespace_id'] not in colliding_namespaces:
             rc = db.log_namespace_reveal( checked_ops, op, block_id )
         else:
             rc = False 
             log.error("COLLISION %s" % op['namespace_id'])
      
      elif opcode == NAMESPACE_READY:
         rc = db.log_namespace_ready( checked_ops, op, block_id )
         
      elif opcode == ANNOUNCE:
         rc, announcer_id = db.log_announce( checked_ops, op, block_id )
         if rc:
             # valid announcement
             announce_hash = op['message_hash']

             # go get the text...
             announcement_text = get_announcement( announce_hash ) 
             log.critical("ANNOUNCEMENT (from %s): %s\n------BEGIN MESSAGE------\n%s\n------END MESSAGE------\n" % (announcer_id, announce_hash, announcement_text))
             
             store_announcement( announce_hash, announcement_text )

         # we do not process ANNOUNCEs, since they won't be fed into the consensus hash
         return False 

      debug_op = copy.deepcopy( op )
      if debug_op.has_key('history'):
         del debug_op['history']

      if rc:
         log.debug("ACCEPT op '%s' (%s)" % (opcode, json.dumps(debug_op, sort_keys=True)))

      else:
         log.debug("REJECT op '%s' (%s)" % (opcode, json.dumps(debug_op, sort_keys=True)))
         
      return rc
   
   else:
      log.error("No state engine defined")
      return False
   
   
def db_commit( block_id, opcode, op, txid, vtxindex, db_state=None ):
   """
   (required by virtualchain state engine)

   Advance the state of the state engine: get a list of all
   externally visible state transitions.
   
   Given a block ID and checked opcode, record it as 
   part of the database.  This does *not* need to write 
   the data to persistent storage, since save() will be 
   called once per block processed.
  
   Returns one or more new name operations on success, which will 
   be fed into virtualchain to translate into a string
   to be used to generate this block's consensus hash.
   """
   

   op_seq = None    # sequence of resulting operations from this tx
   if db_state is not None:
      
      db = db_state
      
      if op is not None:

        # committing an operation
        # pass along tx info
        if not op.has_key('txid') and txid is not None:
            op['txid'] = txid

        if not op.has_key('vtxindex') and vtxindex is not None:
            op['vtxindex'] = vtxindex
            
        op_seq = None

        if opcode == NAME_PREORDER:
            op_seq = db.commit_preorder( op, block_id )

        elif opcode == NAME_REGISTRATION:
            op_seq = db.commit_registration( op, block_id )

        elif opcode == NAME_UPDATE:
            op_seq = db.commit_update( op, block_id )

        elif opcode == NAME_TRANSFER:
            op_seq = db.commit_transfer( op, block_id )

        elif opcode == NAME_REVOKE:
            op_seq = db.commit_revoke( op, block_id )
            
        elif opcode == NAME_IMPORT:
            op_seq = db.commit_name_import( op, block_id )
            
        elif opcode == NAMESPACE_PREORDER:
            op_seq = db.commit_namespace_preorder( op, block_id )
            
        elif opcode == NAMESPACE_REVEAL:
            op_seq = db.commit_namespace_reveal( op, block_id )

        elif opcode == NAMESPACE_READY:
            op_seq = db.commit_namespace_ready( op, block_id )
     
        if type(op_seq) != list:
            op_seq = [op_seq]

        if op_seq and op_seq[0]:

            for commit_op in op_seq:
                debug_op = copy.deepcopy( commit_op )
                if debug_op.has_key('history'):
                    del debug_op['history']

                log.debug("COMMIT op '%s' (%s)" % (opcode, json.dumps(debug_op, sort_keys=True)))

      else:

        # final commit before save
        # do expirations
        log.debug("Clear all expired names at %s" % block_id )
        db.commit_name_expire_all( block_id )
        
        log.debug("Clear all expired preorders at %s" % block_id )
        db.commit_preorder_expire_all( block_id )
        
        log.debug("Clear all expired namespace preorders at %s" % block_id )
        db.commit_namespace_preorder_expire_all( block_id )
        
        log.debug("Clear all expired partial namespace imports at %s" % block_id )
        db.commit_namespace_reveal_expire_all( block_id )

        # reset for next block
        db.log_prescan_reset()
        
   else:
      log.error("No state engine defined")
      return None
  
   return op_seq


def db_save( block_id, consensus_hash, pending_ops, filename, db_state=None ):
   """
   (required by virtualchain state engine)
   
   Save all persistent state to stable storage.
   Clear out expired names in the process.
   Called once per block.
   
   Return True on success
   Return False on failure.
   """
   
   db = db_state 
   
   # remove expired names before saving
   if db is not None:
      
      # see if anything actually changed
      if len(pending_ops.get('virtualchain_ordered', [])) > 0:
          # state has changed 
          log.debug("Save database %s" % filename)
          return db.save_db( filename )
      
      else:
          
          # all good 
          return True
   
   else:
      log.error("No state engine defined")
      return False 


def sync_blockchain( bt_opts, last_block ):
    """
    synchronize state with the blockchain.
    build up the next blockstore_db
    """

    global blockstore_db, blockstore_db_lock

    log.info("Synchronizing database up to block %s" % last_block)
    db_filename = virtualchain.get_db_filename()
    tmp_db_filename = virtualchain.get_db_filename() + ".tmp"
    tmp_snapshot_filename = virtualchain.get_snapshots_filename() + ".tmp"
    tmp_lastblock_filename = virtualchain.get_lastblock_filename() + ".tmp"
    
    if os.path.exists( tmp_lastblock_filename ) or (os.path.exists(tmp_db_filename) or os.path.exists(tmp_snapshot_filename)):
      log.debug("Temp lastblock exists = %s" % os.path.exists( tmp_lastblock_filename ))
      log.debug("Temp DB exists = %s" % os.path.exists( tmp_db_filename ))
      log.debug("Temp Snapshot exists = %s" % os.path.exists( tmp_snapshot_filename ))
      log.info("Database sync already in progress for '%s', Saving state in progress" % db_filename )
    else:
      new_db = BlockstoreDB( db_filename )

      virtualchain.sync_virtualchain( bt_opts, last_block, new_db )

      # refresh
      blockstore_db_lock.acquire()
      del blockstore_db
      blockstore_db = new_db
      
      blockstore_db_lock.release()


def stop_sync_blockchain():
    """
    stop synchronizing with the blockchain
    """
    global blockstore_db, blockstore_db_lock

    if blockstore_db is None:
        return

    blockstore_db_lock.acquire()
    if blockstore_db is None:
        return 

    blockstore_db.stop_build()
    blockstore_db_lock.release()

