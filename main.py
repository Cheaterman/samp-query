import sys

import trio

from samp_query import Client


async def main(*args: str) -> str | None:
    if len(args) != 3:
        return f'Usage: {args[0]} ip port'

    ip, port = args[1:]
    client = Client(ip, int(port))
    ping = await client.ping()
    print(ping)
    print(await client.info())

    with trio.move_on_after(2 * ping) as cancel_scope:
        print(await client.players())

    if cancel_scope.cancelled_caught:
        print('More than 100 players online, no info returned')

    print('Uses open.mp:', await client.is_omp())
    print(await client.rules())
    return None


if __name__ == '__main__':
    sys.exit(trio.run(main, *sys.argv))
