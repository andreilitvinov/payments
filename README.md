# Сервис работы с платежами по заказу

Тестовое задание: сервис платежей (наличные и эквайринг), интеграция с API банка, REST API, хранение в PostgreSQL.

## Стек

- **FastAPI** — веб-API, валидация (Pydantic)
- **SQLAlchemy 2 + Alembic** — ORM и миграции
- **PostgreSQL** — хранилище
- **httpx** — асинхронные запросы к API банка
- **pytest** — тесты

## Архитектура

- **API (api/)** — маршруты, схемы запросов/ответов, обработка ошибок и валидация.
- **Service (services/)** — бизнес-логика: создание/возврат платежей, учёт суммы по заказу, вызов банка для эквайринга.
- **Repository (db/repositories/)** — доступ к БД (заказы, платежи).
- **Integrations (integrations/)** — клиент API банка (acquiring_start, acquiring_check), таймауты и разбор ошибок.

Модель платежа одна для всех типов (cash/acquiring); различие только в поле `payment_type` и в том, что для эквайринга сохраняется `bank_payment_id` и статус синхронизируется с банком через `acquiring_check`.

## Запуск

### Локально

1. Установить Poetry (если не установлен)
2. Установить зависимости: `poetry install`
3. Поднять PostgreSQL (например: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16-alpine`)
4. Переменные окружения (опционально): `DATABASE_URL`, `BANK_API_BASE_URL`, `BANK_API_TIMEOUT_SECONDS`
5. Миграции: `poetry run alembic upgrade head`
6. Запуск приложения: `poetry run uvicorn main:app --reload`

### Docker Compose

```bash
docker compose up --build
```

API: http://localhost:8000  
Документация: http://localhost:8000/docs

## API банка (внешняя система)

- **POST acquiring_start** — тело: `{ "order_number", "order_amount" }`; успех → `bank_payment_id`, иначе — ошибка.
- **GET acquiring_check** — query: `bank_payment_id`; ответ: данные платежа или «платеж не найден».

Код обращения к API: `integrations/bank_client.py`. Учтены таймауты, сетевые ошибки и разбор ответов; состояние платежа в банке может измениться независимо от приложения, поэтому предусмотрена синхронизация через вызов `acquiring_check` (ручка **POST /api/payments/{id}/sync** или фоновая задача).

## REST API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/orders | Список заказов |
| GET | /api/orders/{order_id} | Заказ по ID |
| POST | /api/orders | Создать заказ (total_amount) |
| POST | /api/orders/{order_id}/payments | Создать платёж (payment_type: cash \| acquiring, amount) |
| GET | /api/payments/{payment_id} | Платёж по ID |
| POST | /api/payments/{payment_id}/refund | Возврат (body: amount) |
| POST | /api/payments/{payment_id}/sync | Синхронизация статуса эквайринга с банком |

Входные данные проверяются (Pydantic); ошибки внутренних операций и банка возвращаются с подходящими HTTP-кодами (400, 404, 409, 502).

## Схема БД

См. [docs/SCHEMA.md](docs/SCHEMA.md).

## Тесты

```bash
poetry run pytest tests/ -v
```

- **tests/test_payments.py** — доменная логика (in-memory: заказ, платежи, депозит/возврат, лимит суммы).
- **tests/test_service.py** — сервисный слой с моком банка (cash/acquiring, sync).
- **tests/test_api.py** — HTTP-ручки (TestClient, переопределённый get_db, SQLite in-memory).

## Операции без REST

Сервис `PaymentService` можно вызывать из любого кода (скрипты, фоновые задачи):

```python
from db.session import SessionLocal
from services.payment_service import PaymentService
from payments.models import PaymentType

db = SessionLocal()
svc = PaymentService(db=db)
# svc.add_order(...), await svc.create_payment(...), svc.refund(...), await svc.sync_acquiring_payment(...)
```

Синхронизация эквайринга с банком: периодически вызывать `sync_acquiring_payment` для платежей со статусом `pending` и типом `acquiring` (например, через FastAPI BackgroundTasks или отдельный воркер).
