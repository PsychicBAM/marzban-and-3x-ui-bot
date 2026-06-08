\# Cursor cheat sheet for Telegram VPN Bot



\## Goal



Create a new clean Telegram VPN sales bot.



The bot must support:



\* Marzban

\* 3x-ui

\* PostgreSQL

\* Docker

\* QR-code generation

\* Customer menu

\* Admin panel

\* Manual payment confirmation

\* Tariffs with IP limit / device count

\* Expiry notifications: 7 / 3 / 1 days



\## Paths



Old bot:

C:\\Users\\abdal\\Desktop\\Telegram-BOT-VPN\\arabic\_course\_bot



New bot:

C:\\Users\\abdal\\Desktop\\Telegram-BOT-VPN\\marzban and 3x-ui bot



\## How to save Cursor tokens



Do not ask:

“Rewrite the whole project.”



Ask:

“Inspect only files related to Marzban API and identify functions for login, create user, update user and subscription link.”



Do not ask:

“Look at all code.”



Ask:

“Work only with app/services and app/models.”



Do not ask:

“Build everything at once.”



Work in stages:



1\. Create project structure.

2\. Add Docker and .env.example.

3\. Add config system.

4\. Add database models.

5\. Add Alembic migrations.

6\. Add Marzban service.

7\. Add 3x-ui service.

8\. Add customer menu.

9\. Add admin menu.

10\. Add payment requests.

11\. Add QR-code generation.

12\. Add expiry notifications.

13\. Add README and deployment docs.



\## Old bot rule



Do not modify the old bot.

Do not delete files from the old bot.

Do not copy old architecture.



Allowed to reuse only:



\* Marzban authentication

\* create user

\* update user

\* disable user

\* enable user

\* delete user

\* get subscription link

\* get user status



\## Database rule



Use PostgreSQL for the new project.



Do not directly edit Marzban or 3x-ui SQLite databases.



The bot must communicate with Marzban and 3x-ui only through their APIs.



\## Secrets rule



Never commit:



\* .env

\* Telegram bot token

\* Marzban credentials

\* 3x-ui credentials

\* database password

\* real payment details



GitHub must contain only:



\* .env.example

\* source code

\* Dockerfile

\* docker-compose.yml

\* migrations

\* README.md

\* docs



\## Docker rule



docker-compose.yml must contain:

restart: unless-stopped



Services:



\* bot

\* postgres



PostgreSQL data must be stored in a Docker volume.



\## QR-code rule



Generate QR-code inside the bot from subscription link or VPN link.



Do not permanently store QR images unless necessary.



Prefer generating QR-code in memory and sending it directly to Telegram.



\## Before every commit



Run:



git status



Make sure these files are NOT included:



\* .env

\* \*.db

\* \*.sqlite

\* backups/

\* logs/

\* generated QR images

\* tokens

\* passwords



