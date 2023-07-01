Usage
-----

Here's a basic example of how to use the library:

.. code-block:: python

    import trio
    from samp_query import Client


    async def main():
        client = Client(
            ip='127.0.0.1',
            port=7777,
            rcon_password=None,  # Your rcon password as string
        )
        await client.connect()

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

Make sure to replace ``'127.0.0.1'`` and ``7777`` with the actual IP address and port of the game server you want to connect to. If the server has RCON enabled, provide a password in the ``rcon_password`` attribute of the :class:`samp_query.Client` instance (otherwise keep it None).
