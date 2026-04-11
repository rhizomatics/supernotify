"""Test suite per il transport Gotify di SuperNotify.

Copertura:
- _build_extras(): funzione pura - tutte le combinazioni di parametri
- validate_action(): solo notify.* services sono validi
- deliver(): happy path, title, priority
- Mapping priorita SuperNotify -> intero Gotify (tutti e 5 i livelli, critical->10)
- gotify_priority: string "7" -> int 7, out-of-range -> clamp, invalid -> fallback auto
- gotify_attach_image: boolify corretto ("false" stringa e falsy - no bug come ntfy)
- gotify_image_url: precedenza su gotify_attach_image
- gotify_* keys NON presenti nel payload inviato al servizio
- raw_data residuo NON passato a call_action (schema HACS fisso)
- Snapshot camera: camera_entity_id, snapshot_url fallback, failure graceful
- Eccezione service call -> return False + error_count incrementato
- supported_features include IMAGES, esclude ACTIONS e SPOKEN

Note implementative:
- Mock su hass_api (non su hass) come da Lezione #7 CLAUDE.md
- envelope.calls usato per verificare il payload - evita asserzioni fragili sul mock
- TRANSPORT_GOTIFY richiede modifica a const.py (vedere code/const_additions_gotify.py)

Percorso nel repo upstream: tests/components/supernotify/test_transport_gotify.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.notify.const import ATTR_DATA
from homeassistant.const import CONF_ACTION

from custom_components.supernotify.const import (
    ATTR_PRIORITY,
    CONF_TRANSPORT,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_MINIMUM,
    TRANSPORT_GOTIFY,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.gotify import GotifyTransport, _build_extras

from tests.components.supernotify.hass_setup_lib import TestingContext


# ---------------------------------------------------------------------------
# _build_extras() - test di unita puri (nessuna dipendenza HA)
# ---------------------------------------------------------------------------


def test_build_extras_all_none_returns_none() -> None:
    """Tutti i parametri None/False -> None (nessun extras da aggiungere)."""
    assert _build_extras(None, None, False, None) is None


def test_build_extras_click_url() -> None:
    """click_url -> extras["client::notification"]["click"]["url"]."""
    extras = _build_extras("https://ha.local", None, False, None)
    assert extras is not None
    assert extras["client::notification"]["click"]["url"] == "https://ha.local"
    assert "bigImageUrl" not in extras["client::notification"]


def test_build_extras_image_url() -> None:
    """image_url -> extras["client::notification"]["bigImageUrl"]."""
    extras = _build_extras(None, "https://ha.local/snap.jpg", False, None)
    assert extras is not None
    assert extras["client::notification"]["bigImageUrl"] == "https://ha.local/snap.jpg"
    assert "click" not in extras["client::notification"]


def test_build_extras_click_and_image_url_together() -> None:
    """click + image_url -> entrambi sotto client::notification."""
    extras = _build_extras("https://ha.local", "https://ha.local/img.jpg", False, None)
    assert extras is not None
    cn = extras["client::notification"]
    assert cn["click"]["url"] == "https://ha.local"
    assert cn["bigImageUrl"] == "https://ha.local/img.jpg"


def test_build_extras_markdown() -> None:
    """markdown=True -> extras["client::display"]["contentType"] = "text/markdown"."""
    extras = _build_extras(None, None, True, None)
    assert extras is not None
    assert extras["client::display"]["contentType"] == "text/markdown"
    assert "client::notification" not in extras


def test_build_extras_intent_url() -> None:
    """intent_url -> extras["android::action"]["onReceive"]["intentUrl"]."""
    extras = _build_extras(None, None, False, "intent://example.com")
    assert extras is not None
    assert extras["android::action"]["onReceive"]["intentUrl"] == "intent://example.com"


def test_build_extras_all_fields() -> None:
    """Tutti i campi: struttura completa con tutte e 3 le chiavi extras."""    extras = _build_extras(
        "https://ha.local",
        "https://ha.local/snap.jpg",
        True,
        "intent://example.com",
    )
    assert extras is not None
    assert "client::notification" in extras
    assert "client::display" in extras
    assert "android::action" in extras
    assert extras["client::notification"]["click"]["url"] == "https://ha.local"
    assert extras["client::notification"]["bigImageUrl"] == "https://ha.local/snap.jpg"
    assert extras["client::display"]["contentType"] == "text/markdown"
    assert extras["android::action"]["onReceive"]["intentUrl"] == "intent://example.com"


def test_build_extras_markdown_false_no_display_key() -> None:
    """markdown=False -> chiave client::display assente (nessun extras inutili)."""
    extras = _build_extras("https://ha.local", None, False, None)
    assert extras is not None
    assert "client::display" not in extras


# ---------------------------------------------------------------------------
# validate_action()
# ---------------------------------------------------------------------------


def test_validate_action_notify_service_is_valid() -> None:
    """notify.gotify e un'azione valida."""
    ctx = _ctx()
    uut = GotifyTransport(ctx)
    assert uut.validate_action("notify.gotify") is True


