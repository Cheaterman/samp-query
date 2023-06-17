import sys

import trio

from samp_query import (
    Client,
    InvalidRCONPassword,
    RCONDisabled,
)

TIMEOUT = 5


def prompt(text: str, default: bool = False) -> bool:
    choices = ['y', 'n']
    default_index = 0 if default is True else 1
    choices[default_index] = choices[default_index].upper()
    choices_text = '/'.join(choices)
    valid_choices = ('y', 'yes', 'n', 'no')

    while True:
        try:
            response = input(f'{text} ({choices_text}) ').lower()
        except EOFError:
            print()
            return False

        if not response:
            return default

        if response not in valid_choices:
            print(
                f'Invalid response {response}. Valid choices are:',
                ', '.join(repr(choice) for choice in valid_choices)
            )
            continue

        return response.startswith('y')


async def main(*args: str) -> str | None:
    header = 'samp-query RCON client'
    print(header)
    print('=' * len(header), end='\n\n')

    if len(args) != 4:
        return f'Usage: {args[0]} host port rcon_password'

    host, port, rcon_password = args[1:]
    client = Client(host, int(port), rcon_password)

    print(f'Connecting to {host}:{port}...')

    try:
        with trio.fail_after(TIMEOUT):
            ping = await client.ping()
            info = await client.info()
            is_omp = await client.is_omp()

    except (trio.TooSlowError, ConnectionRefusedError):
        return f'Server at {host}:{port} is offline.'

    print('Connected.', end='\n\n')

    title = 'Server info:'
    print(title)
    print('-' * len(title))
    print(f'Name: {info.name}')
    print(f'Gamemode: {info.gamemode}')
    print(f'Language: {info.language}')
    print(f'Players: {info.players}/{info.max_players}')
    print(f'Ping: {ping * 1000:.0f}ms')
    print('Password:', 'Yes' if info.password else 'No')
    print('Is open.mp:', 'Yes' if is_omp else 'No', end='\n\n')

    try:
        await client.rcon('echo')

    except RCONDisabled:
        return f'RCON is disabled on {host}:{port}.'

    except InvalidRCONPassword:
        return f'Invalid RCON password for {host}:{port}.'

    while True:
        try:
            command = input(f'rcon@{host}:{port} # ')
        except EOFError:
            print()
            break

        if not command:
            continue

        if command == 'quit':
            break

        if command == 'exit':
            if not prompt(
                'Are you sure you want to shut your server down?'
            ):
                continue

            try:
                await client.rcon(command)
            except RCONDisabled:
                pass  # Yes, it's very much disabled the hard way now.

            break

        try:
            # Safety margins can't hurt here.
            with trio.fail_after((ping + 5) * 10):
                print(await client.rcon(command))

        except trio.TooSlowError:
            print('Unknown command or variable:', command)

        except RCONDisabled:
            print('No response.')

    print('Goodbye, have a nice day! 😁')
    return None


def run() -> str | None:
    return trio.run(main, *sys.argv)


if __name__ == '__main__':
    sys.exit(run())
