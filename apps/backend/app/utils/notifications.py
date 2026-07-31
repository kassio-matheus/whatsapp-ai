import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    to: str
    subject: str
    body: str
    channel: str = "console"


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, notification: Notification) -> None: ...


class ConsoleChannel(NotificationChannel):
    def send(self, notification: Notification) -> None:
        logger.info(
            "Notification queued through %s channel | to=%s | subject=%s\n%s",
            notification.channel,
            notification.to,
            notification.subject,
            notification.body,
        )


class NotificationService:
    def __init__(self) -> None:
        self._channels: dict[str, NotificationChannel] = {}

    def register(self, name: str, channel: NotificationChannel) -> None:
        self._channels[name] = channel

    def send(self, notification: Notification) -> None:
        channel = self._channels.get(notification.channel)
        if channel:
            channel.send(notification)
        else:
            logger.warning("No channel registered for '%s'", notification.channel)


notification = NotificationService()
notification.register("console", ConsoleChannel())