def test_validate_action_any_notify_service_is_valid() -> None:
    """Qualsiasi notify.* e accettato (nome configurabile dall'utente)."""
    ctx = _ctx()
    uut = GotifyTransport(ctx)
    assert uut.validate_action("notify.my_gotify_instance") is True


def test_validate_action_non_notify_service_is_invalid() -> None:
    """Un dominio diverso da notify.* viene rifiutato."""
    ctx = _ctx()
    uut = GotifyTransport(ctx)
    assert uut.validate_action("something.else") is False


def test_validate_action_none_is_invalid() -> None:
    """None viene rifiutato - action e obbligatoria per Gotify."""
    ctx = _ctx()
    uut = GotifyTransport(ctx)
    assert uut.validate_action(None) is False


# ---------------------------------------------------------------------------
# Helpers per i test di deliver()
# ---------------------------------------------------------------------------


def _ctx(delivery_data: dict | None = None, action: str = "notify.gotify") -> TestingContext:
    """Crea un TestingContext minimale con una delivery gotify_test."""
    delivery_cfg: dict = {
        "gotify_test": {
            CONF_TRANSPORT: TRANSPORT_GOTIFY,
            CONF_ACTION: action,
        }
    }
    if delivery_data:
        delivery_cfg["gotify_test"]["data"] = delivery_data
    return TestingContext(
        deliveries=delivery_cfg,
        transport_types=[GotifyTransport],
    )


def _mock_hass_api(abs_url_base: str = "https://my.home") -> MagicMock:
    """Crea un mock di hass_api con call_service e abs_url.

    Usare questo mock invece di ctx.hass.services.async_call (Lezione #7 CLAUDE.md).
    """
    mock = MagicMock()
    mock.call_service = AsyncMock(return_value={})
    mock.abs_url = MagicMock(side_effect=lambda p: f"{abs_url_base}{p}")
    return mock


def _envelope(
    ctx: TestingContext,
    message: str = "Test Gotify",
    title: str | None = None,
    data: dict | None = None,
    media: dict | None = None,
    priority: str | None = None,
) -> Envelope:
    """Costruisce un Envelope pronto per deliver()."""
    action_data: dict = {}
    if priority:
        action_data[ATTR_PRIORITY] = priority    if media:
        action_data["media"] = media

    uut = ctx.transport(TRANSPORT_GOTIFY)
    return Envelope(
        Delivery("gotify_test", ctx.delivery_config("gotify_test"), uut),
        Notification(ctx, message=message, title=title, action_data=action_data or None),
        data=data,
    )


# ---------------------------------------------------------------------------
# deliver() - happy path
# ---------------------------------------------------------------------------


async def test_deliver_happy_path() -> None:
    """Consegna base: messaggio -> True, priority=5 (MEDIUM) nel payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx)
    result = await uut.deliver(e)

    assert result is True
    assert len(e.calls) == 1
    assert e.calls[0].domain == "notify"
    assert e.calls[0].action == "gotify"
    assert e.calls[0].action_data["message"] == "Test Gotify"
    assert e.calls[0].action_data[ATTR_DATA]["priority"] == 5


async def test_deliver_with_title() -> None:
    """Il titolo viene incluso nel payload quando presente."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, message="Corpo", title="Titolo")
    result = await uut.deliver(e)

    assert result is True
    assert e.calls[0].action_data["message"] == "Corpo"
    assert e.calls[0].action_data["title"] == "Titolo"


