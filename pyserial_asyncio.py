import asyncio

async def open_serial_connection(**kwargs):  # pragma: no cover - test shim
    reader = asyncio.StreamReader()
    class DummyWriter:
        def write(self, data):
            pass
        async def drain(self):
            pass
        def is_closing(self):
            return False
        def close(self):
            pass
        async def wait_closed(self):
            pass
    return reader, DummyWriter()
