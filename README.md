samp-query
==========

[![CI](https://github.com/Cheaterman/samp-query/actions/workflows/ci.yml/badge.svg)](https://github.com/Cheaterman/samp-query/actions/workflows/ci.yml)

![samp-query logo](https://cheaterman.github.io/samp-query/_static/favicon.ico)

samp-query is a Python library for interacting with SA-MP/open.mp servers using the query protocol.
It provides functionality to query server information, retrieve player list, show rules, and execute remote console (RCON) commands.

Installation
------------

To install the library, you can use `pip`:

```sh
pip install samp-query
```

Features
--------

* Connect to a game server using IP address and port.
* Retrieve server information including name, player count, maximum players, gamemode, and language.
* Get a list of players currently on the server with their name and score.
* Fetch a list of rules and their values set on the server.
* Execute RCON commands on the server (requires RCON password).

Usage
-----

Here's a basic example of how to use the library:

```py
import trio
from samp_query import Client


async def main():
    client = Client(
        ip='127.0.0.1',
        port=7777,
        rcon_password=None,  # Your rcon password as string
    )

    info = await client.info()
    print(f'Server Name: {info.name}')
    print(f'Player Count: {info.players}/{info.max_players}')

    player_list = await client.players()
    print('Players:')

    for player in player_list.players:
        print(f'- {player.name} (Score: {player.score})')

    rule_list = await client.rules()
    print('Rules:')

    for rule in rule_list.rules:
        print(f'- {rule.name}: {rule.value}')

    if client.rcon_password:
        response = await client.rcon('echo Hello, server!')
        print(f'RCON Response: {response}')


trio.run(main)
```

Make sure to replace `'127.0.0.1'` and `7777` with the actual IP address and port of the game server you want to connect to. If the server has RCON enabled, provide a password in the `rcon_password` attribute of the `samp_query.Client` instance (otherwise keep it None).

Documentation
-------------

For more information, you can [read the documentation](https://cheaterman.github.io/samp-query/).