async def test_deliver_no_extras_when_only_priority() -> None:
    """Senza campi extra, 'extras' non compare nel payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx)
    await uut.deliver(e)

    assert "extras" not in e.calls[0].action_data[ATTR_DATA]


# ---------------------------------------------------------------------------
# Mapping priorita - tutti e 5 i livelli
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sn_priority", "expected_gotify_priority"),
    [
        (PRIORITY_CRITICAL, 10),
        (PRIORITY_HIGH,     7),
        (PRIORITY_MEDIUM,   5),
        (PRIORITY_LOW,      2),
        (PRIORITY_MINIMUM,  0),
    ],
)
async def test_priority_mapping(sn_priority: str, expected_gotify_priority: int) -> None:
    """Ogni livello SuperNotify e mappato all'intero Gotify corretto."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, priority=sn_priority)
    await uut.deliver(e)

    assert e.calls[0].action_data[ATTR_DATA]["priority"] == expected_gotify_priority
    assert isinstance(e.calls[0].action_data[ATTR_DATA]["priority"], int), (
        "La priorita Gotify deve essere un int, non una stringa"
    )


async def test_gotify_priority_override_int() -> None:
    """gotify_priority=9 (int) sovrascrive il mapping automatico."""
    ctx = _ctx()    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_priority": 9}, priority=PRIORITY_MINIMUM)
    await uut.deliver(e)

    assert e.calls[0].action_data[ATTR_DATA]["priority"] == 9


async def test_gotify_priority_override_string() -> None:
    """gotify_priority='7' (stringa da YAML) viene castato a int 7 senza errori."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_priority": "7"})
    result = await uut.deliver(e)

    assert result is True
    assert e.calls[0].action_data[ATTR_DATA]["priority"] == 7
    assert isinstance(e.calls[0].action_data[ATTR_DATA]["priority"], int)


async def test_gotify_priority_string_float() -> None:
    """gotify_priority='7.0' (float come stringa) -> fallback mapping."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_priority": "7.0"})
    await uut.deliver(e)
    priority = e.calls[0].action_data[ATTR_DATA]["priority"]
    assert isinstance(priority, int)


async def test_gotify_priority_clamp_too_high() -> None:
    """gotify_priority=15 (fuori range 0-10) viene clampato a 10."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_priority": 15})
    await uut.deliver(e)

    assert e.calls[0].action_data[ATTR_DATA]["priority"] == 10


async def test_gotify_priority_clamp_too_low() -> None:
    """gotify_priority=-5 (fuori range 0-10) viene clampato a 0."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_priority": -5})
    await uut.deliver(e)

    assert e.calls[0].action_data[ATTR_DATA]["priority"] == 0


async def test_gotify_priority_invalid_string_falls_back_to_auto_mapping() -> None:
    """gotify_priority='alta' (non numerica) -> warning + fallback al mapping SN."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_priority": "alta"}, priority=PRIORITY_HIGH)
    await uut.deliver(e)

    assert e.calls[0].action_data[ATTR_DATA]["priority"] == 7


# ---------------------------------------------------------------------------
# Campi opzionali - extras
# ---------------------------------------------------------------------------


async def test_deliver_with_click_url() -> None:
    """gotify_click -> extras.client::notification.click.url."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_click": "https://ha.local:8123"})
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA]["extras"]
    assert extras["client::notification"]["click"]["url"] == "https://ha.local:8123"

async def test_deliver_with_image_url_direct() -> None:
    """gotify_image_url -> extras.client::notification.bigImageUrl."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_image_url": "https://example.com/foto.jpg"})
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA]["extras"]
    assert extras["client::notification"]["bigImageUrl"] == "https://example.com/foto.jpg"


async def test_deliver_with_markdown_true() -> None:
    """gotify_markdown=True -> extras.client::display.contentType = 'text/markdown'."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_markdown": True})
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA]["extras"]
    assert extras["client::display"]["contentType"] == "text/markdown"


