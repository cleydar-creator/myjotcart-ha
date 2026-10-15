"""End-to-end against a real MyJotCart server (MJC_URL, MJC_TOKEN = hat_…, MJC_COOKIE = cs=… of a user).

    MJC_URL=http://127.0.0.1:8299 MJC_TOKEN=hat_… MJC_COOKIE=cs=… pytest tests
"""

import asyncio
import os

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.myjotcart.const import DOMAIN

URL, TOKEN, COOKIE = os.environ.get("MJC_URL"), os.environ.get("MJC_TOKEN"), os.environ.get("MJC_COOKIE")
pytestmark = [pytest.mark.skipif(not URL, reason="needs a running MyJotCart (MJC_URL)")]

from homeassistant.helpers.service_info.hassio import HassioServiceInfo


async def phone(method, path, json=None):
    """What a family member does from the app (logged-in cookie)."""
    conn = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    async with aiohttp.ClientSession(connector=conn) as s, s.request(method, URL + path, json=json, headers={"Cookie": COOKIE}) as r:
        return await r.json()


async def wait_for(cond, secs=8):
    for _ in range(secs * 10):
        if cond():
            return True
        await asyncio.sleep(0.1)
    return False


async def setup(hass):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["type"] == FlowResultType.FORM
    bad = await hass.config_entries.flow.async_configure(r["flow_id"], {"url": URL, "token": "hat_nope"})
    assert bad["errors"] == {"base": "invalid_auth"}
    off = await hass.config_entries.flow.async_configure(r["flow_id"], {"url": "http://127.0.0.1:1", "token": TOKEN})
    assert off["errors"] == {"base": "cannot_connect"}
    ok = await hass.config_entries.flow.async_configure(r["flow_id"], {"url": URL, "token": TOKEN})
    assert ok["type"] == FlowResultType.CREATE_ENTRY, ok
    await hass.async_block_till_done()
    return ok["result"]


async def test_everything(hass: HomeAssistant):
    entry = await setup(hass)
    state = await phone("GET", "/api/state")
    lists = {l["name"]: l["id"] for l in state["lists"]}

    # 1 · Lists appear as to-do entities named like the list
    reg = er.async_get(hass)
    ents = {e.original_name: e.entity_id for e in reg.entities.values() if e.domain == "todo" and e.platform == DOMAIN}
    print("todo entities", ents)
    assert set(lists) <= set(ents)
    merc = ents["Mercadona"]
    assert hass.states.get(merc).state == "0"

    # 2 · Add from HA (what voice «add milk to Mercadona» ends up calling) — «2 leche» → qty 2
    await hass.services.async_call("todo", "add_item", {"item": "2 leche"}, target={"entity_id": merc}, blocking=True)
    await hass.services.async_call("todo", "add_item", {"item": "Pan"}, target={"entity_id": merc}, blocking=True)
    st = await phone("GET", "/api/state")
    leche = next(i for i in st["items"] if i["name"] == "leche")
    assert leche["qty"] == 2 and leche["by"] == "ha" and leche["listId"] == lists["Mercadona"]
    assert hass.states.get(merc).state == "2"
    res = await hass.services.async_call("todo", "get_items", {}, target={"entity_id": merc}, blocking=True, return_response=True)
    print("items", res)
    it = {x["summary"]: x for x in res[merc]["items"]}
    assert it["leche"]["description"] == "×2"

    # 3 · Added from a phone → shows up in HA by itself (live stream, no polling)
    await phone("POST", "/api/items", {"listId": lists["Mercadona"], "name": "Huevos"})
    assert await wait_for(lambda: hass.states.get(merc).state == "3"), "live update did not arrive"

    # 4 · Sensors
    pend = next(e.entity_id for e in reg.entities.values() if e.platform == DOMAIN and e.unique_id.endswith("_pending"))
    assert await wait_for(lambda: hass.states.get(pend).state == "3")
    print("pending attrs", hass.states.get(pend).attributes)

    # 5 · Tick in HA → in the cart in the app; edit description → qty/note
    await hass.services.async_call("todo", "update_item", {"item": "leche", "status": "completed"}, target={"entity_id": merc}, blocking=True)
    await hass.services.async_call("todo", "update_item", {"item": "Pan", "description": "×3 · integral"}, target={"entity_id": merc}, blocking=True)
    st = await phone("GET", "/api/state")
    by = {i["name"]: i for i in st["items"]}
    assert by["leche"]["done"] and by["leche"]["qty"] == 2, by["leche"]
    assert by["Pan"]["qty"] == 3 and by["Pan"]["note"] == "integral" and not by["Pan"]["done"]
    assert hass.states.get(merc).state == "2"

    # 6 · «Clear completed» = finish the shopping → leche leaves the list and goes to the home stock
    await hass.services.async_call("todo", "remove_completed_items", {}, target={"entity_id": merc}, blocking=True)
    st = await phone("GET", "/api/state")
    assert not any(i["name"] == "leche" for i in st["items"])
    p = next(p for p in st["products"] if p["name"] == "leche")
    assert p["stock"] == 2

    # 7 · Remove one pending item = delete it
    await hass.services.async_call("todo", "remove_item", {"item": "Huevos"}, target={"entity_id": merc}, blocking=True)
    st = await phone("GET", "/api/state")
    assert not any(i["name"] == "Huevos" for i in st["items"])

    # 8 · Running-out sensor: product with min 3 and stock 2
    await phone("PATCH", f"/api/products/{p['id']}", {"min": 3})
    low = next(e.entity_id for e in reg.entities.values() if e.platform == DOMAIN and e.unique_id.endswith("_running_out"))
    assert await wait_for(lambda: hass.states.get(low).state == "1")
    assert hass.states.get(low).attributes["products"] == ["leche"]

    # 9 · New list in the app → new entity; deleted → gone
    nl = await phone("POST", "/api/lists", {"name": "Lidl", "store": "lidl"})
    assert await wait_for(lambda: any(e.original_name == "Lidl" for e in reg.entities.values() if e.platform == DOMAIN))
    await phone("DELETE", f"/api/lists/{nl['id']}")
    assert await wait_for(lambda: not any(e.original_name == "Lidl" for e in reg.entities.values() if e.platform == DOMAIN))

    # 10 · Same household found again by the add-on discovery → no duplicate, data updated
    r = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(config={"host": "127.0.0.1", "port": int(URL.rsplit(":", 1)[1]), "token": TOKEN}, name="MyJotCart", slug="x_myjotcart", uuid="1"),
    )
    assert r["type"] == FlowResultType.ABORT and r["reason"] == "already_configured", r

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_discovery_new(hass: HomeAssistant):
    r = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(config={"host": "127.0.0.1", "port": int(URL.rsplit(":", 1)[1]), "token": TOKEN}, name="MyJotCart", slug="x_myjotcart", uuid="1"),
    )
    assert r["type"] == FlowResultType.FORM and r["step_id"] == "hassio_confirm", r
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(r["result"].entry_id)
