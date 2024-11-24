import configparser
import json
import os
import httpx
import time
import re
from urllib.parse import unquote
from loguru import logger
from bs4 import BeautifulSoup

logger.remove()  
logger.add(
    sink=lambda msg: print(msg.strip()), 
    format="ParsThreads | {time:HH:mm:ss} | HashBrute | {level}: {message}",
    level="INFO",
)


config = configparser.ConfigParser(interpolation=None)
config.read("config.ini")

cookies = {key: unquote(value) for key, value in config["cookies"].items()}

headers = {
    "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Priority': 'u=0, i',
}

userid = config["parameters"]["userid"]
username = config["parameters"]["username"]

base_url = "https://lolz.live/forums/"
progress_file = "progress.txt"
output_file = "final.txt"
xfurl = "https://lolz.live"



def fetch_xf_token():
    logger.info("Получение xfToken...")
    try:
        with httpx.Client(cookies=cookies, headers=headers) as client:
            response = client.get(xfurl, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                xf_token_tag = soup.find('input', {'name': '_xfToken'})
                if xf_token_tag:
                    xf_token = xf_token_tag.get('value', '')
                    logger.info(f"xfToken успешно получен: {xf_token}")
                    return xf_token
                else:
                    logger.error("Не удалось найти xfToken на странице.")
                    return None
            else:
                logger.error(f"Ошибка запроса при получении xfToken: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при получении xfToken: {e}")
        return None


def save_progress(page):
    with open(progress_file, "w") as file:
        file.write(str(page))


def load_progress():
    try:
        with open(progress_file, "r") as file:
            return int(file.read().strip())
    except FileNotFoundError:
        return 1


def sort_and_save_ids(input_file, output_file):
    try:
        with open(input_file, "r") as file:
            ids = file.readlines()

        ids = list(dict.fromkeys(id.strip() for id in ids))

        def extract_id(link):
            match = re.search(r'https://lolz\.live/threads/(\d+)', link)
            return match.group(1) if match else "0"

        def calculate_repetition_score(thread_id):
            max_streak = 1
            current_streak = 1
            for i in range(1, len(thread_id)):
                if thread_id[i] == thread_id[i - 1]:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1
            return max_streak

        ids.sort(key=lambda x: (-calculate_repetition_score(extract_id(x)), x))

        with open(output_file, "w") as file:
            file.write("\n".join(ids))

        logger.info(f"Финальная обработка завершена. Уникальных ссылок: {len(ids)}.")
    except FileNotFoundError:
        logger.error(f"Файл {input_file} не найден.")



def parse_and_save(response_json):
    try:
        data = json.loads(response_json)

        html_content = data.get("templateHtml", "")
        if not html_content:
            logger.warning("HTML не найден в JSON")
            return 0

        matches = re.findall(r'href=["\']?threads[\\/](\d+)[\\/"]?', html_content)
        if matches:
            with open(output_file, "a") as file:
                for match in matches:
                    file.write(f"https://lolz.live/threads/{match}\n") 
            logger.info(f"Спаршено {len(matches)} ID.")
            return len(matches)
        else:
            logger.warning("ID не найдены на этой странице.")
            return 0
    except json.JSONDecodeError:
        logger.error("Ошибка при парсинге JSON")
        return 0
    except KeyError:
        logger.error("Ключ templateHtml отсутствует в JSON")
        return 0

    


def reset_progress():
    if os.path.exists(progress_file):
        os.remove(progress_file)
        logger.info("Файл прогресса сброшен.")
    else:
        logger.info("Файл прогресса не существует. Сбрасывать нечего.")

        
def main():
    print("Автор: HashBrute")
    print("1. Запустить парс айди")
    print("2. Запустить парс удаленных айди")
    choice = input("Выберите действие (1 или 2): ").strip()

    xfToken = fetch_xf_token()
    if not xfToken:
        logger.error("Не удалось получить xfToken. Завершаем.")
        return

    if choice == "1":
        logger.info("Запущен парс активных ID.")
        url_template = f"{base_url}?page={{}}&enabled=1&tab=userthreads&order=last_post_date&direction=desc&user_id={userid}&next_page_loading=1&_xfResponseType=json&_xfToken={xfToken}&_threadFilter=1"
    elif choice == "2":
        logger.info("Запущен парс удаленных ID.")
        url_template = f"{base_url}?page={{}}&enabled=1&tab=mythreads&order=last_post_date&direction=desc&state=deleted&next_page_loading=1&_xfResponseType=json&_xfToken={xfToken}&_threadFilter=1"
    else:
        logger.error("Некорректный выбор. Завершаем.")
        return

    current_page = load_progress()
    logger.info(f"Начинаем с page={current_page}")

    try:
        with httpx.Client(cookies=cookies, headers=headers) as client:
            while True:
                try:
                    url = url_template.format(current_page)
                    logger.info(f"Делаем запрос")
                    response = client.get(url, timeout=10)

                    if response.status_code == 200:
                        ids_fetched = parse_and_save(response.text)
                        if ids_fetched == 0:
                            logger.info("Данные закончились. Завершаем.")
                            reset_progress()
                            break

                        current_page += 1
                        save_progress(current_page)
                    else:
                        logger.error(f"Ошибка запроса: {response.status_code}")
                        save_progress(current_page)
                        break

                    time.sleep(2)

                except httpx.ConnectTimeout:
                    logger.warning("Тайм-аут. Ждем 10 секунд и повторяем...")
                    time.sleep(10)
                except Exception as e:
                    logger.error(f"Ошибка: {e}. Сохраняем прогресс.")
                    save_progress(current_page)
                    break

        logger.info("Удаляем дубликаты и сортируем ID...")
        sort_and_save_ids(output_file, output_file)

    except KeyboardInterrupt:
        logger.warning("Остановлено пользователем. Сохраняем прогресс.")
        save_progress(current_page)


if __name__ == "__main__":
    main()
