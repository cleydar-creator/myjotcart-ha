# MyJotCart for Home Assistant

Your [MyJotCart](https://github.com/cleydar-creator/myjotcart-addon) shopping lists inside Home Assistant.

<img src="https://raw.githubusercontent.com/cleydar-creator/myjotcart-addon/main/images/home-pantry.png" width="240" alt="MyJotCart home pantry"> <img src="https://raw.githubusercontent.com/cleydar-creator/myjotcart-addon/main/images/shopping-list.png" width="240" alt="MyJotCart shopping list">

> **Add-on or integration?** The [MyJotCart add-on](https://github.com/cleydar-creator/myjotcart-addon) is the app itself — it is the **MyJotCart** entry in the sidebar and keeps your data. This integration is optional: it connects the app to Home Assistant (to-do lists, voice, sensors, dashboard card) and does not add anything to the sidebar.

- **Every list is a to-do list**: use the standard *To-do list* card on any dashboard, tick items in the shop, add things from the sidebar.
- **Voice** with Assist: *"Add milk to my Mercadona list"* · *"Añade leche a la lista Mercadona"*.
- **Live**: what anyone adds from their phone shows up in Home Assistant within a second (and the other way round).
- **The whole app in a dashboard** with the *MyJotCart* card — at home and from outside (it goes through Home Assistant, like the sidebar panel).
- **Sensors** for automations: *Pending to buy* (per list in the attributes) and *Running out at home*.

| In Home Assistant | In MyJotCart |
|---|---|
| Add `2 milk` | 2 × milk on that list |
| Tick an item | It's in the cart |
| Item description `×3 · whole grain` | quantity 3, note "whole grain" |
| **Remove completed items** | **Finish shopping**: ticked items leave the list and go into the home pantry |
| Delete a pending item | Deleted |

## Install

1. Install the **MyJotCart add-on** first (Settings → Add-ons → Add-on store → ⋮ → Repositories → `https://github.com/cleydar-creator/myjotcart-addon`).
2. HACS → ⋮ → **Custom repositories** → `https://github.com/cleydar-creator/myjotcart-ha`, type **Integration** → install **MyJotCart** → restart Home Assistant.
3. Settings → Devices & services: **MyJotCart** appears under *Discovered* → **Add**. That's it.

Running MyJotCart outside Home Assistant (Docker, another machine)? Settings → Devices & services → Add integration → MyJotCart, and enter its address (e.g. `http://192.168.1.10:8210`) and a token from MyJotCart → Settings → Home Assistant → *Create a token manually*.

## Dashboard examples

The whole app (lists, home pantry, scanner) — pick **MyJotCart** in *Add card*, or:

```yaml
type: custom:myjotcart-card
height: 80vh        # optional; in a "Panel" view it fills the screen
```

Just one list, with the standard card:

```yaml
type: todo-list
entity: todo.mercadona
```

## Automation example: remind me when I'm near the shop

```yaml
triggers:
  - trigger: zone
    entity_id: person.me
    zone: zone.mercadona
    event: enter
conditions:
  - condition: numeric_state
    entity_id: todo.mercadona
    above: 0
actions:
  - action: notify.mobile_app_my_phone
    data:
      message: "{{ states('todo.mercadona') }} things to buy at Mercadona"
```

Languages: English, Español, Deutsch, Français, Português.

This integration (the Home Assistant connector) is MIT licensed. MyJotCart itself is a separate product.
