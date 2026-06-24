from __future__ import annotations

import asyncio
import json


class EventStream:
    def __init__(self) -> None:
        self.subscribers: list[asyncio.Queue] = []

    async def publish(self, event: dict) -> None:
        dead = []
        for queue in self.subscribers:
            try:
                queue.put_nowait(json.dumps(event))
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            self.subscribers.remove(queue)

    async def subscribe(self):
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.append(queue)
        try:
            while True:
                payload = await queue.get()
                yield f"data: {payload}\n\n"
        finally:
            if queue in self.subscribers:
                self.subscribers.remove(queue)


event_stream = EventStream()
