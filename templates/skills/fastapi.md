---
display_name: "FastAPI"
description: "Паттерны и лучшие практики FastAPI"
tags: [python, fastapi, api, backend]
---

# Навык: FastAPI

## Основные паттерны:
- Pydantic v2 модели для request/response схем (используй `model_validator`, `field_validator`)
- Dependency Injection через `Depends()` — для сервисов, сессий БД, текущего пользователя
- Path-операции с полными аннотациями типов и `response_model`
- `BackgroundTasks` для отложенной работы (email, уведомления)
- Middleware для сквозной функциональности (логирование, CORS, timing)
- `APIRouter` для группировки эндпоинтов по доменам

## Структура проекта:
```
app/
├── main.py # FastAPI app, lifespan, подключение роутеров
├── config.py # Pydantic Settings для конфигурации
├── routes/ # Эндпоинты, сгруппированные по доменам
│ ├── init.py
│ ├── users.py
│ └── items.py
├── schemas/ # Pydantic-модели (вход/выход/фильтры)
│ ├── users.py
│ └── items.py
├── models/ # ORM-модели (SQLAlchemy)
├── services/ # Бизнес-логика
├── repositories/ # Слой доступа к данным
├── dependencies.py # DI — get_db, get_current_user и т.д.
└── exceptions.py # Кастомные HTTP-исключения + обработчики
```


## Модели — всегда разделяй:
- `CreateUserRequest` — входная схема (без id, без created_at)
- `UpdateUserRequest` — все поля `Optional`, для PATCH
- `UserResponse` — выходная схема (без пароля, с computed-полями)
- `UserInDB` — внутренняя модель/ORM (не утекает наружу)

## Лучшие практики:
- `status_code` явно на каждом эндпоинте: `@router.post(..., status_code=201)`
- `HTTPException` с осмысленным `detail` — не "Error", а "User with email 'x@y.z' already exists"
- `response_model_exclude_none=True` для чистых ответов
- Async-обработчики для I/O-bound операций (БД, HTTP-запросы)
- Sync-обработчики для CPU-bound (FastAPI сам вынесет в threadpool)
- `Annotated[Depends(...)]` для переиспользуемых зависимостей (Python 3.11+)
- `lifespan` context manager вместо `on_startup`/`on_shutdown`

## Обработка ошибок:
- Кастомные exception-классы наследуют от базового `AppException`
- Глобальные `exception_handler` для единообразных ответов
- Валидационные ошибки Pydantic автоматически → 422 с подробностями
- Бизнес-ошибки → 400/409/404, системные → 500 с логированием

## Безопасность:
- `OAuth2PasswordBearer` + JWT для аутентификации
- Зависимость `get_current_user` на защищённых роутах
- Rate limiting через middleware или `slowapi`
- CORS — явный список `allow_origins`, не `["*"]` в проде
