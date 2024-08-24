import json

import trio
import time

import httpx

response_times = []
limiter_size = 1
num_requests = 1


async def send(client, url, limiter: trio.CapacityLimiter):
    async with limiter:
        response = await client.get(url, timeout=10)
        print(response.status_code)
        response_time = response.elapsed.total_seconds()
        status_code = response.status_code
        response_times.append({"status_code": status_code, "response_time": response_time})


async def main():
    limiter = trio.CapacityLimiter(limiter_size)
    async with httpx.AsyncClient(http2=True,
                                 verify=False,
                                 ) as client:
        try:
            async with trio.open_nursery() as nursery:
                for _ in range(num_requests):
                    nursery.start_soon(send, client, "", limiter)
        except httpx.ReadTimeout:
            print("ReadTimeout")

    with open(f"response_times_{limiter_size}.json", "w") as f:
        json.dump(response_times, f, indent=4)


trio.run(main)
