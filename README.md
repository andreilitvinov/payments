# Async Payments Service

Микросервис для асинхронного процессинга платежей с `FastAPI`, `PostgreSQL`, `RabbitMQ`, `FastStream`, `SQLAlchemy 2.0`, `Alembic`, `Docker` и пакетным менеджером `uv`.

## Что реализовано

- `POST /api/v1/payments` с обязательными заголовками `X-API-Key` и `Idempotency-Key`
- `GET /api/v1/payments/{payment_id}`
- Outbox pattern (`payments` + `outbox` в одной транзакции)
- Публикация событий в `payments.new`
- Один consumer:
  - имитация обработки платежа (2-5 сек)
  - успех 90%, ошибка 10%
  - обновление статуса в БД
  - отправка webhook
  - retry (3 попытки, exponential backoff)
- DLQ: сообщения после 3 неудачных попыток летят в `payments.dlq`
- Отдельный DLQ consumer логирует сообщения из `payments.dlq` и обновляет метрики
- Тесты на идемпотентность и webhook retry
- RabbitMQ definitions (`rabbitmq/definitions.json`): durable очереди + TTL (`payments.new` 24ч, `payments.dlq` 7д)

### DLQ reason codes

- `invalid_payload` — некорректный формат входного сообщения
- `status_update_failed` — ошибка фиксации статуса платежа в БД
- `webhook_delivery_failed` — неуспешная доставка webhook после лимита попыток

## Запуск в Docker

```bash
cp .env.example .env
# заполните .env реальными значениями API_KEY, DATABASE_URL, RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_URL
docker compose up --build
```

Сервисы:
- API: `http://localhost:8000`
- RabbitMQ UI: `http://localhost:15672` (логин/пароль из `.env`)
- Метрики: `http://localhost:8000/metrics`

## Пример создания платежа

```bash
curl -X POST "http://localhost:8000/api/v1/payments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -H "Idempotency-Key: order-1001" \
  -d '{
    "amount": 1250.50,
    "currency": "RUB",
    "description": "Оплата заказа #1001",
    "metadata": {"customer_id": "c-42", "order_id": "1001"},
    "webhook_url": "https://example.com/webhook"
  }'
```

## Пример получения платежа

```bash
curl -X GET "http://localhost:8000/api/v1/payments/<payment_id>" \
  -H "X-API-Key: <your-api-key>"
```
