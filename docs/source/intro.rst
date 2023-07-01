samp-query is a Python library for interacting with SA-MP/open.mp servers using the query protocol. It provides functionality to query server information, retrieve player list, show rules, and execute remote console (RCON) commands.

Installation
------------

To install the library, you can use ``pip``:

.. code-block:: sh

    pip install samp-query

Features
--------

* Connect to a game server using IP address and port.
* Retrieve server information including name, player count, maximum players, gamemode, and language.
* Get a list of players currently on the server with their name and score.
* Fetch a list of rules and their values set on the server.
* Execute RCON commands on the server (requires RCON password).
