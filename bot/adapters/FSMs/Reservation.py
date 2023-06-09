from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from aiogram.types import Message
from adapters.buttons import make_row_keyboard, available_days, available_time, agreement
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from aiogram import types
from aiogram.types import ReplyKeyboardRemove

from core.timetable import days_nums
from service.store import Excel_interactions, GoogleSheet_interactions
import core.timetable as tt
from ..buttons import get_timetable, get_commands, capital_first

from config import config

from core.entities import ProfileLink, GENERAL_FUNCTIONALITY


router = Router()


class Reservation_fsm(StatesGroup):
    day_selection = State()
    time_selection = State()
    acceptance = State()
    contact_sharing = State()
    tg_sharing = State()
    vk_sharing = State()

    async def clear(self) -> None:
        await self.set_state(state=None)
        await self.set_data({})


# Entrypoint handler for 'reserve'
@router.message(Command("reserve"))
async def entrypoint(message: Message, state: FSMContext):
    await message.answer(
        text="Выберите день ",
        reply_markup=make_row_keyboard(available_days)
    )
    await state.set_state(Reservation_fsm.day_selection)
 # Additional options for calling 'Reservation'   
router.message.register(entrypoint, F.text.in_(GENERAL_FUNCTIONALITY['reserve']))


# Handler for day selection
@router.message(
    Reservation_fsm.day_selection,
    F.text.in_(available_days)
)
async def select_day(message: Message, state: FSMContext):
    await state.update_data(day=message.text.lower())
    user_data = await state.get_data()
    await message.answer(
        text=f"Вы выбрали '{user_data['day']}'. Спасибо.\n<b>Сейчас, пожалуйста, выберите время</b>",
        reply_markup=make_row_keyboard(available_time)
    )
    await state.set_state(Reservation_fsm.time_selection)


@router.message(Reservation_fsm.day_selection)
async def incorrect_day(message: Message):
    await message.answer(
        text="<b>Некорректный формат дня недели!</b> \n\n"
             "Пожалуйста, выберите день из списка ниже:",
        reply_markup=make_row_keyboard(available_days)
    )


@router.message(
    Reservation_fsm.time_selection,
    F.text.in_(available_time)
)
async def select_time(message: Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Отправить  Telegram  профиль", request_contact=True))

    await state.update_data(time=message.text.lower())
    user_data = await state.get_data()

    # Реализация запрета бронирования уже занятого места
    dict_with_free_slots = tt.searching_free_slots()
    if capital_first(user_data['day']) in dict_with_free_slots.keys() and user_data['time'] in dict_with_free_slots[capital_first(user_data['day'])] :
        await message.answer(
            text=f"Вы выбрали день '{user_data['day']}' и время '{user_data['time']}'.\n"
                "<b>Сейчас поделитесь Вашим контактом в Telegram</b>",
                reply_markup=builder.as_markup(resize_keyboard=True)
        )
        await state.set_state(Reservation_fsm.contact_sharing)
    else:
        await message.answer(
            text=f"Вы выбрали занятый слот: '{user_data['day']}' и время '{user_data['time']}'.\n"
                "<b>Пожалуйста, выберите другой слот</b>",
                reply_markup=make_row_keyboard(available_days)
        )
        await state.clear()
        await state.set_state(Reservation_fsm.day_selection)



@router.message(Reservation_fsm.time_selection)
async def incorrect_time(message: Message):
    await message.answer(
        text="Неправильный формат времени! \n\n"
             "<b>Выберите один из слотов из списка ниже<b>",
        reply_markup=make_row_keyboard(available_time)
    )


# Handler for contact sharing
@router.message(
    Reservation_fsm.contact_sharing,
    F.contact
)
async def select_contact(message: Message, state: FSMContext):
    if not message.contact.user_id == message.from_user.id:
        builder = ReplyKeyboardBuilder()
        builder.row(types.KeyboardButton(text="Отправить  Telegram  профиль", request_contact=True))
        await message.answer(text='Отправьте, пожалуйста, Ваш контакт', reply_markup=builder.as_markup(resize_keyboard=True))
    else:
        await state.update_data(user_id=message.contact.user_id)
        user_data = await state.get_data()
        await message.answer(
            text=f"<b>Вы выбрали день:</b> {user_data['day']}\n"
                 f"<b>Время:</b> {user_data['time']} \n"
                 f"<b>Telegram profile:</b> <a href=\"tg://user?id={message.contact.user_id}\">{message.from_user.full_name}</a>.\n\n"
                 "<b>Бронируем?</b>",
            reply_markup=make_row_keyboard(agreement)
        )
        await state.set_state(Reservation_fsm.acceptance)


# @router.message(Reservation_fsm.contact_sharing)
# async def incorrect_day(message: Message):
#     builder = ReplyKeyboardBuilder()
#     builder.row(types.KeyboardButton(text="Отправить  Telegram  профиль", request_contact=True))
#     await message.answer(
#         text="Пожалуйста, поделитесь контактом Telegram, чтобы другие музыканты могли с Вами связаться 📲",
#         request_contact=True,
#         reply_markup=builder.as_markup(resize_keyboard=True)
#     )


@router.message(
    Reservation_fsm.acceptance,
    F.text.in_(agreement)
)
async def final_reservation(message: Message, state: FSMContext):
    if message.text.lower() == 'да':
        user_data = await state.get_data()
        # timetable_xlsx = Excel_interactions(config.EXCEL_PATH)
        timetable_xlsx = GoogleSheet_interactions(CREDENTIALS_FILE=config.SERVICE_ACCOUNT_CREDENTIALS_PATH, spreadsheetId=config.SPREADSHEET_ID)
        # Translation (time, day) to excel cell (letter, number), should be decompose
        day_to_letter= { d.lower():chr(n+66) for n, d in enumerate(available_days)}
        time_to_number = { t:str(n+2) for n, t in enumerate(available_time) }

        pos = (day_to_letter[user_data['day']], time_to_number[user_data['time']])

        user_data = await state.get_data()
        profile = ProfileLink(**{'id': user_data['user_id'],
                                 'fullname': message.from_user.full_name
                                 })
        timetable_xlsx.put(data=profile, position=pos)
        await message.answer(
            text=f"Время успешно забронировано!",
            reply_markup=get_commands()
        )

    if message.text.lower() == 'нет':
        await message.answer(
            text=f"Бронь отменена.",
            reply_markup=get_commands()
        )
    await message.answer(tt.get_timetable_pretty(), reply_markup=get_timetable())
    await state.clear()


@router.message(Reservation_fsm.acceptance)
async def incorrect_day(message: Message):
    await message.answer(
        text="Выберите вариант из списка ниже. Бронируем?",
        reply_markup=make_row_keyboard(agreement)
    )
