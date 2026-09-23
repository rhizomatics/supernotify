from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import voluptuous as vol
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
)
from homeassistant.core import valid_entity_id
from homeassistant.helpers.redact import partial_redact

from .common import ensure_list
from .const import (
    ATTR_EMAIL,
    ATTR_MOBILE_APP_ID,
    ATTR_PERSON_ID,
    ATTR_PHONE,
    RE_DEVICE_ID,
    TARGET_CATEGORY_VALUES,
)
from .schema import phone

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from .hass_api import HomeAssistantAPI
    from .model import SelectionRule


_LOGGER = logging.getLogger(__name__)

# Avoid importing this from HA component to dodge heavy imports until lazyimport available
MOBILE_APP_DOMAIN = "mobile_app"


@dataclass(frozen=True)
class TargetEntityCategory:
    """Declares which entities a transport accepts for the `entity_id` target category.

    Used in a `Transport.target_categories` list in place of a plain category name, since
    "any entity_id" is too broad - most entity-based transports only want entities of a
    particular domain (or domains), or ones registered by a particular platform/integration
    (or both). `domain`/`platform` may each be a single value or a list; `None` means
    "don't filter on this".
    """

    domain: str | list[str] | None = None
    platform: str | list[str] | None = None

    def matches(self, entity_id: str, hass_api: HomeAssistantAPI) -> bool:
        if self.domain is not None:
            domains = [self.domain] if isinstance(self.domain, str) else self.domain
            if entity_id.split(".", 1)[0] not in domains:
                return False
        # only look the platform up, in the entity registry, when there's a platform to check against
        if self.platform is not None:
            platforms = [self.platform] if isinstance(self.platform, str) else self.platform
            if hass_api.platform_for_entity(entity_id) not in platforms:
                return False
        return True


