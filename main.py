import sys

import trio

from samp_query import Client


async def main(*args: str) -> str | None:
    if len(args) != 3:
        return f'Usage: {args[0]} ip port'

    ip, port = args[1:]
    client = Client(ip, int(port))
    print(await client.ping())
    print(await client.info())
    return None


if __name__ == '__main__':
    sys.exit(trio.run(main, *sys.argv))
