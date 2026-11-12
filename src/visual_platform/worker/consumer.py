import asyncio
from pydantic import ValidationError
from visual_platform.events.broker import Delivery

class Consumer:
    def __init__(self,worker,broker): self.worker=worker; self.broker=broker
    async def handle(self,message):
        if len(message.body)>4096:
            await message.reject(requeue=False); return 'invalid'
        try: delivery=Delivery.model_validate_json(message.body)
        except ValidationError:
            await message.reject(requeue=False); return 'invalid'
        try:
            valid=await self.worker.db('SELECT ops.validate_delivery($1,$2)',delivery.outbox_id,delivery.task_id)
            if not valid:
                await message.reject(requeue=False); return 'invalid_reference'
            result=await self.worker.run(delivery.task_id)
        except asyncio.CancelledError: raise
        except Exception:
            # No ACK while the DB cannot establish a durable recovery point.
            await message.nack(requeue=True); await asyncio.sleep(1); return 'retry'
        await message.ack()
        return result
    async def run(self):
        tag=await self.broker.queue.consume(self.handle,no_ack=False)
        try: await asyncio.Event().wait()
        finally: await self.broker.queue.cancel(tag)
