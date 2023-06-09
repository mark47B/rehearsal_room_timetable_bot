from aiogram import Bot
from aiogram.types import BotCommand


async def set_default_commands(bot: Bot) -> None:
    await bot.set_my_commands(commands=
        [
            # BotCommand(command="help", description="help"),
            BotCommand(command="start", description="Начать"),
            BotCommand(command="info", description="Информация о репетиционной точке"),
            BotCommand(command="reserve", description="Забронировать"),
            BotCommand(command="check_free_slots", description="Свободные слоты"),
            BotCommand(command="free_my_slots", description="Освободить все мои слоты"),
            BotCommand(command="cancel", description="Отмена"),
        ]
    )
