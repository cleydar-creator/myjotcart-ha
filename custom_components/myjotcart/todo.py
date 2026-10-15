"""Each MyJotCart list is a Home Assistant to-do list (dashboard card, voice: «add milk to Mercadona»)."""

from __future__ import annotations

import re

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyJotCartConfigEntry
from .coordinator import MyJotCartCoordinator
from .entity import MyJotCartEntity

# «2 leche», «3x eggs» → quantity + name. The quantity is shown in the description as «×2».
QTY_RE = re.compile(r"^\s*(\d{1,2})\s*[x×]?\s+(.+)$", re.I)
DESC_QTY_RE = re.compile(r"^\s*[x×](\d{1,2})\s*(?:·\s*)?(.*)$", re.S)


async def async_setup_entry(hass: HomeAssistant, entry: MyJotCartConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: dict[str, MyJotCartTodo] = {}

    @callback
    def sync() -> None:
        ids = {l["id"] for l in coordinator.lists()}
        new = [MyJotCartTodo(coordinator, lid) for lid in ids if lid not in known]
        for ent in new:
            known[ent.list_id] = ent
        if new:
            async_add_entities(new)
        # Lists deleted in the app disappear from Home Assistant too.
        reg = er.async_get(hass)
        for lid in [x for x in known if x not in ids]:
            ent = known.pop(lid)
            if ent.entity_id and reg.async_get(ent.entity_id):
                reg.async_remove(ent.entity_id)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))


class MyJotCartTodo(MyJotCartEntity, TodoListEntity):
    """A shopping list. Ticking an item = it is in the cart; «Clear completed» = finish the shopping."""

    _attr_has_entity_name = False  # entity name = list name, so voice works with just «Mercadona»
    _attr_icon = "mdi:cart-outline"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: MyJotCartCoordinator, list_id: str) -> None:
        super().__init__(coordinator)
        self.list_id = list_id
        self._attr_unique_id = f"{coordinator.entry.unique_id or coordinator.entry.entry_id}_list_{list_id}"

    @property
    def _list(self) -> dict | None:
        return next((l for l in self.coordinator.lists() if l["id"] == self.list_id), None)

    @property
    def available(self) -> bool:
        return super().available and self._list is not None

    @property
    def name(self) -> str | None:
        l = self._list
        return l["name"] if l else None

    @property
    def todo_items(self) -> list[TodoItem] | None:
        data = self.coordinator.data or {}
        order = {c["id"]: n for n, c in enumerate(data.get("cats", []))}
        prods = {p["id"]: p for p in data.get("products", [])}

        def aisle(i: dict) -> int:
            p = prods.get(i.get("productId") or "")
            return order.get((p or i).get("category") or "otros", 999)

        items = sorted(self.coordinator.items(self.list_id), key=lambda i: (bool(i.get("done")), aisle(i), i.get("name", "").lower()))
        out = []
        for i in items:
            qty, note = i.get("qty") or 1, i.get("note") or ""
            desc = " · ".join(x for x in (f"×{qty}" if qty > 1 else "", note) if x) or None
            out.append(TodoItem(
                uid=i["id"], summary=i["name"], description=desc,
                status=TodoItemStatus.COMPLETED if i.get("done") else TodoItemStatus.NEEDS_ACTION,
            ))
        return out

    async def async_create_todo_item(self, item: TodoItem) -> None:
        name, qty = (item.summary or "").strip(), 1
        if m := QTY_RE.match(name):
            qty, name = int(m.group(1)), m.group(2).strip()
        qty, note = _split_desc(item.description, qty)
        created = await self.coordinator.api.add_item(self.list_id, name, qty, note)
        if item.status == TodoItemStatus.COMPLETED:
            await self.coordinator.api.update_item(created["id"], done=True)
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        # HA always sends the whole item (summary, status and description), so qty/note come from the description.
        qty, note = _split_desc(item.description, 1)
        fields: dict = {"done": item.status == TodoItemStatus.COMPLETED, "qty": qty, "note": note}
        if item.summary:
            fields["name"] = item.summary
        await self.coordinator.api.update_item(item.uid, **fields)
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        done = {i["id"] for i in self.coordinator.items(self.list_id) if i.get("done")}
        if done and set(uids) == done:
            # «Clear completed items»: same as «Finish shopping» in the app — what was bought goes into the home stock.
            await self.coordinator.api.finish(self.list_id)
        else:
            for uid in uids:
                await self.coordinator.api.delete_item(uid)
        await self.coordinator.async_refresh()


def _split_desc(desc: str | None, qty: int) -> tuple[int, str]:
    """«×2 · without lactose» → (2, "without lactose")."""
    desc = (desc or "").strip()
    if m := DESC_QTY_RE.match(desc):
        return int(m.group(1)), m.group(2).strip()
    return qty, desc
