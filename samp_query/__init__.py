from __future__ import annotations
import struct
import random
import typing
from dataclasses import dataclass, field

import cchardet as chardet  # type: ignore
import trio

# Assuming ratio between max and min ping can't be higher than this
MAX_LATENCY_VARIANCE = 5


def encode_codepage(string: str) -> bytes:
    """
    Encode the given string into bytes using the first possible codepage.

    :param str string: The string to encode.
    :return: The encoded bytes.
    :rtype: bytes
    :raises UnicodeEncodeError: If no suitable codepage is found.
    """
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
    """
    Pack a string into bytes with a length prefix.

    :param str string: The string to pack.
    :param str len_type: The format specifier for the length prefix.
    :return: The packed bytes.
    :rtype: bytes
    """
    format = f'<{len_type}'
    return struct.pack(format, len(string)) + encode_codepage(string)


def unpack_string(data: bytes, len_type: str) -> tuple[str, bytes, str]:
    """
    Unpack a string from bytes with a length prefix.

    :param bytes data: The data to unpack.
    :param str len_type: The format specifier for the length prefix.
    :return: The unpacked string, the remaining data, and the detected
             encoding.
    :rtype: tuple[str, bytes]
    """
    format = f'<{len_type}'
    size = struct.calcsize(format)
    str_len, data = *struct.unpack_from(format, data), data[size:]
    string, data = data[:str_len], data[str_len:]
    encoding = chardet.detect(string)['encoding'] or 'ascii'
    return string.decode(encoding), data, encoding


class MissingRCONPassword(Exception):
    """Raised when no RCON password was provided."""


class InvalidRCONPassword(Exception):
    """Raised when an invalid RCON password is provided."""


class RCONDisabled(Exception):
    """Raised when RCON is disabled on the server or did not respond."""


class Encodings(typing.TypedDict):
    """Encoding detection sources: name, gamemode, and language."""
    name: str
    gamemode: str
    language: str


@dataclass
class ServerInfo:
    """
    Represents server information.

    :param str name: The name of the server.
    :param bool password: Indicates if the server requires a password to join.
    :param int players: The number of players on the server.
    :param int max_players:
        The maximum number of players allowed on the server.
    :param str gamemode: The current gamemode of the server.
    :param str language: The language used by the server.
    """
    name: str
    password: bool
    players: int
    max_players: int
    gamemode: str
    language: str
    encodings: Encodings

    @classmethod
    def from_data(cls, data: bytes) -> ServerInfo:
        """
        Create a ServerInfo object from the given raw data.

        :param bytes data: The data to create the ServerInfo object from.
        :return: The created ServerInfo object.
        :rtype: ServerInfo
        """
        password, players, max_players = struct.unpack_from('<?HH', data)
        data = data[5:]  # _Bool + short + short, see above
        name, data, name_encoding = unpack_string(data, 'I')
        gamemode, data, gamemode_encoding = unpack_string(data, 'I')
        language, data, language_encoding = unpack_string(data, 'I')

        assert not data  # We consumed all the buffer

        return cls(
            name=name,
            password=password,
            players=players,
            max_players=max_players,
            gamemode=gamemode,
            language=language,
            encodings=dict(
                name=name_encoding,
                gamemode=gamemode_encoding,
                language=language_encoding,
            ),
        )


@dataclass
class PlayerInfo:
    """
    Represents player information.

    :param str name: The name of the player.
    :param int score: The score of the player.
    """
    name: str
    score: int

    @classmethod
    def from_data(cls, data: bytes) -> tuple[PlayerInfo, bytes]:
        """
        Create a PlayerInfo object from the given raw data.

        :param bytes data: The data to create the PlayerInfo object from.
        :return: The created PlayerInfo object and the remaining data.
        :rtype: tuple[PlayerInfo, bytes]
        """
        # Player name can't really be anything else than ASCII
        name, data, _ = unpack_string(data, 'B')
        score = struct.unpack_from('<i', data)[0]
        data = data[4:]  # int, see above

        return cls(
            name=name,
            score=score,
        ), data


