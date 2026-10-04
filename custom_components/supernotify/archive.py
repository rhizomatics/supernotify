from __future__ import annotations

import datetime as dt
import json
import logging
import math
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

import aiofiles.os
import anyio
import homeassistant.util.dt as dt_util
from anyio import Path
from homeassistant.const import (
    CONF_DEBUG,
    CONF_ENABLED,
)

from .const import (
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_DIAGNOSTICS,
    CONF_ARCHIVE_EVENT_NAME,
    CONF_ARCHIVE_EVENT_SELECTION,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_ARCHIVE_PURGE_INTERVAL,
)
from .schema import DeliveryOutcome, OutcomeSelection

if TYPE_CHECKING:
    from homeassistant.core import Context as HAContext
    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.hass_api import HomeAssistantAPI

    from .engine import SupernotifyEngine
    from .people import Recipient

_LOGGER = logging.getLogger(__name__)

ARCHIVE_PURGE_MIN_INTERVAL = 3 * 60
ARCHIVE_DEFAULT_DAYS = 1
WRITE_TEST = ".startup"


def _filename_period(filename: str) -> tuple[float, float] | None:
    """The span of time an archive file could have been created in, going by the local time
    to the minute at the start of its name, or ``None`` if it isn't named that way.

    Both sides of a daylight saving change are allowed for, since the name has no UTC offset.
    """
    try:
        named: dt.datetime = dt.datetime.strptime(filename[:16], "%Y-%m-%dT%H-%M")
    except ValueError:
        return None
    time_zone = dt_util.get_default_time_zone()
    stamps: list[float] = [named.replace(tzinfo=time_zone, fold=fold).timestamp() for fold in (0, 1)]
    return min(stamps), max(stamps) + 60


class ArchivableObject:
    ha_context: HAContext | None = None

    @abstractmethod
    def base_filename(self) -> str:
        pass

    @abstractmethod
    def contents(self, diagnostics: bool = False, **_kwargs: Any) -> dict[str, Any]:
        pass

    def outcome(self) -> DeliveryOutcome:
        return DeliveryOutcome.NO_DELIVERY

    def diagnostics_selected(self, outcome_policy: OutcomeSelection) -> bool:
        """Whether the archived copy should carry the full diagnostic content"""
        return self.selected(outcome_policy)

    def selected(self, outcome_policy: OutcomeSelection) -> bool:
        if outcome_policy & OutcomeSelection.NONE:
            return False
        return bool(
            outcome_policy & OutcomeSelection.ALL
            or (outcome_policy & OutcomeSelection.SUCCESS and self.outcome() == DeliveryOutcome.SUCCESS)
            or (outcome_policy & OutcomeSelection.NO_DELIVERY and self.outcome() == DeliveryOutcome.NO_DELIVERY)
            or (outcome_policy & OutcomeSelection.PARTIAL_DELIVERY and self.outcome() == DeliveryOutcome.PARTIAL_DELIVERY)
            or (outcome_policy & OutcomeSelection.DUPE and self.outcome() == DeliveryOutcome.DUPE)
            or (outcome_policy & OutcomeSelection.FALLBACK_DELIVERY and self.outcome() == DeliveryOutcome.FALLBACK_DELIVERY)
            or (outcome_policy & OutcomeSelection.ERROR and self.outcome() == DeliveryOutcome.ERROR)
        )


class ArchiveDestination:
    @abstractmethod
    async def archive(self, archive_object: ArchivableObject) -> bool:
        pass


class EventArchiver(ArchiveDestination):
    def __init__(
        self, hass_api: HomeAssistantAPI, event_name: str, diagnostics: OutcomeSelection = OutcomeSelection.ERROR
    ) -> None:
        self.hass_api = hass_api
        self.event_name = event_name
        self.diagnostics = diagnostics
        if diagnostics & OutcomeSelection.NONE:
            pass
        elif diagnostics & OutcomeSelection.ALL:
            _LOGGER.info("SUPERNOTIFY Archiving all notifications as %s events", event_name)
        else:
            if diagnostics & OutcomeSelection.SUCCESS:
                _LOGGER.info("SUPERNOTIFY Archiving successful notifications as %s events", event_name)
            if diagnostics & OutcomeSelection.PARTIAL_DELIVERY:
                _LOGGER.info("SUPERNOTIFY Archiving partial delivery notifications as %s events", event_name)

            if diagnostics & OutcomeSelection.FALLBACK_DELIVERY:
                _LOGGER.info("SUPERNOTIFY Archiving fallback notifications as %s events", event_name)
            if diagnostics & OutcomeSelection.NO_DELIVERY:
                _LOGGER.info("SUPERNOTIFY Archiving no delivery notifications as %s events", event_name)

            if diagnostics & OutcomeSelection.ERROR:
                _LOGGER.info("SUPERNOTIFY Archiving error notifications as %s events", event_name)

            if diagnostics & OutcomeSelection.DUPE:
                _LOGGER.info("SUPERNOTIFY Archiving dupe notifications as %s events", event_name)

    async def archive(self, archive_object: ArchivableObject) -> bool:
        try:
            payload = archive_object.contents(diagnostics=archive_object.diagnostics_selected(self.diagnostics))
            self.hass_api.fire_event(self.event_name, payload, context=archive_object.ha_context)
            return True
        except Exception:
            _LOGGER.warning(f"SUPERNOTIFY Failed to archive to event {self.event_name}")
            return False


