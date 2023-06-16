from __future__ import annotations
import struct
import random
from dataclasses import dataclass, field

import cchardet as chardet  # type: ignore
import trio

# Assuming ratio between max and min ping can't be higher than this
MAX_LATENCY_VARIANCE = 5


def encode_codepage(string: str) -> bytes:
    for codepage in range(1250, 1259):
        try:
            return string.encode(f'cp{codepage}')
        except UnicodeEncodeError:
            continue

    raise UnicodeEncodeError(
        'cp1250-1258',
        string,
        0,
        len(string),
        'Unable to find a suitable codepage',
    )


def pack_string(string: str, len_type: str) -> bytes:
    format = f'<{len_type}'
    return struct.pack(format, len(string)) + encode_codepage(string)


def unpack_string(data: bytes, len_type: str) -> tuple[str, bytes]:
    format = f'<{len_type}'
    size = struct.calcsize(format)
    str_len, data = *struct.unpack_from(format, data), data[size:]
    string, data = data[:str_len], data[str_len:]
    encoding = chardet.detect(string)['encoding'] or 'ascii'
    return string.decode(encoding), data


class MissingRCONPassword(Exception):
    pass


class InvalidRCONPassword(Exception):
    pass


class RCONDisabled(Exception):
    pass


@dataclass
class ServerInfo:
    name: str
    password: bool
    players: int
    max_players: int
    gamemode: str
    language: str

    @classmethod
    def from_data(cls, data: bytes) -> ServerInfo:
        password, players, max_players = struct.unpack_from('<?HH', data)
        data = data[5:]  # _Bool + short + short, see above
        name, data = unpack_string(data, 'I')
        gamemode, data = unpack_string(data, 'I')
        language, data = unpack_string(data, 'I')

        assert not data  # We consumed all the buffer

        return cls(
            name=name,
            password=password,
            players=players,
            max_players=max_players,
            gamemode=gamemode,
            language=language,
        )


@dataclass
class PlayerInfo:
    name: str
    score: int

    @classmethod
    def from_data(cls, data: bytes) -> tuple[PlayerInfo, bytes]:
        name, data = unpack_string(data, 'B')
        score = struct.unpack_from('<i', data)[0]
        data = data[4:]  # int, see above

        return cls(
            name=name,
            score=score,
        ), data


@dataclass
class PlayerList:
    players: list[PlayerInfo]

    @classmethod
    def from_data(cls, data: bytes) -> PlayerList:
        player_count = struct.unpack_from('<H', data)[0]
        data = data[2:]  # short, see above
        players = []

        for _ in range(player_count):
            player, data = PlayerInfo.from_data(data)
            players.append(player)

        assert not data  # We consumed all the buffer

        return cls(players=players)


@dataclass
class Rule:
    name: str
    value: str

    @classmethod
    def from_data(cls, data: bytes) -> tuple[Rule, bytes]:
        name, data = unpack_string(data, 'B')
        value, data = unpack_string(data, 'B')

        return cls(
            name=name,
            value=value,
        ), data


@dataclass
class RuleList:
    rules: list[Rule]

    @classmethod
    def from_data(cls, data: bytes) -> RuleList:
        rule_count = struct.unpack_from('<H', data)[0]
        data = data[2:]  # short, see above
        rules = []

        for _ in range(rule_count):
            rule, data = Rule.from_data(data)
            rules.append(rule)

        assert not data  # We consumed all the buffer

        return cls(rules=rules)


@dataclass
class Client:
    ip: str
    port: int
    rcon_password: str | None = field(default=None, repr=False)

    prefix: bytes | None = field(default=None, repr=False)
    _socket: trio.socket.SocketType | None = field(default=None, repr=False)

    async def connect(self) -> None:
        family, type, proto, _, (ip, *_) = (await trio.socket.getaddrinfo(
            self.ip,
            self.port,
            family=trio.socket.AF_INET,
            proto=trio.socket.IPPROTO_UDP,
        ))[0]
        self.ip = ip
        self._socket = socket = trio.socket.socket(family, type, proto)
        await socket.connect((self.ip, self.port))
        self.prefix = (
            b'SAMP'
            + trio.socket.inet_aton(self.ip)
            + self.port.to_bytes(2, 'little')
        )

    async def send(self, opcode: bytes, payload: bytes = b'') -> None:
        if not self._socket:
            await self.connect()

        assert self._socket and self.prefix
        await self._socket.send(self.prefix + opcode + payload)

    async def receive(self, header: bytes = b'') -> bytes:
        assert self._socket

        while True:
            data = await self._socket.recv(4096)

            if data.startswith(header):
                return data[len(header):]

    async def ping(self) -> float:
        payload = random.getrandbits(32).to_bytes(4, 'little')
        start_time = trio.current_time()
        await self.send(b'p', payload)
        assert self.prefix
        data = await self.receive(header=self.prefix + b'p' + payload)
        assert not data  # No data beyond expected header
        return trio.current_time() - start_time

    async def is_omp(self) -> bool:
        ping = await self.ping()
        payload = random.getrandbits(32).to_bytes(4, 'little')

        with trio.move_on_after(MAX_LATENCY_VARIANCE * ping):
            await self.send(b'o', payload)
            assert self.prefix
            data = await self.receive(header=self.prefix + b'o' + payload)
            assert not data  # No data beyond expected header
            return True

        return False

    async def info(self) -> ServerInfo:
        await self.send(b'i')
        assert self.prefix
        data = await self.receive(header=self.prefix + b'i')
        return ServerInfo.from_data(data)

    async def players(self) -> PlayerList:
        await self.send(b'c')
        assert self.prefix
        data = await self.receive(header=self.prefix + b'c')
        return PlayerList.from_data(data)

    async def rules(self) -> RuleList:
        await self.send(b'r')
        assert self.prefix
        data = await self.receive(header=self.prefix + b'r')
        return RuleList.from_data(data)

    async def rcon(self, command: str) -> str:
        if not self.rcon_password:
            raise MissingRCONPassword()

        ping = await self.ping()
        payload = (
            pack_string(self.rcon_password, 'H')
            + pack_string(command, 'H')
        )
        await self.send(b'x', payload)
        assert self.prefix

        response = ''

        with trio.move_on_after(MAX_LATENCY_VARIANCE * ping) as cancel_scope:
            while True:
                start_time = trio.current_time()
                data = await self.receive(header=self.prefix + b'x')
                receive_duration = trio.current_time() - start_time
                line, data = unpack_string(data, 'H')
                assert not data
                response += line + '\n'
                cancel_scope.deadline += receive_duration

        if not response:
            raise RCONDisabled()

        if response == 'Invalid RCON password.\n':
            raise InvalidRCONPassword()

        return response[:-1]  # Strip trailing newline
