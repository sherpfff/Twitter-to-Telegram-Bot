import os
import json
import time
import logging
import signal
import sys
from dotenv import load_dotenv
from telegram import Bot
import tweepy

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройки Twitter API (из переменных окружения)
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Настройки Telegram Bot API (из переменных окружения)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# Список аккаунтов Twitter, за которыми нужно следить
TWITTER_ACCOUNTS = ["twitter_account1", "twitter_account2"]

# Файл для хранения последних твитов
LAST_TWEETS_FILE = "last_tweets.json"

# Инициализация клиента Twitter
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

# Инициализация Telegram бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Глобальные переменные
last_tweets = {}


def load_last_tweets():
    """Загружает последние твиты из файла."""
    try:
        with open(LAST_TWEETS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_last_tweets(last_tweets):
    """Сохраняет последние твиты в файл."""
    with open(LAST_TWEETS_FILE, "w") as f:
        json.dump(last_tweets, f)


def get_latest_tweet(user_id):
    """Получает последний твит пользователя с медиа."""
    tweets = client.get_users_tweets(
        id=user_id,
        max_results=1,
        exclude="retweets",
        expansions="attachments.media_keys",
        media_fields=["url"],
    )
    if tweets.data:
        tweet = tweets.data[0]
        media_urls = []
        if "attachments" in tweet.data and "media_keys" in tweet.data["attachments"]:
            media_keys = tweet.data["attachments"]["media_keys"]
            media = {m["media_key"]: m for m in tweets.includes["media"]}
            for key in media_keys:
                if key in media and "url" in media[key]:
                    media_urls.append(media[key]["url"])
        return tweet.id, tweet.text, media_urls
    return None, None, []


def send_to_telegram(message, media_urls=None):
    """Отправляет сообщение в Telegram канал с медиа."""
    if media_urls:
        message += "\n\nМедиа:\n" + "\n".join(media_urls)
    bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode="Markdown")


def shutdown(signal, frame):
    """Обработчик завершения работы."""
    logging.info("Остановка мониторинга...")
    save_last_tweets(last_tweets)
    sys.exit(0)


def main():
    global last_tweets

    # Загружаем последние твиты
    last_tweets = load_last_tweets()

    # Получаем ID пользователей Twitter
    user_ids = {}
    for username in TWITTER_ACCOUNTS:
        user = client.get_user(username=username)
        user_ids[user.data.id] = username
        if str(user.data.id) not in last_tweets:
            last_tweets[str(user.data.id)] = None

    logging.info("Мониторинг твитов запущен...")

    while True:
        try:
            for user_id, username in user_ids.items():
                tweet_id, tweet_text, media_urls = get_latest_tweet(user_id)

                # Если новый твит найден и он отличается от последнего
                if tweet_id and str(tweet_id) != last_tweets[str(user_id)]:
                    last_tweets[str(user_id)] = str(tweet_id)
                    message = f"*Новый твит от* @{username}:\n\n{tweet_text}"
                    send_to_telegram(message, media_urls)
                    logging.info(f"Отправлен твит от @{username}: {tweet_text}")

            # Сохраняем последние твиты
            save_last_tweets(last_tweets)

            # Ждем перед следующей проверкой
            time.sleep(300)  # Проверяем каждые 5 минут

        except Exception as e:
            logging.error(f"Ошибка: {e}")
            time.sleep(60)  # При ошибке ждем минуту и продолжаем


if __name__ == "__main__":
    # Обработчик сигнала для завершения работы
    signal.signal(signal.SIGINT, shutdown)

    # Запуск основного цикла
    main()