async def test_deliver_with_markdown_false_no_extras() -> None:
    """gotify_markdown=False -> extras assente nel payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_markdown": False})
    await uut.deliver(e)

    assert "extras" not in e.calls[0].action_data[ATTR_DATA]


async def test_deliver_with_intent_url() -> None:
    """gotify_intent_url -> extras.android::action.onReceive.intentUrl."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_intent_url": "intent://scan/abc"})
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA]["extras"]
    assert extras["android::action"]["onReceive"]["intentUrl"] == "intent://scan/abc"


async def test_deliver_with_all_optional_extras() -> None:
    """Tutti i campi extras insieme -> struttura completa e corretta."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(
        ctx,
        data={
            "gotify_click": "https://ha.local",
            "gotify_image_url": "https://ha.local/img.jpg",
            "gotify_markdown": True,
            "gotify_intent_url": "intent://scan/123",
        },
    )
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA]["extras"]
    assert "client::notification" in extras
    assert "client::display" in extras
    assert "android::action" in extras


# ---------------------------------------------------------------------------
# boolify - comportamento CORRETTO (no bug come ntfy)
# ---------------------------------------------------------------------------


async def test_gotify_markdown_string_true_is_truthy() -> None:
    """gotify_markdown='true' (stringa YAML) -> boolify -> markdown attivato."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_markdown": "true"})
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA].get("extras", {})
    assert extras.get("client::display", {}).get("contentType") == "text/markdown"


async def test_gotify_markdown_string_false_is_falsy() -> None:
    """gotify_markdown='false' (stringa YAML) -> boolify -> markdown NON attivato."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_markdown": "false"})
    await uut.deliver(e)

    assert "extras" not in e.calls[0].action_data[ATTR_DATA], (
        "gotify_markdown='false' NON deve attivare markdown."
    )


async def test_gotify_attach_image_string_false_is_falsy() -> None:
    """gotify_attach_image='false' (stringa YAML) -> boolify -> nessun attach."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(
        ctx,
        data={"gotify_attach_image": "false"},
        media={"snapshot_url": "/api/camera_proxy/camera.test"},
    )
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA].get("extras", {})
    assert "bigImageUrl" not in extras.get("client::notification", {}), (
        "gotify_attach_image='false' NON deve attivare l'attach."
    )


async def test_gotify_attach_image_string_true_is_truthy() -> None:
    """gotify_attach_image='true' (stringa YAML) -> boolify -> attach attivato."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(
        ctx,
        data={"gotify_attach_image": "true"},
        media={"snapshot_url": "/api/camera_proxy/camera.test"},
    )
    await uut.deliver(e)

    extras = e.calls[0].action_data[ATTR_DATA].get("extras", {})
    assert "bigImageUrl" in extras.get("client::notification", {}), (
        "gotify_attach_image='true' DEVE attivare l'attach."
    )


# ---------------------------------------------------------------------------
# gotify_image_url vs gotify_attach_image - precedenza
# ---------------------------------------------------------------------------


async def test_image_url_takes_precedence_over_attach_image() -> None:
    """gotify_image_url esplicito ha precedenza su gotify_attach_image=True."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(
        ctx,
        data={
            "gotify_image_url": "https://direct-url.com/img.jpg",
            "gotify_attach_image": True,
        },
        media={"camera_entity_id": "camera.ingresso"},
    )
    await uut.deliver(e)

    all_call_args = [c.args for c in mock_api.call_service.call_args_list]
    snapshot_calls = [a for a in all_call_args if a[0] == "camera" and a[1] == "snapshot"]
    assert snapshot_calls == []

    extras = e.calls[0].action_data[ATTR_DATA]["extras"]    assert extras["client::notification"]["bigImageUrl"] == "https://direct-url.com/img.jpg"


# ---------------------------------------------------------------------------
# gotify_attach_image -- snapshot camera e snapshot_url fallback
# ---------------------------------------------------------------------------


