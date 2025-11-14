# API Документация для Мерчантов (Markets)

## Введение

API White Coin позволяет создавать маркеты (мерчанты) для скупки и продажи игровой валюты (BC - White Coins). API использует OAuth2 для авторизации и предоставляет полный набор функций для работы с балансами и переводами.

## Базовый URL

```
https://white-coin.ru/api/v1
```

## Получение API ключа

1. Откройте бота White Coin в Telegram
2. Перейдите в меню "Настройки"
3. Нажмите "Получить ключ API" или "Обновить ключ API"
4. Сохраните полученный ключ (32 символа)

**Важно:** Ключ API привязан к вашему профилю. Не передавайте его третьим лицам!

## Авторизация

API использует OAuth2 Bearer Token для авторизации. Все запросы (кроме `/auth`) требуют заголовок:

```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Получение токена для авторизации на сайте

**Endpoint:** `POST /auth`

**Content-Type:** `application/x-www-form-urlencoded`

**Параметры:**
- `username` (string, required) - ваш user_id
- `password` (string, required) - ваш API ключ

**Пример запроса:**
```bash
curl -X POST "https://white-coin.ru/api/v1/auth" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=123456789&password=YOUR_ACCESS_TOKEN"
```

**Пример ответа:**
```json
{
  "access_token": "YOUR_ACCESS_TOKEN",
  "token_type": "bearer"
}
```

## Endpoints

### 1. Получить баланс пользователя

**Endpoint:** `GET /balance`

**Авторизация:** Требуется

**Описание:** Возвращает текущий баланс пользователя, связанного с API ключом.

**Пример запроса:**
```bash
curl -X GET "https://white-coin.ru/api/v1/balance" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Пример ответа:**
```json
{
  "user_id": 123456789,
  "balance": 1000000
}
```

**Коды ошибок:**
- `401` - Не авторизован (неверный токен или токен не найден)
- `403` - Пользователь заблокирован
- `503` - API временно недоступен

---

### 2. Получить список транзакций

**Endpoint:** `GET /transactions`

**Авторизация:** Требуется

**Параметры запроса:**
- `type` (string, optional) - Тип транзакций: `"in"` (входящие), `"out"` (исходящие), `"all"` (все). По умолчанию: `"all"`
- `offset` (integer, optional) - Смещение для пагинации. По умолчанию: `0`
- `limit` (integer, optional) - Количество записей (1-100). По умолчанию: `20`

**Пример запроса:**
```bash
curl -X GET "https://white-coin.ru/api/v1/transactions?type=in&offset=0&limit=20" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Пример ответа:**
```json
[
  {
    "id": 1,
    "sender_id": 987654321,
    "recipient_id": 123456789,
    "amount": 50000,
    "created_at": "2024-01-15T10:30:00"
  },
  {
    "id": 2,
    "sender_id": 111222333,
    "recipient_id": 123456789,
    "amount": 100000,
    "created_at": "2024-01-15T11:00:00"
  }
]
```

**Коды ошибок:**
- `401` - Не авторизован
- `403` - Пользователь заблокирован
- `503` - API временно недоступен

---

### 3. Отправить перевод

**Endpoint:** `POST /send_coins`

**Авторизация:** Требуется

**Content-Type:** `application/json`

**Тело запроса:**
```json
{
  "recipient_id": 987654321,
  "amount": 50000
}
```

**Параметры:**
- `recipient_id` (integer, required) - ID получателя
- `amount` (integer, required) - Сумма перевода (минимум 1)

**Пример запроса:**
```bash
curl -X POST "https://white-coin.ru/api/v1/send_coins" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_id": 987654321,
    "amount": 50000
  }'
```

**Пример ответа:**
```json
{
  "id": 123,
  "sender_id": 123456789,
  "recipient_id": 987654321,
  "amount": 50000,
  "created_at": "2024-01-15T12:00:00"
}
```

**Коды ошибок:**
- `401` - Не авторизован
- `403` - Перевод запрещен (недостаточно средств, пользователь заблокирован, переводы запрещены и т.д.)
- `503` - API временно недоступен

**Возможные причины ошибки 403:**
- Недостаточно средств на балансе
- Получатель заблокирован
- Переводы заблокированы для отправителя или получателя
- Получатель не найден

---

### 4. Установить callback URL

**Endpoint:** `POST /callback`

**Авторизация:** Требуется

**Content-Type:** `application/json`

**Тело запроса:**
```json
{
  "url": "https://your-market.com/webhook"
}
```

**Параметры:**
- `url` (string, required) - URL для получения уведомлений о входящих переводах. Должен начинаться с `http://` или `https://`, длина 4-100 символов.

