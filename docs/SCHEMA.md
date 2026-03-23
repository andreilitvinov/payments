# Схема БД

## ER (описание)

```
┌─────────────────────┐       ┌─────────────────────────────┐
│ orders              │       │ payments                     │
├─────────────────────┤       ├─────────────────────────────┤
│ id (PK)             │───┐   │ id (PK)                      │
│ total_amount        │   └──<│ order_id (FK → orders.id)    │
│ payment_status      │       │ payment_type (cash|acquiring) │
└─────────────────────┘       │ deposited_amount             │
                              │ refunded_amount              │
                              │ status (pending|completed|   │
                              │         failed|refunded)      │
                              │ bank_payment_id (nullable)    │
                              │ bank_checked_at              │
                              │ created_at, updated_at       │
                              └─────────────────────────────┘
```

## Таблицы

### orders

| Колонка          | Тип           | Описание                                      |
|------------------|----------------|-----------------------------------------------|
| id               | SERIAL PK      | Внутренний идентификатор                      |
| total_amount     | NUMERIC(12,2)  | Сумма заказа                                  |
| payment_status   | VARCHAR(32)    | unpaid \| partially_paid \| paid              |

### payments

| Колонка          | Тип            | Описание                                      |
|------------------|----------------|-----------------------------------------------|
| id               | SERIAL PK      | Внутренний идентификатор                      |
| order_id         | INT FK         | Ссылка на orders.id                           |
| payment_type     | VARCHAR(32)    | cash \| acquiring                            |
| deposited_amount | NUMERIC(12,2)  | Внесённая сумма                               |
| refunded_amount  | NUMERIC(12,2)  | Сумма возврата                                |
| status           | VARCHAR(32)    | pending \| completed \| failed \| refunded   |
| bank_payment_id   | VARCHAR(128)   | ID платежа в банке (для эквайринга)          |
| bank_checked_at  | TIMESTAMPTZ    | Время последней проверки статуса в банке      |
| created_at       | TIMESTAMPTZ    | Время создания                                |
| updated_at       | TIMESTAMPTZ    | Время обновления                              |

Сумма всех успешных платежей по заказу (deposited_amount − refunded_amount по записям со status = completed) не должна превышать total_amount заказа. Это обеспечивается на уровне приложения при создании платежа и при депозите.
