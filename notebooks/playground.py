import asyncio


async def task(name):
    print(f"{name} starts")
    await asyncio.sleep(1)  # NON-BLOCKING
    print(f"{name} ends")


if __name__ == "__main__":
    asyncio.run(task("123"))
