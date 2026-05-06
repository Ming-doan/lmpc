import pytest
from lmpc_worker.adapters.stub import StubAdapter


@pytest.mark.asyncio
async def test_stub_returns_valid_result():
    adapter = StubAdapter()
    result = await adapter.send_request(None, "", "Hello world", 100)
    assert result.success is True
    assert result.ttft_ms > 0
    assert result.e2e_ms >= result.ttft_ms
    assert result.output_tokens > 0


@pytest.mark.asyncio
async def test_stub_readiness():
    adapter = StubAdapter()
    info = await adapter.wait_until_ready("", 5)
    assert info.ready is True
    assert info.container_start_ms > 0
