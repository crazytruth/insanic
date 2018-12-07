import aiotask_context
import asyncio


async def test_task_context():
    aiotask_context.set("a", "b")
    a = aiotask_context.get("a")
    assert a == "b"


async def test_task_context_child():
    aiotask_context.set("a", "b")

    async def child_task(a):
        aiotask_context.set("a", a)

    await asyncio.gather(*[child_task(i) for i in range(5)])

    a = aiotask_context.get("a")
    assert a == "b"
