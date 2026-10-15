from unittest.mock import patch

from aiohttp.resolver import ThreadedResolver
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations, socket_enabled):
    """Load custom_components/ and allow talking to the real MyJotCart server.

    The plain resolver avoids aiodns' shutdown thread, which the HA test harness reports as lingering.
    """
    with patch("homeassistant.helpers.aiohttp_client.AsyncResolver", ThreadedResolver), \
         patch("aiohttp.connector.DefaultResolver", ThreadedResolver):
        yield
