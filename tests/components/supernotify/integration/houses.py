"""The integration test houses, as plain data, used by conftest.py's fixtures. preview_house is
also what preview/seed.py makes of the Docker preview Home Assistant, so has only what that can
really have: the demo integration's entities, users, people, floors, areas and template PIRs.

Each is the keyword arguments of framework.House, with `config` naming a YAML file alongside
this one rather than holding its text.
"""

from __future__ import annotations

from typing import Any

HOUSES: dict[str, dict[str, Any]] = {
    # The Docker preview, from the demo integration plus what seed.py adds, with a completely
    # default Supernotify installation with zero YAML.
    #     - 2 floors, with 5 rooms, 3 of them the demo integration's own
    #     - 2 User accounts, each with a Person, and no mobile apps
    #     - The demo integration's cameras, media players, notify entity, sirens and switches
    #     - 2 PIRs
    "preview_house": {
        "demo": True,
        "alexa_per_area": False,
        "floors": ["ground", "first"],
        "areas": {
            "kitchen": "ground",
            "living room": "ground",
            "bedroom": "first",
            "office": "first",
            "garden": None,
        },
        "users": {"alice": "alice", "bob": "bob"},
        "pirs": {"hall_pir": "living room", "garden_pir": "garden"},
    },
    # A minimal Home Assistant setup, with no technical users, and a completely default
    # Supernotify installation with zero YAML.
    #     - One floor, but not defined in HA, no areas, no labels
    #     - One User account, with a Person
    #     - One mobile app
    "starter_flat": {
        "users": {"jo": "jo"},
        "apple_apps": {"jo_phone": "jo"},
    },
    # A slightly richer Home Assistant setup, with no technical users, and a completely default
    # Supernotify installation with zero YAML.
    #     - 2 floors, with 5 rooms defined
    #     - Five Alexa echo devices
    #     - 2 Mobile apps, with just enough config to make them work
    #     - 2 cameras
    #     - 2 PIRs
    "town_house": {
        "floors": ["ground", "first"],
        "areas": {
            "kitchen": "ground",
            "lounge": "ground",
            "garage": "ground",
            "bedroom": "first",
            "office": "first",
            "garden": None,
        },
        "users": {"alice": "alice", "bob": "bob"},
        "android_apps": {"bob_phone": "bob"},
        "apple_apps": {"alice_phone": "alice"},
        "cameras": {"front_door": "garage", "back_garden": None},
        "pirs": {"hall_pir": "lounge", "garden_pir": None},
    },
    # A richer Home Assistant setup, and Supernotify configured with YAML, from smart_villa.yaml
    # alongside this file, which is where its scenarios will go too.
    #     - 3 floors, with 7 rooms defined
    #     - 3 Mobile apps
    #     - 2 cameras
    #     - 2 PIRs
    #     - A doorbell chime delivery, ringing a hall chime switch and the gate siren
    "smart_villa": {
        "floors": ["basement", "ground", "first"],
        "areas": {
            "hall": "ground",
            "kitchen": "ground",
            "lounge": "ground",
            "master_bedroom": "first",
            "guest_suite": "first",
            "cinema": "basement",
            "pool_house": None,
        },
        "users": {"carla": "carla", "dev": "dev", "nonna": "nonna"},
        "android_apps": {"dev_phone": "dev"},
        "apple_apps": {"carla_phone": "carla", "nonna_tablet": "nonna"},
        "cameras": {"gate": None, "pool": "pool_house"},
        "pirs": {"hall_pir": "hall", "pool_pir": "pool_house"},
        "config": "smart_villa.yaml",
        "stub_actions": ["switch.turn_on", "siren.turn_on"],
    },
}
