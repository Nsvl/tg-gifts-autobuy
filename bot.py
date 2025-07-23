import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.methods import GetAvailableGifts, SendGift
from aiogram.filters import Command

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_ID = int(os.getenv("TELEGRAM_ID"))
MAXIMUM_SUPPLY = int(os.getenv("MAXIMUM_SUPPLY", 700000))
MAXIMUM_PRICE = int(os.getenv("MAXIMUM_PRICE", 6000))
BUY_STRATEGY = int(os.getenv("BUY_STRATEGY", 1))

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

is_paused = False
last_gifts = []

@dp.message(Command("pause"))
async def pause_cmd(message: types.Message):
    global is_paused
    is_paused = True
    await message.answer("⏸️ Автопокупка приостановлена.")

@dp.message(Command("resume"))
async def resume_cmd(message: types.Message):
    global is_paused
    is_paused = False
    await message.answer("▶️ Автопокупка возобновлена.")

@dp.message(Command("status"))
async def status_cmd(message: types.Message):
    await message.answer(
        f"🤖 Статус: {'⏸️ Пауза' if is_paused else '▶️ Активен'}\n"
        f"Фильтр: до {MAXIMUM_PRICE} звёзд, не более {MAXIMUM_SUPPLY} шт.\n"
        f"Стратегия: {BUY_STRATEGY}"
    )

@dp.message(Command("last"))
async def last_cmd(message: types.Message):
    if not last_gifts:
        await message.answer("Подарков пока не найдено.")
        return
    msg = "🎁 Последние найденные подарки:\n"
    for gift in last_gifts:
        msg += f"• {getattr(gift, 'id', '?')} — {getattr(gift, 'star_count', '?')} звёзд, всего: {getattr(gift, 'total_count', '?')}\n"
    await message.answer(msg)

def log(msg):
    print(f"[{asyncio.get_event_loop().time():.0f}] {msg}")

async def main():
    global last_gifts
    log("🤖 Gift auto-buyer started!")
    await bot.send_message(TELEGRAM_ID, "🤖 Gift auto-buyer запущен!\n\n"
                                        "Доступные команды:\n"
                                        "/pause — пауза\n"
                                        "/resume — возобновить\n"
                                        "/status — статус\n"
                                        "/last — последние подарки")

    last_not_sold_out_ids = set()
    while True:
        try:
            if is_paused:
                await asyncio.sleep(2)
                continue

            gifts = await bot(GetAvailableGifts())
            if not gifts or not getattr(gifts, "gifts", None):
                log("Нет подарков, ждем...")
                await asyncio.sleep(5)
                continue

            not_sold_out = [
                g for g in gifts.gifts
                if getattr(g, "limited", False) and not getattr(g, "soldOut", False)
            ]
            last_gifts = not_sold_out

            current_ids = set(getattr(g, "id", None) for g in not_sold_out)
            new_ids = current_ids - last_not_sold_out_ids
            if new_ids:
                await bot.send_message(
                    TELEGRAM_ID,
                    f"🎉 Новые подарки вышли! ID: {', '.join(map(str, new_ids))}"
                )
                log(f"Новые подарки: {', '.join(map(str, new_ids))}")
            last_not_sold_out_ids = current_ids

            if not not_sold_out:
                log("Ждём подарков...")
                await asyncio.sleep(5)
                continue

            gifts_matching = [
                g for g in not_sold_out
                if getattr(g, "star_count", 0) <= MAXIMUM_PRICE and
                   getattr(g, "total_count", 0) <= MAXIMUM_SUPPLY
            ]
            if not gifts_matching:
                log("Нет подарков по фильтрам")
                await asyncio.sleep(5)
                continue

            if BUY_STRATEGY == 2:
                gifts_to_buy = [gifts_matching[0]]
            elif BUY_STRATEGY == 3:
                gifts_to_buy = [gifts_matching[-1]]
            else:
                gifts_to_buy = gifts_matching

            for gift in gifts_to_buy:
                try:
                    result = await bot(SendGift(
                        chat_id=TELEGRAM_ID,
                        gift_id=getattr(gift, "id"),
                        text="🎁 Автопокупка подарка!"
                    ))
                    if result:
                        await bot.send_message(
                            TELEGRAM_ID,
                            f"✅ Куплен подарок: {getattr(gift, 'id')} за {getattr(gift, 'star_count', 0)} ⭐️"
                        )
                        log(f"Куплен подарок: {getattr(gift, 'id')}")
                    else:
                        log(f"Не удалось купить подарок: {getattr(gift, 'id')}")
                        await bot.send_message(
                            TELEGRAM_ID,
                            f"❌ Не удалось купить подарок: {getattr(gift, 'id')}"
                        )
                except Exception as e:
                    log(f"Ошибка при покупке подарка: {e}")
                    await bot.send_message(
                        TELEGRAM_ID,
                        f"❌ Ошибка при покупке подарка: {e}"
                    )
            await asyncio.sleep(5)
        except Exception as e:
            log(f"Ошибка основного цикла: {e}")
            await bot.send_message(TELEGRAM_ID, f"❗️ Ошибка: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling(bot))
    loop.run_until_complete(main())