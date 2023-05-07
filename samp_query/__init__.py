from __future__ import annotations
import struct
import random
from dataclasses import dataclass, field

import cchardet as chardet  # type: ignore
import trio


def unpack_string(data: bytes) -> tuple[str, bytes]:
    str_len, data = *struct.unpack_from('<I', data), data[4:]
    string, data = data[:str_len], data[str_len:]
    encoding: str = chardet.detect(string)['encoding']
    return string.decode(encoding), data


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
        name, data = unpack_string(data)
        gamemode, data = unpack_string(data)
        language, data = unpack_string(data)

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
class Client:
    ip: str
    port: int
    rcon_password: str | None = field(default=None, repr=False)

    _socket: trio.socket.SocketType | None = field(default=None, repr=False)
    _prefix: bytes | None = field(default=None, repr=False)

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
        self._prefix = (
            b'SAMP'
            + trio.socket.inet_aton(self.ip)
            + self.port.to_bytes(2, 'little')
        )

    async def send(self, opcode: bytes, payload: bytes = b'') -> None:
        if not self._socket:
            await self.connect()

        assert self._socket and self._prefix
        await self._socket.send(self._prefix + opcode + payload)

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
        assert self._prefix
        data = await self.receive(header=self._prefix + b'p' + payload)
        assert not data  # No data beyond expected header
        return trio.current_time() - start_time

    async def info(self) -> ServerInfo:
        await self.send(b'i')
        assert self._prefix
        data = await self.receive(header=self._prefix + b'i')
        return ServerInfo.from_data(data)
