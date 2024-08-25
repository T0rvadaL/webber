import trio
import httpx
import pytest
import respx
from httpx import HTTPStatusError

from .test_utils import raise_for_status_hook
from webber._client_manager import ClientManager
from webber._exceptions import AdjustmentError


@pytest.mark.parametrize("min_client_requests, max_client_requests", [(1, 1), (1, 2), (10, 1000)])
def test_valid_initialization(min_client_requests, max_client_requests, proxies_3):
    client_manager = ClientManager(proxies_3, min_client_requests, max_client_requests)
    assert client_manager.proxy_pool
    assert client_manager.min_client_requests == min_client_requests
    assert client_manager.max_client_requests == max_client_requests
    assert client_manager._last_requested == 0


@pytest.mark.parametrize("min_client_requests, max_client_requests", [(-1, 1), (0, 3), (0, 0), (1, -1)])
def test_invalid_initialization(min_client_requests, max_client_requests, proxies_3):
    with pytest.raises(ValueError):
        ClientManager(proxies_3, min_client_requests, max_client_requests)


@pytest.mark.parametrize("value", [2, 3])
def test_valid_min_client_requests_setter(value, client_manager_2_3):
    client_manager_2_3.min_client_requests = value
    assert client_manager_2_3.min_client_requests == value


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_invalid_min_client_requests_setter(value, client_manager_2_3):
    with pytest.raises(ValueError):
        client_manager_2_3.min_client_requests = value


@pytest.mark.parametrize("value", [2, 3, 4])
def test_valid_max_client_requests_setter(value, client_manager_2_3):
    client_manager_2_3.max_client_requests = value
    assert client_manager_2_3.max_client_requests == value


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_invalid_max_client_requests_setter(value, client_manager_2_3):
    with pytest.raises(ValueError):
        client_manager_2_3.max_client_requests = value


@respx.mock
@pytest.mark.trio
async def test_creates_new_clients_when_on_timeout(proxies_3, url):
    respx.get().respond(200)
    client_manager = ClientManager(proxies_3, 10, 10)
    async with trio.open_nursery() as nursery:
        for _ in range(3):
            nursery.start_soon(client_manager.request, url, {})
    assert len(client_manager._clients) == 3


@respx.mock
@pytest.mark.trio
async def test_reuses_clients_if_not_on_timeout(proxies_3, url):
    respx.get().respond(200)
    client_manager = ClientManager(proxies_3, 10, 10)
    await client_manager.request(url, {})
    await trio.sleep(ClientManager._calc_wait_time(next(iter(client_manager._clients))) + 0.1)
    await client_manager.request(url, {})
    assert len(client_manager._clients) == 1


@respx.mock
@pytest.mark.trio
async def test_creates_new_clients_if_different_http_version(proxies_3, url):
    respx.get().respond(200)
    client_manager = ClientManager(proxies_3, 10, 10)
    await client_manager.request(url, {})
    await trio.sleep(ClientManager._calc_wait_time(next(iter(client_manager._clients))) + 0.1)
    await client_manager.request(url, {}, http2=False)
    assert len(client_manager._clients) == 2


@pytest.mark.trio
@respx.mock
@pytest.mark.parametrize("event_hooks", [None, {"response": [raise_for_status_hook]}])
async def test_400x_500x_closes_client(proxies_1000, codes_400x_500x, url, event_hooks):
    codes_400x_500x.remove(429)
    respx.get().mock(side_effect=(httpx.Response(status_code) for status_code in codes_400x_500x))
    client_manager = ClientManager(proxies_1000, 2, 2)
    for _ in codes_400x_500x:
        try:
            await client_manager.request(url, {}, event_hooks=event_hooks)
        except HTTPStatusError:
            pass
        assert not client_manager._clients


@respx.mock
@pytest.mark.trio
@pytest.mark.parametrize("event_hooks", [None, {"response": [raise_for_status_hook]}])
async def test_429_reduces_max_client_requests_and_closes_clients(url, proxies_3, event_hooks):
    respx.get().respond(200)
    client_manager = ClientManager(proxies_3, 4, 4)

    # Create the first client
    try:
        await client_manager.request(url, {}, event_hooks=event_hooks)
    except HTTPStatusError:
        pass
    await trio.sleep(ClientManager._calc_wait_time(next(iter(client_manager._clients))) + 0.1)

    # Reuse the first client and create 2 more
    for _ in range(3):
        try:
            await client_manager.request(url, {}, event_hooks=event_hooks)
        except HTTPStatusError:
            pass
    assert len(client_manager._clients) == 3

    # Set the last in queue client's requests_allowed = 2
    last_in_queue = client_manager._clients.popitem()
    last_in_queue[1]["requests_allowed"] = 2
    client_manager._clients[last_in_queue[0]] = last_in_queue[1]

    # Set up the 429 response. need to reduce min_client_requests, so we don't get an AdjustmentError
    respx.get().respond(429)
    client_manager.min_client_requests = 2

    # Wait so me don't create a new client
    await trio.sleep(ClientManager._calc_wait_time(next(iter(client_manager._clients))) + 0.1)

    # The first client we created has made two clients, the next one will be unsuccessful, so max_client_requests,
    # should be reduced to 2 after the request has been made
    try:
        await client_manager.request(url, {}, event_hooks=event_hooks)
    except HTTPStatusError:
        pass

    # Only the last_in_queue client has a requests_allowed of 2 or less, so it should be the only one left
    assert len(client_manager._clients) == 1
    assert last_in_queue[0] in client_manager._clients
    assert client_manager.max_client_requests == 2


@respx.mock
@pytest.mark.trio
@pytest.mark.parametrize("event_hooks", [None, {"response": [raise_for_status_hook]}])
async def test_429_handling_raises_adjustment_error_if_max_client_requests_falls_below_min_client_requests(url, proxies_3, event_hooks):
    respx.get().respond(429)
    client_manager = ClientManager(proxies_3, 3, 3)
    with pytest.raises(AdjustmentError):
        try:
            await client_manager.request(url, {}, event_hooks=event_hooks)
        except HTTPStatusError:
            pass