async def test_attach_image_with_snapshot_url() -> None:
    """attach_image=True + snapshot_url -> abs_url chiamato, bigImageUrl nel payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    mock_api = _mock_hass_api("https://my.home")
    uut.hass_api = mock_api

    e = _envelope(
        ctx,
        data={"gotify_attach_image": True},
        media={"snapshot_url": "/api/camera_proxy/camera.ingresso"},
    )
    await uut.deliver(e)

    mock_api.abs_url.assert_called_with("/api/camera_proxy/camera.ingresso")
    extras = e.calls[0].action_data[ATTR_DATA]["extras"]
    assert extras["client::notification"]["bigImageUrl"] == "https://my.home/api/camera_proxy/camera.ingresso"


async def test_attach_image_with_camera_entity_calls_snapshot() -> None:
    """attach_image=True + camera_entity_id -> camera.snapshot chiamato prima di ntfy."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    mock_api = _mock_hass_api("https://my.home")
    uut.hass_api = mock_api

    e = _envelope(
        ctx,
        data={"gotify_attach_image": True},
        media={"camera_entity_id": "camera.ingresso"},
    )
    result = await uut.deliver(e)

    assert result is True
    # Verifica che camera.snapshot sia stato chiamato
    all_calls = mock_api.call_service.call_args_list
    snapshot_calls = [c for c in all_calls if c.args[0] == "camera" and c.args[1] == "snapshot"]
    assert len(snapshot_calls) == 1, "camera.snapshot deve essere chiamato esattamente una volta"
    assert snapshot_calls[0].kwargs["service_data"]["entity_id"] == "camera.ingresso"

    # Verifica bigImageUrl nel payload
    extras = e.calls[0].action_data[ATTR_DATA]["extras"]
    assert "bigImageUrl" in extras["client::notification"]

async def test_attach_image_false_no_snapshot_no_bigimage() -> None:
    """attach_image=False -> camera.snapshot non chiamato, bigImageUrl assente."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(
        ctx,
        data={"gotify_attach_image": False},
        media={"camera_entity_id": "camera.ingresso"},
    )
    await uut.deliver(e)

    # camera.snapshot non chiamato
    all_calls = mock_api.call_service.call_args_list
    snapshot_calls = [c for c in all_calls if c.args[0] == "camera"]
    assert snapshot_calls == []

    # bigImageUrl assente
    extras = e.calls[0].action_data[ATTR_DATA].get("extras", {})
    assert "bigImageUrl" not in extras.get("client::notification", {})


async def test_attach_image_true_without_media_no_bigimage() -> None:
    """attach_image=True ma nessuna media -> bigImageUrl assente, nessun crash."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(ctx, data={"gotify_attach_image": True})  # no media
    result = await uut.deliver(e)

    assert result is True
    extras = e.calls[0].action_data[ATTR_DATA].get("extras", {})
    assert "bigImageUrl" not in extras.get("client::notification", {})


async def test_attach_image_camera_snapshot_failure_delivery_continues() -> None:
    """Se camera.snapshot fallisce, la notifica viene inviata lo stesso senza bigImageUrl."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        if args[0] == "camera" and args[1] == "snapshot":
            raise RuntimeError("camera irraggiungibile")
        call_count += 1
        return {}

    mock_api = _mock_hass_api()
    mock_api.call_service.side_effect = _side_effect
    uut.hass_api = mock_api

    e = _envelope(
        ctx,
        data={"gotify_attach_image": True},
        media={"camera_entity_id": "camera.ingresso"},
    )
    result = await uut.deliver(e)

    # La notifica deve arrivare comunque
    assert result is True
    assert call_count == 1, "notify.gotify deve essere chiamato anche dopo errore snapshot"

    # bigImageUrl assente perche lo snapshot ha fallito
    extras = e.calls[0].action_data[ATTR_DATA].get("extras", {})
    assert "bigImageUrl" not in extras.get("client::notification", {})


# ---------------------------------------------------------------------------
# gotify_* keys non devono finire nel payload
# ---------------------------------------------------------------------------


async def test_gotify_keys_not_leaked_to_service_payload() -> None:
    """Nessuna chiave con prefisso gotify_* deve comparire nel payload al servizio."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(
        ctx,
        data={
            "gotify_priority": 5,
            "gotify_click": "https://ha.local",
            "gotify_image_url": "https://ha.local/img.jpg",
            "gotify_attach_image": True,
            "gotify_markdown": True,
            "gotify_intent_url": "intent://example.com",
        },
    )
    await uut.deliver(e)

    ad = e.calls[0].action_data
    leaked = [k for k in ad if k.startswith("gotify_")]
    assert leaked == [], f"Chiavi gotify_* trovate nel payload: {leaked}"

    # Verifica anche nel payload annidato ATTR_DATA
    payload_data = ad.get(ATTR_DATA, {})
    leaked_nested = [k for k in payload_data if k.startswith("gotify_")]
    assert leaked_nested == [], f"Chiavi gotify_* trovate in ATTR_DATA: {leaked_nested}"

