import asyncio
import time

import numpy as np

import httpx

response_times = []
last_median_response_time = None
delays = []
delay = 1
last_response_time = None
delay_change_time = 0


# The base value:
    # 1. Is the fastest average response time, you can get.
    # 2. The base value changes, depending on the server's load, your internet connection, and probably proxy location/load

# Too frequent requests can cause:
    # 1. Respond times to stay at a constant value, that is higher than the base value
    # 2. Respond times to continuously increase

# Too infrequent requests can cause:
    # 1. Respond times to stay at base value


def calc_delay(response_time):
    global last_median_response_time, delay

    median_response_time = np.median(response_times)
    if last_median_response_time is None:
        last_median_response_time = median_response_time
    else:
        new_delay = delay * median_response_time / response_time
        # If the new delay is higher than the current delay, increase the new delay by another 5%
        # to avoid the delay from being stuck at a constant value
        delay = new_delay if new_delay > delay else new_delay * 1.05
        last_median_response_time = median_response_time
        delays.append(delay)

async def send(client, url, lock):
    global delay, last_response_time

    async with lock:
        await asyncio.sleep(delay)

    requested = time.time()
    response = await client.get(url, timeout=10)
    print(response.status_code)
    elapsed = response.elapsed.total_seconds()
    if 200 <= response.status_code < 300 and elapsed and requested > delay_change_time:
        response_times.append(elapsed)
        if len(response_times) >= 10:
            calc_delay(elapsed)



async def main():
    lock = asyncio.Lock()
    async with httpx.AsyncClient(http2=True, verify=False) as client:
        try:
            async with asyncio.TaskGroup() as group:
                for _ in range(200):
                    group.create_task(send(client, "https://localhost:8000", lock))
        except httpx.ReadTimeout:
            print("ReadTimeout")

    with open("response_times_var.txt", "w") as f:
        f.write("\n".join(map(str, response_times)))
    with open("delays.txt", "w") as f:
        f.write("\n".join(map(str, delays)))
asyncio.run(main())
