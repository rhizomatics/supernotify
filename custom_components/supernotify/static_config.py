from .transport import Transport
from .transports.alexa_devices import AlexaDevicesTransport
from .transports.alexa_media_player import AlexaMediaPlayerTransport
from .transports.chime import ChimeTransport
from .transports.discord import DiscordTransport
from .transports.email import EmailTransport
from .transports.generic import GenericTransport
from .transports.gotify import GotifyTransport
from .transports.html5 import HTML5Transport
from .transports.kodi import KodiTransport
from .transports.lametric import LaMetricTransport
from .transports.matrix import MatrixTransport
from .transports.media_player import MediaPlayerTransport
from .transports.mobile_push import MobilePushTransport
from .transports.mqtt import MQTTTransport
from .transports.notify_entity import NotifyEntityTransport
from .transports.ntfy import NtfyTransport
from .transports.persistent import PersistentTransport
from .transports.pushover import PushoverTransport
from .transports.sms import SMSTransport
from .transports.telegram import TelegramTransport
from .transports.tts import TTSTransport

TRANSPORTS: list[type[Transport]] = [
    EmailTransport,
    SMSTransport,
    MQTTTransport,
    AlexaDevicesTransport,
    AlexaMediaPlayerTransport,
    MobilePushTransport,
    MediaPlayerTransport,
    ChimeTransport,
    PersistentTransport,
    GenericTransport,
    TTSTransport,
    NotifyEntityTransport,
    NtfyTransport,
    GotifyTransport,
    TelegramTransport,
    LaMetricTransport,
    PushoverTransport,
    HTML5Transport,
    MatrixTransport,
    KodiTransport,
    DiscordTransport,
]  # No auto-discovery of transport plugins so manual class registration required here

TRANSPORT_NAMES = [t.name for t in TRANSPORTS]
