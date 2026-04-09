# Restaurant Booking Telegram Bot

AI-powered Telegram bot for managing restaurant table reservations and answering customer questions.

## Features

- **Table booking** — multi-turn conversation to collect date, time, guest count, name and phone
- **Booking management** — modify or cancel existing reservations
- **Q&A via RAG** — answers questions about the restaurant using a knowledge base (menu, hours, contacts, etc.)
- **Admin agent** — admin can query the database, view today's bookings, and message customers directly from Telegram
- **Notifications** — admin receives Telegram alerts on every new/modified/cancelled booking
- **Docker support** — runs fully containerized with MySQL

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Bot framework | python-telegram-bot |
| Conversation flow | LangGraph (state machine) |
| LLM (intent & extraction) | Groq (LLaMA) |
| LLM (RAG answers) | OpenAI GPT-4o-mini |
| Vector store | ChromaDB |
| Database | MySQL 8.0 |
| Containerization | Docker + Docker Compose |

## Project Structure

```
├── bot/
│   └── telegram_bot.py       # Telegram handlers
├── graph/
│   ├── builder.py            # LangGraph state machine
│   ├── state.py              # State definitions
│   └── nodes/               # Graph nodes (classify, extract, validate, modify, cancel)
├── db/
│   ├── save_booking.py
│   ├── modify_booking.py
│   ├── cancel_booking.py
│   ├── check_table.py
│   └── get_bookings.py
├── RAG/
│   ├── chroma_store.py       # ChromaDB setup
│   ├── init_chroma.py        # Initialize vector store from info.md
│   └── parser.py             # Markdown chunker
├── admin/
│   └── admin_agent.py        # Admin agent with tools
├── init_db/
│   └── init.sql              # Database schema + seed data
├── info.md                   # Restaurant knowledge base
├── config.py                 # Environment variable loading
├── main.py                   # Entry point
├── docker-compose.yml
└── Dockerfile
```

## Database Schema

- **users** — telegram_id, name, phone
- **tables** — id, capacity (22 tables: 10×2-seat, 8×4-seat, 4×6-seat)
- **bookings** — order_id, user_id, table_id, start_time, end_time, count_clients

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/restaurant-business_project.git
cd restaurant-business_project
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in your values in `.env` (see [Environment Variables](#environment-variables)).

### 3. Run with Docker

```bash
docker-compose up --build
```

The bot starts automatically after the database is healthy. The RAG vector store is initialized on first run.

### 4. Run locally (without Docker)

```bash
pip install -r requirements.txt

# Start MySQL separately and update .env with connection details
python main.py
```

## Environment Variables

Create a `.env` file based on the table below:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY` | OpenAI API key (used for RAG embeddings and answers) |
| `GROQ_API_KEY` | Groq API key (used for intent classification and extraction) |
| `ADMIN_TG_ID` | Telegram user ID of the admin |
| `DB_HOST` | MySQL host (default: `db` in Docker, `localhost` locally) |
| `DB_PORT` | MySQL port (default: `3306`) |
| `DB_USER` | MySQL user (default: `root`) |
| `DB_PASSWORD` | MySQL password |
| `DB_NAME` | MySQL database name (default: `restaurant`) |
| `LANGCHAIN_API_KEY` | *(Optional)* LangSmith API key for tracing |
| `LANGCHAIN_TRACING_V2` | *(Optional)* Set to `true` to enable LangSmith tracing |

## How It Works

### Booking Flow (LangGraph)

```
User message
    │
    ▼
classify_intent ──► new_booking ──► extraction ──► validate_hours ──► check_table ──► save
                │
                ├──► modify_booking ──► modify ──► modify_db
                │
                └──► cancel_booking ──► cancel ──► cancel_db
```

1. **classify_intent** — Groq LLaMA determines whether the user wants to book, modify, cancel, or ask a question
2. **extraction** — collects booking details across multiple messages (date, time, guests, name, phone)
3. **validate_hours** — checks that the requested time falls within operating hours
4. **check_table** — finds an available table with enough capacity
5. **save** — writes to MySQL and notifies the admin

### RAG (Question Answering)

`info.md` is chunked by section and embedded into ChromaDB using OpenAI embeddings. On each question, the top relevant chunks are retrieved and passed to GPT-4o-mini to generate an answer.

### Admin Agent

The admin interacts with the bot via natural language. Available tools:
- Query today's bookings
- Look up any booking by ID or customer name
- Send a message to any customer

## License

MIT
