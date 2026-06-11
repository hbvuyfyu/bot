# AK Jumper Bot

A Telegram bot for AppsFlyer, Adjust, and Singular event sending with farming capabilities.

## Features

- AppsFlyer event sending
- Adjust event sending
- Singular event sending
- Farm system for automated level progression
- Proxy support
- Admin panel for user management
- PostgreSQL (Neon) database support

## Deployment

### Railway

1. Click "Deploy on Railway" button
2. Set environment variables:
   - `BOT_TOKEN`: Your Telegram bot token
   - `DATABASE_URL`: Your Neon PostgreSQL connection string
   - `ADMIN_IDS`: Comma-separated admin user IDs
   - `SUPPORT_USER`: Support username

### Manual

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure
4. Run the SQL schema: `psql -f schema.sql` (or via Neon dashboard)
5. Run: `python main.py`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| BOT_TOKEN | Telegram bot token | Yes |
| DATABASE_URL | PostgreSQL connection string | Yes |
| ADMIN_IDS | Admin user IDs (comma-separated) | Yes |
| SUPPORT_USER | Support username | No |

## Database Setup

Run the `schema.sql` file on your Neon PostgreSQL database to create all required tables.

## License

MIT
