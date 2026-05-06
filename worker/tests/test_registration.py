"""Worker registration flow tests using respx."""
import pytest
import respx
import httpx
from pathlib import Path


@pytest.mark.asyncio
async def test_register_saves_token(tmp_path, monkeypatch):
    token_path = tmp_path / ".lmpc" / "token"
    monkeypatch.setenv("LMPC_TOKEN_PATH", str(token_path))
    monkeypatch.setenv("LMPC_API_URL", "http://test-backend")
    monkeypatch.setenv("LMPC_WORKER_NAME", "test-worker")

    # Reload settings with patched env
    import importlib
    import lmpc_worker.config as cfg_mod
    importlib.reload(cfg_mod)
    import lmpc_worker.registration as reg_mod
    importlib.reload(reg_mod)

    with respx.mock:
        respx.post("http://test-backend/api/v1/workers/register").mock(
            return_value=httpx.Response(
                201,
                json={"worker_id": "abc-123", "api_token": "tok-xyz", "status": "pending"},
            )
        )
        with pytest.raises(SystemExit):
            await reg_mod.register_or_load()

    assert token_path.read_text().strip() == "tok-xyz"


@pytest.mark.asyncio
async def test_load_existing_token(tmp_path, monkeypatch):
    token_path = tmp_path / ".lmpc" / "token"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("existing-token")
    monkeypatch.setenv("LMPC_TOKEN_PATH", str(token_path))
    monkeypatch.setenv("LMPC_API_URL", "http://test-backend")

    import importlib
    import lmpc_worker.config as cfg_mod
    importlib.reload(cfg_mod)
    import lmpc_worker.registration as reg_mod
    importlib.reload(reg_mod)

    token = await reg_mod.register_or_load()
    assert token == "existing-token"
