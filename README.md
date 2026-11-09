# llm-catalog-search

Прототип интеллектуального интерфейса к каталогу товаров

Пользователь пишет запрос на естественном языке («Покажи самые дешевые ноутбуки до 80 тысяч рублей»), 
LLM превращает его в структурированный объект ProductQuery, а обычная программа проверяет параметры и ищет товары в SQLite.

LLM не пишет и не выполняет SQL, а только интерпретирует запрос. SQL собирает код из белого списка полей,
значения передаются параметрами.

Отчет: [report/report.md](report/report.md). Демонстрация всех частей с выводами: [notebooks/demo.ipynb](notebooks/demo.ipynb).

## Структура

| Путь                 | Назначение                                                                                                                          |
|----------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| src/config.py        | Чтение .env, создание клиента ChatOpenAI (make_llm, режим размышления выключен по умолчанию)                                        |
| src/schema.py        | Pydantic-модель ProductQuery                                                                                                        |
| src/chains.py        | Промпты и LCEL-цепочки: категория (ч. 1), структурированный ответ (ч. 2), поиск через RunnableLambda (ч. 3), промпты диалога (ч. 5) |
| src/db.py            | Каталог SQLite: создание и заполнение, параметризованный поиск                                                                      |
| src/tools.py         | Поиск как инструмент LangChain search_products + bind_tools                                                                         |
| src/pipeline.py      | Итоговый пайплайн: retry, проверка, поиск, обработка ошибок                                                                         |
| src/journal.py       | Журнал шагов (токен в журнал не попадает)                                                                                           |
| src/dialog.py        | Уточняющие запросы: состояние вне модели и вариант с историей диалога                                                               |
| scripts/init_db.py   | Скрипт инициализации базы data/catalog.db                                                                                           |
| tests/               | Офлайн-тесты pytest на фейковой модели (сервер и токен не нужны)                                                                    |
| notebooks/demo.ipynb | Прогон частей 1-5 на реальной модели с сохраненными выводами                                                                        |
| report/report.md     | Отчет, report/results.json - данные прогона ноутбука                                                                                |

## Требования

* Python 3.12
* Доступ к серверу модели `http://10.32.2.11:35000/v1` (сеть университета или VPN) и персональный токен (только для
  ноутбука). Тесты работают без них
* SQLite отдельно устанавливать не нужно, используется встроенный модуль sqlite3

## Установка

Команды для Windows выполняются из корня репозитория:

```bat
cd /d "путь\к\llm-catalog-search"
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

<details>
<summary>Linux / macOS</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
</details>

### Токен

Скопируйте шаблон и впишите в .env свой токен:

```bat
copy .env.example .env
```

```
LITELLM_BASE_URL=http://10.32.2.11:35000/v1
LITELLM_API_KEY=ваш_токен
MODEL_NAME=qwen3.8-27b
```

Токен читается только из окружения. Файл .env указан в .gitignore и в репозиторий не попадает.

## Запуск

### База данных

```bat
python scripts\init_db.py
```

Скрипт создает data/catalog.db (16 товаров: 6 ноутбуков, 5 смартфонов, 4 планшета и 1 товар неподдерживаемой
категории). Ноутбук пересоздает базу сам в первой ячейке, а функция поиска создает ее, если файла нет.

### Тесты (без сервера и токена)

```bat
pytest -q
```

26 тестов: схема и невалидные ответы (4.1), поиск по SQLite, retry на фейковой модели (4.4), диалог (ч. 5),
отсутствие токена в журнале.

### Ноутбук

Нужны токен в .env и доступ к серверу. Зарегистрируйте ядро окружения (один раз):

```bat
python -m ipykernel install --user --name llm-catalog-search --display-name "Python (llm-catalog-search)"
```

Интерактивно:

```bat
jupyter lab
```

Откройте notebooks/demo.ipynb, выберите ядро **Python (llm-catalog-search)** и выполните
**Kernel -> Restart Kernel and Run All Cells**.

Без интерфейса (выводы сохраняются в сам ноутбук):

```bat
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=llm-catalog-search --ExecutePreprocessor.timeout=600 notebooks\demo.ipynb
```

Ноутбук также сохраняет данные прогона в report/results.json