**Пример запроса:**
```bash
curl -X POST "https://white-coin.ru/api/v1/callback" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-market.com/webhook"
  }'
```

**Пример ответа:**
```json
{
  "callback_url": "https://your-market.com/webhook",
  "callback_secret": "SECRET_KEY_FOR_VERIFICATION"
```

**Важно:** Сохраните `callback_secret` для проверки подлинности уведомлений!

---

### 5. Удалить callback URL

**Endpoint:** `DELETE /callback`

**Авторизация:** Требуется

**Пример запроса:**
```bash
curl -X DELETE "https://white-coin.ru/api/v1/callback" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Пример ответа:**
```json
{
  "response": "ok"
}
```

---

## Callback уведомления

Если вы установили callback URL, при получении входящего перевода на ваш адрес будет отправлен POST запрос.

**URL:** Ваш указанный callback URL

**Method:** `POST`

**Headers:**
- `Content-Type: application/json`
- `X-Callback-Secret: YOUR_CALLBACK_SECRET` (для проверки подлинности)

**Тело запроса:**
```json
{
  "id": 123,
  "sender_id": 987654321,
  "recipient_id": 123456789,
  "amount": 50000,
  "created_at": "2024-01-15T12:00:00"
}
```

**Важно:** Всегда проверяйте заголовок `X-Callback-Secret` для подтверждения, что запрос действительно от White Coin API!

**Рекомендуемый ответ:**
Ваш сервер должен вернуть HTTP статус `200 OK` для подтверждения получения уведомления.

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `401` | Не авторизован - неверный токен или токен не найден |
| `403` | Доступ запрещен - пользователь заблокирован или операция запрещена |
| `503` | Сервис временно недоступен - API отключен или включен тихий режим |

---

## Примеры использования

### Python

```python
import requests

API_BASE_URL = "https://white-coin.ru/api/v1"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

# Получить баланс
response = requests.get(f"{API_BASE_URL}/balance", headers=headers)
balance_data = response.json()
print(f"Баланс: {balance_data['balance']} BC")

# Отправить перевод
transfer_data = {
    "recipient_id": 987654321,
    "amount": 50000
}
response = requests.post(
    f"{API_BASE_URL}/send_coins",
    headers=headers,
    json=transfer_data
)
transaction = response.json()
print(f"Перевод выполнен: {transaction['id']}")

# Получить входящие транзакции
response = requests.get(
    f"{API_BASE_URL}/transactions",
    headers=headers,
    params={"type": "in", "limit": 10}
)
transactions = response.json()
for tx in transactions:
    print(f"Получено {tx['amount']} BC от {tx['sender_id']}")
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

const API_BASE_URL = 'https://white-coin.ru/api/v1';
const ACCESS_TOKEN = 'YOUR_ACCESS_TOKEN';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Authorization': `Bearer ${ACCESS_TOKEN}`
  }
});

// Получить баланс
async function getBalance() {
  const response = await api.get('/balance');
  console.log(`Баланс: ${response.data.balance} BC`);
  return response.data;
}

// Отправить перевод
async function sendCoins(recipientId, amount) {
  const response = await api.post('/send_coins', {
    recipient_id: recipientId,
    amount: amount
  });
  console.log(`Перевод выполнен: ${response.data.id}`);
  return response.data;
}

// Получить транзакции
async function getTransactions(type = 'all', limit = 20) {
  const response = await api.get('/transactions', {
    params: { type, limit }
  });
  return response.data;
}
```

---

## Ограничения и рекомендации

1. **Безопасность:**
   - Храните API ключ в безопасном месте
   - Не передавайте ключ третьим лицам
   - Используйте HTTPS для всех запросов
   - Проверяйте `callback_secret` при получении уведомлений

2. **Лимиты:**
   - Максимальное количество записей в `/transactions`: 100
   - Минимальная сумма перевода: 1 BC
   - Callback URL должен быть доступен и отвечать в течение 5 секунд

3. **Рекомендации:**
   - Используйте пагинацию для получения больших списков транзакций
   - Реализуйте обработку ошибок и повторные попытки
   - Логируйте все операции для аудита
   - Регулярно проверяйте баланс перед операциями

---

## Поддержка

При возникновении проблем с API обращайтесь к администраторам проекта White Coin.

**Важно:** Продажа игровых ценностей запрещена правилами проекта! API предназначен для создания маркетов скупки/продажи валюты, но не для обхода правил проекта.