async def test_raw_data_residuo_not_passed_to_notify_service() -> None:
    """Chiavi non-gotify_* in data non vengono passate al payload di notify.

    Gotify usa uno schema fisso (message, title, data.priority, data.extras).
    Chiavi extra causerebbero errori con il servizio HACS, quindi vengono scartate.
    """
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    uut.hass_api = _mock_hass_api()

    e = _envelope(
        ctx,
        data={
            "some_other_key": "valore_non_gotify",
            "another_key": 42,
        },
    )
    await uut.deliver(e)

    ad = e.calls[0].action_data
    assert "some_other_key" not in ad
    assert "another_key" not in ad
    assert "some_other_key" not in ad.get(ATTR_DATA, {})


# ---------------------------------------------------------------------------
# Gestione errori
# ---------------------------------------------------------------------------


async def test_deliver_service_exception_returns_false() -> None:
    """Eccezione da notify.gotify -> return False, error_count > 0."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)

    mock_api = _mock_hass_api()
    mock_api.call_service.side_effect = ConnectionError("Server Gotify irraggiungibile")
    uut.hass_api = mock_api

    e = _envelope(ctx)
    result = await uut.deliver(e)

    assert result is False
    assert e.error_count > 0

async def test_deliver_service_exception_no_calls_recorded() -> None:
    """Se notify.gotify lancia eccezione, envelope.calls rimane vuoto."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)

    mock_api = _mock_hass_api()
    mock_api.call_service.side_effect = RuntimeError("Connessione rifiutata")
    uut.hass_api = mock_api

    e = _envelope(ctx)
    await uut.deliver(e)

    assert len(e.calls) == 0, "Nessuna chiamata completata deve essere registrata"
    assert len(e.failed_calls) == 1, "La chiamata fallita deve essere in failed_calls"


# ---------------------------------------------------------------------------
# supported_features
# ---------------------------------------------------------------------------


def test_supported_features_include_message_title_images() -> None:
    """supported_features deve includere MESSAGE, TITLE e IMAGES."""
    from custom_components.supernotify.model import TransportFeature

    ctx = _ctx()
    uut = GotifyTransport(ctx)
    features = uut.supported_features

    assert features & TransportFeature.MESSAGE, "MESSAGE deve essere dichiarato"
    assert features & TransportFeature.TITLE, "TITLE deve essere dichiarato"
    assert features & TransportFeature.IMAGES, "IMAGES deve essere dichiarato (allegati bigImageUrl)"


def test_supported_features_exclude_actions_and_spoken() -> None:
    """supported_features NON deve includere ACTIONS o SPOKEN."""
    from custom_components.supernotify.model import TransportFeature

    ctx = _ctx()
    uut = GotifyTransport(ctx)
    features = uut.supported_features

    assert not (features & TransportFeature.ACTIONS), "ACTIONS non supportato da Gotify"
    assert not (features & TransportFeature.SPOKEN), "SPOKEN non supportato da Gotify"


# ---------------------------------------------------------------------------
# default_config
# ---------------------------------------------------------------------------


def test_default_config_no_default_action() -> None:
    """Gotify non ha un'azione di default -- l'utente DEVE specificarla in delivery.yaml."""
    ctx = _ctx()
    uut = GotifyTransport(ctx)
    assert uut.default_config.delivery_defaults.action is None, (
        "Gotify non ha default action -- richiede action: notify.<nome> in delivery.yaml"
    )


def test_default_config_target_required_never() -> None:
    """target_required deve essere NEVER -- Gotify non usa il sistema target HA."""
    from custom_components.supernotify.model import TargetRequired

    ctx = _ctx()
    uut = GotifyTransport(ctx)
    assert uut.default_config.delivery_defaults.target_required == TargetRequired.NEVER