class Target:
    # actual targets, that can positively identified with a validator
    DIRECT_CATEGORIES: ClassVar[list[str]] = [ATTR_ENTITY_ID, ATTR_DEVICE_ID, ATTR_EMAIL, ATTR_PHONE, ATTR_MOBILE_APP_ID]
    # references that lead to targets, that can positively identified with a validator
    AUTO_INDIRECT_CATEGORIES: ClassVar[list[str]] = [ATTR_PERSON_ID]
    # references that lead to targets, that can't be positively identified with a validator
    EXPLICIT_INDIRECT_CATEGORIES: ClassVar[list[str]] = [ATTR_AREA_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID]
    INDIRECT_CATEGORIES = EXPLICIT_INDIRECT_CATEGORIES + AUTO_INDIRECT_CATEGORIES
    AUTO_CATEGORIES = DIRECT_CATEGORIES + AUTO_INDIRECT_CATEGORIES

    CATEGORIES = DIRECT_CATEGORIES + INDIRECT_CATEGORIES

    UNKNOWN_CUSTOM_CATEGORY = "_UNKNOWN_"

    def __init__(
        self,
        target: str
        | list[str]
        | dict[str, str]
        | dict[str, Sequence[str]]
        | dict[str, list[str]]
        | dict[str, str | list[str]]
        | None = None,
        target_data: dict[str, Any] | None = None,
        target_specific_data: bool = False,
    ) -> None:
        self.target_data: dict[str, Any] | None = None
        self.target_specific_data: dict[tuple[str, str], dict[str, Any]] | None = None
        self.targets: dict[str, list[str]] = {}

        matched: list[str]

        if isinstance(target, str):
            target = [target]

        if target is None:
            pass  # empty constructor is valid case for target building
        elif isinstance(target, list):
            # simplified and legacy way of assuming list of entities that can be discriminated by validator
            targets = list(target)
            # "<category>:<value>" entries scope a custom target without needing the full
            # mapping form - only recognised here, in the flat list/scalar form, so the mapping
            # form (`target: {category: value}`) stays available verbatim for any value that
            # collides with this syntax (e.g. one already containing a colon). A prefix is always
            # a target *category* (e.g. `topic:`, `email:`), never a transport or delivery name
            # directly - those are dynamic and only addressable via the mapping form.
            unprefixed: list[str] = []
            for t in targets:
                prefix, sep, rest = t.partition(":") if isinstance(t, str) else ("", "", "")
                if sep and rest and prefix in TARGET_CATEGORY_VALUES:
                    self.targets.setdefault(prefix, [])
                    if rest not in self.targets[prefix]:
                        self.targets[prefix].append(rest)
                else:
                    unprefixed.append(t)
            targets = unprefixed
            for category in self.AUTO_CATEGORIES:
                matched = self._filter_by_category(category, targets)
                if matched:
                    self.targets.setdefault(category, [])
                    self.targets[category].extend([t for t in matched if t not in self.targets[category]])
                    targets = [t for t in targets if t not in matched]
                if not targets:
                    break
            if targets:
                self.targets[self.UNKNOWN_CUSTOM_CATEGORY] = targets

        elif isinstance(target, dict):
            for category in target:
                targets = ensure_list(target[category])
                if not targets:
                    continue
                if category in self.AUTO_CATEGORIES:
                    matched = self._filter_by_category(category, targets)
                    if matched:
                        self.targets.setdefault(category, [])
                        self.targets[category].extend([t for t in matched if t not in self.targets[category]])

                elif category in self.CATEGORIES:
                    # categories that can't be automatically detected, like label_id
                    self.targets[category] = targets
                else:
                    # custom categories
                    self.targets[category] = targets
        else:
            _LOGGER.warning("SUPERNOTIFY Target created with no valid targets: %s", target)

        if target_data and target_specific_data:
            self.target_specific_data = {}
            for category, targets in self.targets.items():
                for t in targets:
                    self.target_specific_data[category, t] = target_data
        if target_data and not target_specific_data:
            self.target_data = target_data

    def _filter_by_category(self, category: str, candidates: list[str]) -> list[str]:
        matched: list[str] = []
        validator = getattr(self, f"is_{category}", None)
        if validator is not None:
            for t in candidates:
                if t not in matched and validator(t):
                    matched.append(t)
        else:
            _LOGGER.debug("SUPERNOTIFY Missing validator for selective target category %s", category)
        return matched

    # Targets by category

    @property
    def email(self) -> list[str]:
        return self.targets.get(ATTR_EMAIL, [])

    @property
    def entity_ids(self) -> list[str]:
        return self.targets.get(ATTR_ENTITY_ID, [])

    @property
    def person_ids(self) -> list[str]:
        return self.targets.get(ATTR_PERSON_ID, [])

    @property
    def device_ids(self) -> list[str]:
        return self.targets.get(ATTR_DEVICE_ID, [])

    @property
    def phone(self) -> list[str]:
        return self.targets.get(ATTR_PHONE, [])

    @property
    def mobile_app_ids(self) -> list[str]:
        return self.targets.get(ATTR_MOBILE_APP_ID, [])

    def domain_entity_ids(self, domain: str | None) -> list[str]:
        return [t for t in self.targets.get(ATTR_ENTITY_ID, []) if domain is not None and t and t.startswith(f"{domain}.")]

    def custom_ids(self, category: str) -> list[str]:
        return self.targets.get(category, []) if category not in self.CATEGORIES else []

    @property
    def area_ids(self) -> list[str]:
        return self.targets.get(ATTR_AREA_ID, [])

    @property
    def floor_ids(self) -> list[str]:
        return self.targets.get(ATTR_FLOOR_ID, [])

    @property
    def label_ids(self) -> list[str]:
        return self.targets.get(ATTR_LABEL_ID, [])

    # Selectors / validators

    @classmethod
    def is_device_id(cls, target: str) -> bool:
        return re.fullmatch(RE_DEVICE_ID, target) is not None

    @classmethod
    def is_entity_id(cls, target: str) -> bool:
        return valid_entity_id(target) and not target.startswith(("person.", "recipient."))

    @classmethod
    def is_person_id(cls, target: str) -> bool:
        """True for a real Person entity_id, or a Recipient's synthetic `recipient.<name>` id -
        used to identify a recipient with no Person record (see people.Recipient.entity_id).
        Both are `person_id`-category target values, resolved the same way downstream."""
        return target.startswith(("person.", "recipient.")) and valid_entity_id(target)

    @classmethod
    def is_phone(cls, target: str) -> bool:
        try:
            return phone(target) is not None
        except vol.Invalid:
            return False

    @classmethod
    def is_mobile_app_id(cls, target: str) -> bool:
        return not valid_entity_id(target) and target.startswith(f"{MOBILE_APP_DOMAIN}_")

    @classmethod
    def is_notify_entity(cls, target: str) -> bool:
        return valid_entity_id(target) and target.startswith(f"{NOTIFY_DOMAIN}.")

    @classmethod
    def is_email(cls, target: str) -> bool:
        try:
            return vol.Email()(target) is not None  # type: ignore[call-arg] # ty: ignore[missing-argument]
        except vol.Invalid:
            return False

    def has_targets(self) -> bool:
        return any(targets for targets in self.targets.values())

    def has_resolved_target(self) -> bool:
        return any(targets for category, targets in self.targets.items() if category not in self.INDIRECT_CATEGORIES)

    def has_unknown_targets(self) -> bool:
        return len(self.targets.get(self.UNKNOWN_CUSTOM_CATEGORY, [])) > 0

    def for_category(self, category: str) -> list[str]:
        return self.targets.get(category, [])

    def resolved_targets(self) -> list[str]:
        result: list[str] = []
        for category, targets in self.targets.items():
            if category not in self.INDIRECT_CATEGORIES:
                result.extend(targets)
        return result

    def hash_resolved(self) -> int:
        targets = []
        for category in self.targets:
            if category not in self.INDIRECT_CATEGORIES:
                targets.extend(self.targets[category])
        return hash(tuple(targets))

    @property
    def direct_categories(self) -> list[str]:
        return self.DIRECT_CATEGORIES + [cat for cat in self.targets if cat not in self.CATEGORIES]

    def direct(self) -> Target:
        t = Target(
            {cat: targets for cat, targets in self.targets.items() if cat in self.direct_categories},
            target_data=self.target_data,
        )
        if self.target_specific_data:
            t.target_specific_data = {k: v for k, v in self.target_specific_data.items() if k[0] in self.direct_categories}
        return t

    def extend(self, category: str, targets: list[str] | str) -> None:
        targets = ensure_list(targets)
        self.targets.setdefault(category, [])
        self.targets[category].extend(t for t in targets if t not in self.targets[category])

    def remove(self, category: str, targets: list[str] | str) -> None:
        targets = ensure_list(targets)
        if category in self.targets:
            self.targets[category] = [t for t in self.targets[category] if t not in targets]

    def safe_copy(self) -> Target:
        t = Target(dict(self.targets), target_data=dict(self.target_data) if self.target_data else None)
        t.target_specific_data = dict(self.target_specific_data) if self.target_specific_data else None
        return t

    def resolve_selectors(self, hass_api: HomeAssistantAPI) -> Target:
        """Replace `area_id`/`floor_id`/`label_id` targets with the entities they reference

        Resolution goes through the same core helper as a Home Assistant entity action, so
        groups are expanded and an entity inherits the area of its device. An entity in more
        than one of them - the kitchen, the first floor and the `voice` label - is kept once,
        and data attached to a selector is inherited by each of its entities, the same way as
        for a group member. Transports therefore never see a selector, and only the exception
        of an action that genuinely knows about areas needs `extra_data`.

        Returns this target untouched when there is no selector to resolve.
        """
        if not any(self.targets.get(category) for category in self.EXPLICIT_INDIRECT_CATEGORIES):
            return self
        kwarg: dict[str, str] = {ATTR_AREA_ID: "area_ids", ATTR_FLOOR_ID: "floor_ids", ATTR_LABEL_ID: "label_ids"}
        targets: dict[str, list[str]] = {
            category: list(values)
            for category, values in self.targets.items()
            if category not in self.EXPLICIT_INDIRECT_CATEGORIES
        }
        entity_ids: list[str] = targets.setdefault(ATTR_ENTITY_ID, [])
        inherited: dict[tuple[str, str], dict[str, Any]] = {}
        unknown: list[str] = []
        for category in self.EXPLICIT_INDIRECT_CATEGORIES:
            for value in self.targets.get(category, []):
                # one selector at a time, so data attached to it follows its own entities
                resolution = hass_api.resolve_target_selectors(**{kwarg[category]: [value]})
                if resolution.has_missing():
                    unknown.append(f"{category}:{value}")
                data: dict[str, Any] | None = (self.target_specific_data or {}).get((category, value))
                for entity_id in resolution.entity_ids:
                    if entity_id not in entity_ids:
                        entity_ids.append(entity_id)
                    if data and (ATTR_ENTITY_ID, entity_id) not in inherited:
                        inherited[(ATTR_ENTITY_ID, entity_id)] = data
        if unknown:
            # a typo in an area or label would otherwise silently resolve to nothing
            _LOGGER.warning("SUPERNOTIFY Unknown target selectors %s", ", ".join(unknown))
        resolved = Target(targets, target_data=self.target_data)
        if inherited or self.target_specific_data:
            # data attached to the entity itself wins over data inherited from a selector
            resolved.target_specific_data = inherited | {
                key: data
                for key, data in (self.target_specific_data or {}).items()
                if key[0] not in self.EXPLICIT_INDIRECT_CATEGORIES
            }
        return resolved

    def select(
        self,
        categories: Sequence[str | TargetEntityCategory],
        own_names: Collection[str],
        hass_api: HomeAssistantAPI,
        target_selector: SelectionRule | None = None,
    ) -> Target:
        """Narrow this target to what a delivery can use, leaving this one untouched

        `categories` are the delivery's declared target categories, and `own_names` its own
        name and its transport's. A target category named after either is always destined
        for that delivery. The two serve different purposes and both stay available:
         - the TRANSPORT name (`sms:value`) reaches every delivery of that transport, so
           scenario/time/occupancy selection logic can still decide which one actually
           fires - the same as it would for a plain, auto-matched value
         - a specific DELIVERY name (`shortcode_sms:value`) pins the target to just that
           one delivery, for when two deliveries of the same transport must stay distinct
           (e.g. `email` vs `html_email`)

        `person_id`s are always kept, whatever the delivery declares, since they aren't
        delivered to but are the link back to the recipients a delivery reaches (see
        `Notification.generate_targets()`, which narrows them to those actually in each
        envelope). They are kept out of the `target_selector` too, as it's for choosing
        between values a transport can address.
        """
        if any(self.targets.get(category) for category in self.EXPLICIT_INDIRECT_CATEGORIES):
            # area/floor/label always become entities first, so everything downstream - the
            # category checks, `target_select`, the transports - only ever sees entity_ids
            return self.resolve_selectors(hass_api).select(categories, own_names, hass_api, target_selector)

        plain_categories = {c for c in categories if isinstance(c, str)}
        entity_selectors = [c for c in categories if isinstance(c, TargetEntityCategory)]
        # HA groups (`group.*` helpers and platform groups such as media player groups) are
        # expanded into their members before the category and target_select checks, so a
        # transport that can't address a group itself still reaches its members
        expansions: dict[tuple[str, str], list[str]] = {}
        groups: set[tuple[str, str]] = set()

        def accepted(category: str, t: str, restricted: bool) -> bool:
            if (
                restricted
                and entity_selectors
                and category == ATTR_ENTITY_ID
                and not any(sel.matches(t, hass_api) for sel in entity_selectors)
            ):
                return False
            return target_selector is None or target_selector.match(t)

        def selected(category: str, targets: list[str]) -> list[str]:
            if category == ATTR_PERSON_ID:
                return targets
            restricted = category not in own_names
            if (
                restricted
                and not (entity_selectors and category == ATTR_ENTITY_ID)
                and plain_categories
                and category not in plain_categories
            ):
                # this delivery declares fixed categories (from its transport, its own
                # config, or both) - anything outside that set is rejected
                return []
            # else: this delivery declares no categories at all (e.g. `generic` with no
            # config) - nothing to restrict against
            chosen: list[str] = []
            for t in targets:
                members = hass_api.group_members(t) if category == ATTR_ENTITY_ID else None
                if members is None:
                    matched = [t] if accepted(category, t, restricted) else []
                else:
                    groups.add((category, t))
                    matched = [m for m in members if accepted(category, m, restricted)]
                    if not matched and accepted(category, t, restricted):
                        # group members unusable but the group id itself accepted, e.g. alexa_devices
                        matched = [t]
                expansions[(category, t)] = matched
                chosen.extend(m for m in matched if m not in chosen)
            return chosen

        filtered_target = Target({k: selected(k, v) for k, v in self.targets.items()}, target_data=self.target_data)
        if self.target_specific_data:
            # data inherited from a group first, so data explicitly attached to a member always wins
            specific_data: dict[tuple[str, str], dict[str, Any]] = {}
            for (c, t), data in self.target_specific_data.items():
                if (c, t) in groups:
                    for m in expansions.get((c, t), []):
                        specific_data[(c, m)] = data
            for (c, t), data in self.target_specific_data.items():
                if (c, t) not in groups and c in filtered_target.targets and t in filtered_target.targets[c]:
                    specific_data[(c, t)] = data
            filtered_target.target_specific_data = specific_data
        return filtered_target

    def split_by_target_data(self) -> list[Target]:
        if not self.target_specific_data:
            result = self.safe_copy()
            result.target_specific_data = None
            return [result]
        results: list[Target] = []
        default: Target = self.safe_copy()
        default.target_specific_data = None
        last_found: dict[str, Any] | None = None
        collected: dict[str, list[str]] = {}
        for (category, target), data in self.target_specific_data.items():
            if last_found is None:
                last_found = data
                collected = {category: [target]}
            elif data != last_found and last_found is not None:
                new_target: Target = Target(collected, target_data=last_found)
                results.append(new_target)
                default -= new_target
                last_found = data
                collected = {category: [target]}
            else:
                collected.setdefault(category, [])
                collected[category].append(target)
        new_target = Target(collected, target_data=last_found)
        results.append(new_target)
        default -= new_target
        if default.has_resolved_target():
            results.append(default)
        return results

    def __len__(self) -> int:
        """How many targets, whether direct or indirect"""
        return sum(len(targets) for targets in self.targets.values())

    def __add__(self, other: Target) -> Target:
        """Create a new target by adding another to this one"""
        new = Target()
        categories = set(list(self.targets.keys()) + list(other.targets.keys()))
        for category in categories:
            new.targets[category] = list(self.targets.get(category, []))
            new.targets[category].extend(t for t in other.targets.get(category, []) if t not in new.targets[category])

        new.target_data = dict(self.target_data) if self.target_data else None
        if other.target_data:
            if new.target_data is None:
                new.target_data = dict(other.target_data)
            else:
                new.target_data.update(other.target_data)
        new.target_specific_data = dict(self.target_specific_data) if self.target_specific_data else None
        if other.target_specific_data:
            if new.target_specific_data is None:
                new.target_specific_data = dict(other.target_specific_data)
            else:
                new.target_specific_data.update(other.target_specific_data)
        return new

    def __sub__(self, other: Target) -> Target:
        """Create a new target by removing another from this one, ignoring target_data"""
        new = Target()
        new.target_data = self.target_data
        if self.target_specific_data:
            new.target_specific_data = {
                k: v for k, v in self.target_specific_data.items() if k[1] not in other.targets.get(k[0], ())
            }
        categories = set(list(self.targets.keys()) + list(other.targets.keys()))
        for category in categories:
            new.targets[category] = []
            new.targets[category].extend(t for t in self.targets.get(category, []) if t not in other.targets.get(category, []))

        return new

    def __eq__(self, other: object) -> bool:
        """Compare two targets"""
        if other is self:
            return True
        if other is None:
            return False
        if not isinstance(other, Target):
            return NotImplemented
        if self.target_data != other.target_data:
            return False
        if self.target_specific_data != other.target_specific_data:
            return False
        return all(self.targets.get(category, []) == other.targets.get(category, []) for category in self.CATEGORIES)

    def as_dict(self, *, redact: bool = False, **_kwargs: Any) -> dict[str, list[str]]:
        result = {k: v for k, v in self.targets.items() if v}
        if redact:
            if ATTR_EMAIL in result:
                result[ATTR_EMAIL] = [partial_redact(v, unmasked_prefix=2, unmasked_suffix=1) for v in result[ATTR_EMAIL]]
            if ATTR_PHONE in result:
                result[ATTR_PHONE] = [partial_redact(v, unmasked_prefix=2, unmasked_suffix=1) for v in result[ATTR_PHONE]]
        return result
