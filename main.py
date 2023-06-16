import sys

import trio

from samp_query import (
    Client,
    InvalidRCONPassword,
    MissingRCONPassword,
    RCONDisabled,
)


async def main(*args: str) -> str | None:
    if not (3 <= len(args) <= 4):
        return f'Usage: {args[0]} ip port [rcon_password]'

    ip, port = args[1:3]

    rcon_password = args[3] if len(args) >= 4 else None

    client = Client(ip, int(port), rcon_password)
    ping = await client.ping()
    print(ping)
    print(await client.info())

    with trio.move_on_after(2 * ping) as cancel_scope:
        print(await client.players())

    if cancel_scope.cancelled_caught:
        print('More than 100 players online, no info returned')

    print('Uses open.mp:', await client.is_omp())
    print(await client.rules())

    try:
        print(await client.rcon('varlist'))
        print(await client.rcon('players'))

    except MissingRCONPassword:
        print("You didn't specify a RCON password.")

    except RCONDisabled:
        print('RCON is disabled.')

    except InvalidRCONPassword:
        print('Invalid RCON password.')

    return None


if __name__ == '__main__':
    sys.exit(trio.run(main, *sys.argv))
