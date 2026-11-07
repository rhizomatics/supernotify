"""Set up a freshly started preview Home Assistant as the preview house.

    uv run python preview/seed.py

compose.yaml's seed service runs this on every start, and it does nothing once seeded.

The preview house is `preview_house` in tests/components/supernotify/integration/houses.py,
which the integration tests use too, so what's seen in the preview is what's tested. Its
cameras, media players, notify entity, sirens and switches are the demo integration's. This
finishes onboarding with the house's first account as owner, then creates its floors, areas,
other users and people, and its PIRs as template helpers, and reloads Supernotify. Every account's
password is `preview`. A long-lived token for the owner is left in homeassistant/.preview_token,
for ha-repl.

Only a preview that hasn't been onboarded yet is seeded - `mise run clean` to start again.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import aiohttp

PREVIEW_DIR = Path(__file__).parent
CONFIG_DIR = PREVIEW_DIR / "homeassistant"
sys.path.insert(0, str(PREVIEW_DIR.parent / "tests" / "components" / "supernotify" / "integration"))
from houses import HOUSES  # type: ignore

HOUSE: dict[str, Any] = HOUSES["preview_house"]
PASSWORD = "preview"
TOKEN_FILE = CONFIG_DIR / ".preview_token"


class Preview:
    def __init__(self, session: aiohttp.ClientSession, url: str) -> None:
        self.session = session
        self.url = url.rstrip("/")
        self.client_id = f"{self.url}/"
        self.token = ""
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_id = 0

    async def wait_until_up(self) -> None:
        for _ in range(150):
            try:
                async with self.session.get(f"{self.url}/api/onboarding") as response:
                    if response.status == 200:
                        return
            except aiohttp.ClientError:
                pass
            await asyncio.sleep(2)
        raise SystemExit(f"Home Assistant not answering at {self.url}")

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:  # ruff: ignore[any-type]
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with self.session.post(f"{self.url}{path}", json=json or {}, headers=headers) as response:
            if response.status >= 400:
                raise SystemExit(f"POST {path} failed {response.status}: {await response.text()}")
            return await response.json() if response.content_type == "application/json" else None

    async def ws(self, message_type: str, **fields: Any) -> Any:  # ruff: ignore[any-type]
        if self._ws is None:
            self._ws = await self.session.ws_connect(f"{self.url}/api/websocket")
            await self._ws.receive_json()
            await self._ws.send_json({"type": "auth", "access_token": self.token})
            if (await self._ws.receive_json())["type"] != "auth_ok":
                raise SystemExit("websocket authentication failed")
        self._ws_id += 1
        await self._ws.send_json({"id": self._ws_id, "type": message_type, **fields})
        result = await self._ws.receive_json()
        if not result.get("success"):
            raise SystemExit(f"{message_type} failed: {result.get('error')}")
        return result.get("result")

    async def onboarded(self) -> bool:
        async with self.session.get(f"{self.url}/api/onboarding") as response:
            return any(step["done"] for step in await response.json())

    async def onboard(self, account: str, person: str) -> None:
        result = await self.post(
            "/api/onboarding/users",
            {"client_id": self.client_id, "name": person, "username": account, "password": PASSWORD, "language": "en"},
        )
        data = {"grant_type": "authorization_code", "code": result["auth_code"], "client_id": self.client_id}
        async with self.session.post(f"{self.url}/auth/token", data=data) as response:
            self.token = str((await response.json())["access_token"])
        await self.post("/api/onboarding/core_config")
        await self.post("/api/onboarding/analytics")
        await self.post("/api/onboarding/integration", {"client_id": self.client_id, "redirect_uri": self.client_id})
        await self.ws("config/core/update", location_name="Preview House", country="GB")
        TOKEN_FILE.write_text(await self.ws("auth/long_lived_access_token", client_name="ha-repl preview", lifespan=3650))

    async def flow(self, handler: str, *steps: dict[str, Any]) -> None:
        result = await self.post("/api/config/config_entries/flow", {"handler": handler})
        for step in steps:
            result = await self.post(f"/api/config/config_entries/flow/{result['flow_id']}", step)
        if result.get("type") != "create_entry":
            raise SystemExit(f"{handler} flow stopped at {result.get('step_id')}: {result.get('errors')}")


async def seed(url: str) -> None:
    async with aiohttp.ClientSession() as session:
        preview = Preview(session, url)
        await preview.wait_until_up()
        if await preview.onboarded():
            print(f"{url} is seeded already - `mise run clean` to start again")
            return
        # onboarding makes the owner's account and Person, so the first of the house's accounts is
        # the owner, rather than an extra account the house doesn't have
        users: dict[str, str] = dict(HOUSE["users"])
        owner, owner_person = next(iter(users.items()))
        await preview.onboard(owner, owner_person)

        floor_ids = {}
        for floor in HOUSE["floors"]:
            floor_ids[floor] = (await preview.ws("config/floor_registry/create", name=floor))["floor_id"]
        # the demo integration makes some areas of its own, like the kitchen, so those are reused
        existing_areas = {a["name"].lower(): a["area_id"] for a in await preview.ws("config/area_registry/list")}
        area_ids = {}
        for area, floor in HOUSE["areas"].items():
            fields = {"floor_id": floor_ids[floor]} if floor else {}
            if area in existing_areas:
                area_ids[area] = existing_areas[area]
                await preview.ws("config/area_registry/update", area_id=area_ids[area], **fields)
            else:
                area_ids[area] = (await preview.ws("config/area_registry/create", name=area, **fields))["area_id"]

        for account, person in list(users.items())[1:]:
            user = (await preview.ws("config/auth/create", name=account, group_ids=["system-users"]))["user"]
            await preview.ws(
                "config/auth_provider/homeassistant/create", user_id=user["id"], username=account, password=PASSWORD
            )
            await preview.ws("person/create", name=person, user_id=user["id"])

        for pir, area in HOUSE["pirs"].items():
            await preview.flow(
                "template", {"next_step_id": "binary_sensor"}, {"name": pir, "state": "{{ false }}", "device_class": "motion"}
            )
            if area:
                await preview.ws("config/entity_registry/update", entity_id=f"binary_sensor.{pir}", area_id=area_ids[area])

        # Supernotify set itself up when Home Assistant started, before any of the house existed
        await preview.post("/api/services/supernotify/reload")
        print(f"Seeded {url} - log in as {', '.join(users)}, with password {PASSWORD!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:9123")
    asyncio.run(seed(parser.parse_args().url))


if __name__ == "__main__":
    main()