@dataclass
class PlayerList:
    """
    Represents a list of players.

    :param list[PlayerInfo] players: The list of players.
    """
    players: list[PlayerInfo]

    @classmethod
    def from_data(cls, data: bytes) -> PlayerList:
        """
        Create a PlayerList object from the given raw data.

        :param bytes data: The data to create the PlayerList object from.
        :return: The created PlayerList object.
        :rtype: PlayerList
        """
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
    """
    Represents a server rule.

    :param str name: The name of the rule.
    :param str value: The value of the rule.
    """
    name: str
    value: str
    encoding: str

    @classmethod
    def from_data(cls, data: bytes) -> tuple[Rule, bytes]:
        """
        Create a Rule object from the given raw data.

        :param bytes data: The data to create the Rule object from.
        :return: The created Rule object and the remaining data.
        :rtype: tuple[Rule, bytes]
        """
        name, data, _ = unpack_string(data, 'B')
        value, data, encoding = unpack_string(data, 'B')

        return cls(
            name=name,
            value=value,
            encoding=encoding,
        ), data


@dataclass
class RuleList:
    """
    Represents a list of server rules.

    :param list[Rule] rules: The list of rules.
    """
    rules: list[Rule]

    @classmethod
    def from_data(cls, data: bytes) -> RuleList:
        """
        Create a RuleList object from the given raw data.

        :param bytes data: The data to create the RuleList object from.
        :return: The created RuleList object.
        :rtype: RuleList
        """
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
    """
    Main query client class to interact with a given game server.

    :param str ip: The IP address of the server.
    :param int port: The port number of the server.
    :param str | None rcon_password:
        The RCON password for the server (optional).
    """
    ip: str
    port: int
    rcon_password: str | None = field(default=None, repr=False)

    prefix: bytes | None = field(default=None, repr=False)
    _socket: trio.socket.SocketType | None = field(default=None, repr=False)

    async def connect(self) -> None:
        """Connect to the server (called automatically)."""
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
        """
        Send a query message to the server.

        :param bytes opcode: The opcode of the message.
        :param bytes payload: The payload of the message (optional).
        """
        if not self._socket:
            await self.connect()

        assert self._socket and self.prefix
        await self._socket.send(self.prefix + opcode + payload)

    async def receive(self, header: bytes = b'') -> bytes:
        """
        Receive a query response from the server.

        :param bytes header: The expected header of the response (optional).
        :return: The received response.
        :rtype: bytes
        """
        assert self._socket

        while True:
            data = await self._socket.recv(4096)

            if data.startswith(header):
                return data[len(header):]

    async def ping(self) -> float:
        """
        Send a ping request to the server and measure the round-trip time.

        :return: The round-trip time in seconds.
        :rtype: float
        """
        payload = random.getrandbits(32).to_bytes(4, 'little')
        start_time = trio.current_time()
        await self.send(b'p', payload)
        assert self.prefix
        data = await self.receive(header=self.prefix + b'p' + payload)
        assert not data  # No data beyond expected header
        return trio.current_time() - start_time

    async def is_omp(self) -> bool:
        """
        Check if the server uses open.mp.

        :return: True if the server uses open.mp, False otherwise.
        :rtype: bool
        """
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
        """
        Retrieve server information.

        :return: The server information.
        :rtype: ServerInfo
        """
        await self.send(b'i')
        assert self.prefix
        data = await self.receive(header=self.prefix + b'i')
        return ServerInfo.from_data(data)

    async def players(self) -> PlayerList:
        """
        Retrieve the list of players on the server.

        :return: The list of players.
        :rtype: PlayerList
        """
        await self.send(b'c')
        assert self.prefix
        data = await self.receive(header=self.prefix + b'c')
        return PlayerList.from_data(data)

    async def rules(self) -> RuleList:
        """
        Retrieve the list of server rules.

        :return: The list of rules.
        :rtype: RuleList
        """
        await self.send(b'r')
        assert self.prefix
        data = await self.receive(header=self.prefix + b'r')
        return RuleList.from_data(data)

    async def rcon(self, command: str) -> str:
        """
        Execute a RCON command on the server.

        :param str command: The RCON command to execute.
        :return: The response from the server.
        :rtype: str
        :raises MissingRCONPassword: If the RCON password is missing.
        :raises InvalidRCONPassword: If an invalid RCON password is provided.
        :raises RCONDisabled:
            If RCON is disabled on the server or no response was received.
        """
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
                line, data, _ = unpack_string(data, 'H')
                assert not data
                response += line + '\n'
                cancel_scope.deadline += receive_duration

        if not response:
            raise RCONDisabled()

        if response == 'Invalid RCON password.\n':
            raise InvalidRCONPassword()

        return response[:-1]  # Strip trailing newline