class ArchiveTopic(ArchiveDestination):
    def __init__(
        self,
        hass_api: HomeAssistantAPI,
        topic: str,
        qos: int = 0,
        retain: bool = True,
        diagnostics: OutcomeSelection = OutcomeSelection.ERROR,
    ) -> None:
        self.hass_api: HomeAssistantAPI = hass_api
        self.topic: str = topic
        self.qos: int = qos
        self.retain: bool = retain
        self.diagnostics: OutcomeSelection = diagnostics
        self.enabled: bool = False

    async def initialize(self) -> None:
        if self.topic:
            if await self.hass_api.mqtt_available(raise_on_error=False):
                _LOGGER.info(f"SUPERNOTIFY Archiving to MQTT topic {self.topic}, qos {self.qos}, retain {self.retain}")
                self.enabled = True
            else:
                _LOGGER.warning(
                    f"SUPERNOTIFY Archiving configured for topic {self.topic} but MQTT not available at startup, disabled"
                )

    async def archive(self, archive_object: ArchivableObject) -> bool:
        if not self.enabled:
            return False
        payload = archive_object.contents(diagnostics=archive_object.diagnostics_selected(self.diagnostics))
        topic = f"{self.topic}/{archive_object.base_filename()}"
        _LOGGER.debug(f"SUPERNOTIFY Publishing notification to {topic}")
        try:
            await self.hass_api.mqtt_publish(
                topic=topic,
                payload=payload,
                qos=self.qos,
                retain=self.retain,
            )
            return True
        except Exception:
            _LOGGER.warning(f"SUPERNOTIFY Failed to archive to topic {self.topic}")
            return False


