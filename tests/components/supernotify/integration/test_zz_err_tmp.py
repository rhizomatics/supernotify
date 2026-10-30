from homeassistant.core import SupportsResponse
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.supernotify import DOMAIN

async def test_err(hass, tmp_path):
    MockConfigEntry(domain=DOMAIN, data={}, options={"archive": {"enabled": True, "file_path": str(tmp_path)}}).add_to_hass(hass)
    config = {"delivery": {"gone": {"transport": "generic", "action": "notify.gone", "inclusion": ["default"]}}}
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()
    await hass.services.async_call(DOMAIN, "notify", {"message": "x"}, blocking=True)
    await hass.async_block_till_done()
    print("FILES", sorted(p.name for p in tmp_path.iterdir()))
    r = await hass.services.async_call(DOMAIN, "enquire_archive", {}, blocking=True, return_response=SupportsResponse.ONLY)
    print("OUTCOME", r["notifications"][0]["outcome"], r["notifications"][0]["deliveries"])
