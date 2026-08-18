import asyncio
import logging

from construct import ConstructError

from .const import MessageType
from .structure import Length, Protocol

logger = logging.getLogger(__name__)


async def _read_and_parse(reader: asyncio.StreamReader):
    stx_byte = await reader.readexactly(1)
    if stx_byte != b"\x02":
        raise ValueError(f"Invalid STX byte: {repr(stx_byte)}")

    length_bytes = await reader.readexactly(2)
    try:
        length = Length.parse(length_bytes)
    except ConstructError as e:
        raise ValueError(f"Length parse error: {e}")

    remaining_bytes = await reader.readexactly(length - 3)

    raw_request = stx_byte + length_bytes + remaining_bytes
    try:
        request = Protocol.parse(raw_request)
    except ConstructError as e:
        raise ValueError(f"Protocol parse error: {e}")

    return request

class Communication:
    def __init__(self):
        self.reader = None
        self.writer = None

        self.reading_task = None
        self.writing_task = None

        self.rx_request_queue = asyncio.Queue()

        self.lock = asyncio.Lock()
        self.tx_request_queue = asyncio.Queue()
        self.rx_response_queue = asyncio.Queue()

    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

        self.reading_task = asyncio.create_task(self._read())
        self.writing_task = asyncio.create_task(self._write())

        try:
            await asyncio.gather(self.reading_task, self.writing_task)
        except Exception as e:
            logger.error("Error in CommunicationHandler: %s", e)
        finally:
            self.reading_task.cancel()
            self.writing_task.cancel()
            await asyncio.gather(
                self.reading_task, self.writing_task, return_exceptions=True
            )
            self.writer.close()
            await self.writer.wait_closed()

    async def _read(self):
        if self.reader is None:
            raise RuntimeError("Reader not initialized")

        try:
            while True:
                try:
                    try:
                        message = await _read_and_parse(self.reader)
                    except ValueError as e:
                        logger.error("Read and parse error: %s", e)
                        continue
                    
                    logger.debug("Received message: %s", repr(message))

                    if message.message_type == MessageType.REQUEST:
                        rx_queue = self.rx_request_queue
                    else:
                        rx_queue = self.rx_response_queue
                    
                    await rx_queue.put(message)
                except (asyncio.IncompleteReadError, asyncio.CancelledError):
                    raise
                except Exception as e:
                    logger.error("Error during reading: %s", e)
        except (asyncio.IncompleteReadError, asyncio.CancelledError):
            pass
        finally:
            logger.info("Closing reading task")

    async def _write(self):
        if self.writer is None:
            raise RuntimeError("Writer not initialized")

        try:
            while True:
                try:
                    message = await self.tx_request_queue.get()

                    logger.debug("Transmitting message: %s", repr(message))

                    self.writer.write(message)
                    await self.writer.drain()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error("Error during writing: %s", e)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Closing writing task")

    async def read_request(self):
        return await self.rx_request_queue.get()

    async def fetch(self, message, timeout: float | None = None):
        """
        Send a request and wait for response with timeout.
        
        Args:
            message: Protocol message to send
            timeout: Timeout in seconds (uses settings.comm_timeout if None)
            
        Returns:
            Protocol response message
            
        Raises:
            TimeoutError: If response not received within timeout
            CommunicationError: If communication fails
        """
        from config import settings
        from exceptions import TimeoutError as PaymentTimeoutError, CommunicationError
        
        if timeout is None:
            timeout = settings.comm_timeout
        
        async with self.lock:
            try:
                # Discard any stale responses in the queue
                while True:
                    self.rx_response_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            
            # Send request
            try:
                await self.tx_request_queue.put(message)
            except Exception as e:
                raise CommunicationError(
                    f"Failed to send request: {e}",
                ) from e
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(
                    self.rx_response_queue.get(),
                    timeout=timeout,
                )
                return response
            except asyncio.TimeoutError as e:
                raise PaymentTimeoutError(
                    f"Device did not respond within {timeout} seconds",
                    timeout=timeout,
                ) from e
