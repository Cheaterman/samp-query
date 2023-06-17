samp_query
==========

A SAMP query/RCON client for Python using trio.

Usage
-----

```py
client = Client(ip, int(port), rcon_password)
print(await client.info())
```