class ArchiveDirectory(ArchiveDestination):
    def __init__(self, path: str, purge_minute_interval: int, diagnostics: OutcomeSelection = OutcomeSelection.ERROR) -> None:
        self.configured_path: str = path
        self.archive_path: anyio.Path | None = None
        self.enabled: bool = False
        self.diagnostics: OutcomeSelection = diagnostics
        self.last_purge: dt.datetime | None = None
        self.purge_minute_interval: int = purge_minute_interval

    async def initialize(self) -> None:
        verify_archive_path: Path = Path(self.configured_path)
        if verify_archive_path and not await verify_archive_path.exists():
            _LOGGER.info("SUPERNOTIFY Archive path not found at %s", verify_archive_path)
            try:
                await verify_archive_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Archive path %s cannot be created: %s", verify_archive_path, e)
        if verify_archive_path and await verify_archive_path.exists() and await verify_archive_path.is_dir():
            try:
                await verify_archive_path.joinpath(WRITE_TEST).touch(exist_ok=True)
                self.archive_path = verify_archive_path
                _LOGGER.info("SUPERNOTIFY Archiving notifications to file system at %s", verify_archive_path)
                self.enabled = True
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Archive path %s cannot be written: %s", verify_archive_path, e)
        else:
            _LOGGER.warning("SUPERNOTIFY Archive path %s is not a directory or does not exist", verify_archive_path)

    async def archive(self, archive_object: ArchivableObject) -> bool:
        archived: bool = False

        if self.enabled and self.archive_path:  # archive_path to assuage mypy
            archive_filepath: Path | None = None
            diagnostics: bool = archive_object.diagnostics_selected(self.diagnostics)
            try:
                filename = f"{archive_object.base_filename()}.json"
                archive_filepath = self.archive_path.joinpath(filename)
                serialized: str = json.dumps(archive_object.contents(diagnostics=diagnostics), indent=2)
                async with aiofiles.open(archive_filepath, mode="w") as file:
                    await file.write(serialized)
                _LOGGER.debug("SUPERNOTIFY Archived notification %s", await archive_filepath.absolute())
                archived = True
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to archive notification: %s", e)
                if diagnostics and archive_filepath:
                    try:
                        serialized = json.dumps(archive_object.contents(diagnostics=False), indent=2)
                        async with aiofiles.open(archive_filepath, mode="w") as file:
                            await file.write(serialized)
                        _LOGGER.warning("SUPERNOTIFY Archived minimal notification %s", await archive_filepath.absolute())
                        archived = True
                    except Exception:
                        _LOGGER.exception("SUPERNOTIFY Unable to archive minimal notification")
        return archived

    async def list_entries(
        self,
        limit: int = 20,
        after: dt.datetime | None = None,
        before: dt.datetime | None = None,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return up to *limit* archived notifications, newest first.

        Optional *after* and *before* filter by the ``created`` timestamp stored in
        each archive file. Optional *outcome* keeps only notifications whose top-level
        ``outcome`` field matches, ignoring case: the archive stores the ``DeliveryOutcome``
        value (``"success"``) and the action's selector offers ``"SUCCESS"``.

        Files are named for the minute they were created, so any that fall outside
        *after* and *before* are passed over without being opened.
        """
        if not self.archive_path or not await self.archive_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        try:
            raw_scan = await aiofiles.os.scandir(self.archive_path)
            files = [e for e in raw_scan if e.name.endswith(".json") and e.name != WRITE_TEST]
            files.sort(key=lambda e: e.stat().st_ctime, reverse=True)
            earliest: float = after.timestamp() if after else -math.inf
            latest: float = before.timestamp() if before else math.inf
            for entry in files:
                if len(entries) >= limit:
                    break
                if (after or before) and (named := _filename_period(entry.name)) and (named[1] < earliest or named[0] > latest):
                    continue
                try:
                    async with aiofiles.open(entry.path, mode="r") as fh:
                        data: dict[str, Any] = json.loads(await fh.read())
                except Exception as exc:
                    _LOGGER.debug("SUPERNOTIFY Skipping unreadable archive file %s: %s", entry.name, exc)
                    continue
                created: dt.datetime | None = dt_util.parse_datetime(data.get("created") or "")
                if after is not None and created is not None and created < after:
                    continue
                if before is not None and created is not None and created > before:
                    continue
                if outcome is not None and str(data.get("outcome", "")).lower() != outcome.lower():
                    continue
                entries.append(data)
        except Exception as exc:
            _LOGGER.warning("SUPERNOTIFY Unable to list archive entries: %s", exc)
        return entries

    async def read_entry(self, notification_id: str) -> dict[str, Any] | None:
        """Return the full JSON of one archived notification by its id, or ``None``."""
        if not self.archive_path or not await self.archive_path.exists():
            return None
        try:
            raw_scan = await aiofiles.os.scandir(self.archive_path)
            for entry in raw_scan:
                if entry.name.endswith(".json") and notification_id in entry.name:
                    async with aiofiles.open(entry.path, mode="r") as fh:
                        return json.loads(await fh.read())
        except Exception as exc:
            _LOGGER.warning("SUPERNOTIFY Unable to read archive entry %s: %s", notification_id, exc)
        return None

    async def size(self) -> int:
        path = self.archive_path
        if path and await path.exists():
            return sum(1 for p in await aiofiles.os.listdir(path) if p != WRITE_TEST)
        return 0

    async def recent(self, since: dt.datetime, limit: int) -> list[dict[str, Any]]:
        """Archived notifications written since a given time, newest first"""
        if not self.archive_path or not await self.archive_path.exists():
            return []
        cutoff: float = since.timestamp()
        candidates: list[tuple[float, str]] = []
        for entry in await aiofiles.os.scandir(self.archive_path):
            if entry.name.endswith(".json") and (modified := entry.stat().st_mtime) >= cutoff:
                candidates.append((modified, entry.path))
        results: list[dict[str, Any]] = []
        for _modified, path in sorted(candidates, reverse=True)[:limit]:
            try:
                async with aiofiles.open(path) as file:
                    results.append(json.loads(await file.read()))
            except (OSError, ValueError) as e:
                _LOGGER.warning("SUPERNOTIFY Unable to read archived notification %s: %s", path, e)
        return results

    async def cleanup(self, days: int, force: bool) -> int:
        if (
            not force
            and self.last_purge is not None
            and self.last_purge > dt.datetime.now(dt.UTC) - dt.timedelta(minutes=self.purge_minute_interval)
        ):
            return 0

        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
        cutoff = cutoff.astimezone(dt.UTC)
        purged = 0
        if self.archive_path and await self.archive_path.exists():
            try:
                archive = await aiofiles.os.scandir(self.archive_path)
                for entry in archive:
                    if entry.name == ".startup":
                        continue
                    # st_ctime is used deliberately here (not st_birthtime): archive files are
                    # written once and never modified afterwards, so ctime reflects creation time
                    # on the platforms this integration targets; st_birthtime is not guaranteed to
                    # be available on all Linux filesystems.
                    if dt_util.utc_from_timestamp(entry.stat().st_ctime) <= cutoff:  # ty: ignore[deprecated,unused-ignore-comment]
                        _LOGGER.debug("SUPERNOTIFY Purging %s", entry.path)
                        await aiofiles.os.unlink(entry.path)
                        purged += 1
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to clean up archive at %s: %s", self.archive_path, e, exc_info=True)
            _LOGGER.info("SUPERNOTIFY Purged %s archived notifications for cutoff %s", purged, cutoff)
            self.last_purge = dt.datetime.now(dt.UTC)
        else:
            _LOGGER.debug("SUPERNOTIFY Skipping archive purge for unknown path %s", self.archive_path)
        return purged


class NotificationArchive:
    def __init__(
        self,
        config: ConfigType,
        hass_api: HomeAssistantAPI,
    ) -> None:
        self.hass_api = hass_api
        self.enabled = bool(config.get(CONF_ENABLED, False))
        self.archive_directory: ArchiveDirectory | None = None
        self.archive_topic: ArchiveTopic | None = None
        self.event_archiver: EventArchiver | None = None
        self.event_selection: OutcomeSelection = config.get(CONF_ARCHIVE_EVENT_SELECTION, OutcomeSelection.NONE)
        self.diagnostics: OutcomeSelection = config.get(CONF_ARCHIVE_DIAGNOSTICS, OutcomeSelection.ERROR)
        self.archive_event_name: str = config.get(CONF_ARCHIVE_EVENT_NAME, "supernotification")
        self.configured_archive_path: str | None = config.get(CONF_ARCHIVE_PATH)
        self.archive_days = int(config.get(CONF_ARCHIVE_DAYS, ARCHIVE_DEFAULT_DAYS))
        self.mqtt_topic: str | None = config.get(CONF_ARCHIVE_MQTT_TOPIC)
        self.mqtt_qos: int = int(config.get(CONF_ARCHIVE_MQTT_QOS, 0))
        self.mqtt_retain: bool = bool(config.get(CONF_ARCHIVE_MQTT_RETAIN, True))
        self.debug: bool = bool(config.get(CONF_DEBUG, False))

        self.purge_minute_interval = int(config.get(CONF_ARCHIVE_PURGE_INTERVAL, ARCHIVE_PURGE_MIN_INTERVAL))

    async def initialize(self) -> None:
        if not self.enabled:
            _LOGGER.info("SUPERNOTIFY Archive disabled")
            return
        if not self.configured_archive_path:
            _LOGGER.warning("SUPERNOTIFY Archive path not configured")
        else:
            self.archive_directory = ArchiveDirectory(
                self.configured_archive_path, purge_minute_interval=self.purge_minute_interval, diagnostics=self.diagnostics
            )
            await self.archive_directory.initialize()

        if self.mqtt_topic:
            self.archive_topic = ArchiveTopic(self.hass_api, self.mqtt_topic, self.mqtt_qos, self.mqtt_retain, self.diagnostics)
            await self.archive_topic.initialize()

        self.event_archiver = EventArchiver(self.hass_api, self.archive_event_name, self.diagnostics)

    async def size(self) -> int:
        return await self.archive_directory.size() if self.archive_directory else 0

    async def recent(self, since: dt.datetime, limit: int) -> list[dict[str, Any]]:
        return await self.archive_directory.recent(since, limit) if self.archive_directory else []

    async def cleanup(self, days: int | None = None, force: bool = False) -> int:
        days = days or self.archive_days
        return await self.archive_directory.cleanup(days, force) if self.archive_directory else 0

    async def archive(self, archive_object: ArchivableObject) -> bool:
        archived: bool = False
        if self.archive_topic and await self.archive_topic.archive(archive_object):
            archived = True
        if self.archive_directory and await self.archive_directory.archive(archive_object):
            archived = True
        if self.event_archiver and archive_object.selected(self.event_selection):
            await self.event_archiver.archive(archive_object)

        return archived


def _names_for(engine: SupernotifyEngine, person_ids: list[str]) -> list[str]:
    def _display_name(recipient: Recipient) -> str:
        return recipient.alias or recipient.name

    people = engine.context.people_registry.people
    return sorted(_display_name(people[p]) if p in people else p for p in person_ids)


def _bump(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def summarize_by_day(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Count archived notifications per local day, oldest first: how many, by outcome, priority,
    local hour and applied scenario, and for each delivery in how many it sent or failed.

    Older archive files keep `enabled_scenarios` as a mapping by name rather than a list - either
    is counted by name. A notification without a readable `created` is left out."""
    days: dict[str, dict[str, Any]] = {}
    for contents in entries:
        created: dt.datetime | None = dt_util.parse_datetime(str(contents.get("created") or ""))
        if created is None:
            continue
        local: dt.datetime = dt_util.as_local(created)
        key: str = local.date().isoformat()
        day: dict[str, Any] = days.setdefault(
            key, {"date": key, "count": 0, "outcome": {}, "priority": {}, "hour": [0] * 24, "deliveries": {}, "scenarios": {}}
        )
        day["count"] += 1
        day["hour"][local.hour] += 1
        _bump(day["outcome"], str(contents.get("outcome") or "unknown").lower())
        _bump(day["priority"], str(contents.get("priority") or "unknown").lower())
        for name, outcomes in (contents.get("deliveries") or {}).items():
            if not isinstance(outcomes, dict):
                continue
            sent, failed = bool(outcomes.get("success")), bool(outcomes.get("error"))
            if sent or failed:
                counts: dict[str, int] = day["deliveries"].setdefault(name, {"success": 0, "failed": 0})
                counts["success"] += sent
                counts["failed"] += failed
        scenarios: Any = contents.get("enabled_scenarios") or []
        for scenario in scenarios if isinstance(scenarios, list | tuple | dict) else [scenarios]:
            _bump(day["scenarios"], str(scenario))
    ordered: list[dict[str, Any]] = [days[key] for key in sorted(days)]
    return {"days": ordered, "count": sum(day["count"] for day in ordered)}


def summarize_notification(engine: SupernotifyEngine, contents: dict[str, Any]) -> dict[str, Any]:
    """Cut an archived or live notification down to what explains what happened to it"""
    deliveries: dict[str, dict[str, Any]] = {}
    for name, outcomes in (contents.get("deliveries") or {}).items():
        if skipped := outcomes.get("skipped"):
            deliveries[name] = {"skipped": skipped.get("suppression_reason")}
            continue
        summary: dict[str, Any] = {}
        recipients: set[str] = set()
        for outcome in ("success", "suppressed", "error"):
            envelopes: list[dict[str, Any]] = outcomes.get(outcome) or []
            if not envelopes:
                continue
            summary[outcome] = len(envelopes)
            for envelope in envelopes:
                recipients.update(((envelope.get("target") or {}).get("person_id")) or [])
                if outcome == "suppressed" and envelope.get("skip_reason"):
                    summary.setdefault("reasons", []).append(envelope["skip_reason"])
                if outcome == "error":
                    summary.setdefault("errors", []).extend(
                        call.get("exception") for call in envelope.get("failed_calls") or [] if call.get("exception")
                    )
        if recipients:
            summary["recipients"] = _names_for(engine, sorted(recipients))
        deliveries[name] = summary
    condition_variables: dict[str, Any] = contents.get("condition_variables") or {}
    result: dict[str, Any] = {
        "id": contents.get("id"),
        "created": contents.get("created"),
        "outcome": contents.get("outcome"),
        "message": contents.get("message"),
        "title": condition_variables.get("notification_title"),
        "priority": contents.get("priority"),
        "scenarios": contents.get("enabled_scenarios") or [],
        "occupancy": {
            state: _names_for(engine, [p.get("person") for p in people if p.get("person")])
            for state, people in (contents.get("occupancy") or {}).items()
        },
        "deliveries": deliveries,
        "delivery_provenance": contents.get("delivery_provenance") or {},
    }
    if contents.get("unknown_names"):
        result["unknown_names"] = contents["unknown_names"]
    if contents.get("_suppression_reason"):
        result["suppressed"] = contents["_suppression_reason"]
    if requester := (contents.get("original_context") or {}).get("user"):
        result["requested_by"] = requester
    return result
