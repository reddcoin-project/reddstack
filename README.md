
# Blockstore

[![PyPI](https://img.shields.io/pypi/v/blockstore.svg)](https://pypi.python.org/pypi/blockstore/)
[![PyPI](https://img.shields.io/pypi/dm/blockstore.svg)](https://pypi.python.org/pypi/blockstore/)
[![Slack](http://slack.blockstack.org/badge.svg)](http://slack.blockstack.org/)

## Name registrations on the bitcoin blockchain

Blockstore enables human-readable name registrations on the Bitcoin blockchain,
along with the ability to store associated data in external datastores. You can
use it to register globally unique names, associate data with those names, and
transfer them between Bitcoin addresses. Anyone can perform lookups on those
names and securely obtain the data associated with them.

Blockstore uses the Bitcoin blockchain for storing name operations and data
hashes, and the Kademlia-based distributed hash table (DHT) and other external
datastores for storing the full data files outside of the blockchain.

The last stable release is [v.0.10.1](https://github.com/blockstack/blockstore/tree/v0.0.10).
## Table of contents

* [Overview](#overview)
* [Quick start](#quick-start)
* [Getting started](#getting-started)
* [What’s included](#whats-included)
* [Documentation](#documentation)
* [Design decisions](#design-decisions)
* [Protocol details](#protocol-details)
* [Definitions](#definitions)
* [FAQ](#faq)
* [Community](#community)
* [Contributing](#contributing)
* [Copyright and license](#copyright-and-license)

## Overview

This document is meant to provide an overview of how to get blockstore up and
running on Mac OS X, Linux, and other UNIX-like operating systems. It is meant
to be a high-level walk-through for application developers who want to run
their own Blockstore instance. Basic proficiency with the command-line is
required.

## Quick start

The fastest way to get started with blockstore is to use pip:

```
pip install blockstore
```

If you encounter any problems during the pip install, see the [detailed install
instructions](https://github.com/blockstack/blockstore/wiki/Installation).

## Debian package

We also release blockstore as a debian package. First get GPG key of one of our developers:

> wget -O - http://packages.blockstack.org/jude@onename.com.gpg.key | sudo apt-key add -

Then add packages.blockstack.org to your sources list:

>  sudo vi /etc/apt/sources.list

and add "deb http://packages.blockstack.org jessie main" at the end of the file.

Now you can install blockstore through apt-get:

> sudo apt-get update && sudo apt-get install blockstore

## Getting started

Start blockstored and index the blockchain:

```
$ blockstored start
```

Then, perform name lookups:

```
$ blockstore-cli lookup werner.id
{
    "address": "1KRca8gGiCiTNGR65iXMPQ6d5fisDdN3ZF",
    "first_registered": 374132,
    "last_renewed": 374132,
    "revoked": false,
    "sender": "76a914ca19f0c96683b6cabfb5c9a406bebc6771d8ede488ac",
    "sender_pubkey": "0411d88aa37a0eea476a5b63ca4b1cd392ded830865...",
    "value_hash": "3dafd5f42798df3045cd2eb70a71cccf8500e6d4"
}

```

Next, learn how to register names of your own, as well as transfer them and
associate data with them:

[Full usage docs](../../wiki/Usage)

## What's included

Within the install you'll find the following directories and files. You'll see
something like this:

```
blockstore/
├── bin/
│   ├── blockstored
│   └── README.md
├── blockstore/
│   ├── __init__.py
│   ├── blockmirrord.py
│   ├── blockmirrord.tac
│   ├── blockstore.tac
│   ├── blockstore-testset.tac
│   ├── blockstored.py
│   ├── build_nameset.py
│   ├── coinkit.patch
│   ├── dht/
│   │   ├── __init__.py
│   │   ├── image/
│   │   │   ├── Dockerfile
│   │   │   └── README.md
│   │   ├── plugin.py
│   │   ├── README.md
│   │   ├── server.tac
│   │   ├── storage.py
│   │   └── test.py
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── b40.py
│   │   ├── config.py
│   │   ├── hashing.py
│   │   ├── nameset/
│   │   │   ├── __init__.py
│   │   │   ├── namedb.py
│   │   │   └── virtualchain_hooks.py
│   │   ├── operations/
│   │   │   ├── __init__.py
│   │   │   ├── nameimport.py
│   │   │   ├── namespacepreorder.py
│   │   │   ├── namespaceready.py
│   │   │   ├── namespacereveal.py
│   │   │   ├── preorder.py
│   │   │   ├── register.py
│   │   │   ├── revoke.py
│   │   │   ├── transfer.py
│   │   │   └── update.py
│   │   ├── README.md
│   │   └── scripts.py
│   ├── tests/
│   │   └── unit_tests.py
│   └── TODO.txt
├── Dockerfile
├── images/
│   └── Dockerfile
├── LICENSE
├── MANIFEST.in
├── README.md
├── requirements.txt
└── setup.py
```

## Documentation

Blockstore’s detailed documentation is located included in this repo’s
[Wiki](https://github.com/blockstack/blockstore/wiki).


## Design decisions

[Design decisions](../../wiki/Design-Decisions)


## Protocol details

[Protocol details](../../wiki/Protocol-Details)

## Definitions

[Definitions](../../wiki/Definitions)

## FAQ

[FAQ](../../wiki/FAQ)

## Community

The Blockstack community is a group of blockchain developers
coming together to define and develop a set of software protocols and tools to
serve as a common backend for blockchain-powered decentralized applications. We
are opening membership to the public, welcoming all developers and organizations
that are interested in joining the community and contributing to Blockstack
development.

For more information, please visit the community website @
[Blockstack.org](http://blockstack.org)

Our community is welcoming on both our [public
Slack](http://chat.blockstack.org/) and [public
Forum](http://forum.blockstack.org/).

## Contributing

We welcome any small or big contributions! Please take a moment to
[review the following guidelines](https://guides.github.com/activities/contributing-to-open-source/)
in order to make the contribution process easy and effective for everyone involved.

We follow the [git flow model](https://github.com/nvie/gitflow)
for managing development. This means that the [develop branch](https://github.com/blockstack/blockstore/tree/develop)
has the most recent version under development and master has the last stable release.

The main authors of Blockstore are:

**[Jude Nelson](http://onename.com/judecn)** ([@judecnelson](https://twitter.com/judecnelson))

**[Muneeb Ali](http://onename.com/muneeb)** ([@muneeb](https://twitter.com/muneeb))

**[Ryan Shea](http://onename.com/ryan)** ([@ryaneshea](https://twitter.com/ryaneshea))

Along with [code contributors](../../graphs/contributors) and other
[people who've helped in various ways](../../wiki/Contributors).

## Copyright and license

Code and documentation copyright 2015 by Blockstack.org. 

Code released under
[the GPL v3 license](http://www.gnu.org/licenses/quick-guide-gplv3.en.html).
Docs released under [Creative Commons](http://creativecommons.org/).

