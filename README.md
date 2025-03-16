# 🚀 Ambrosia Dashboard

Ambrosia Dashboard is a Django-based web application that runs inside **Docker** using **PostgreSQL**, **Nginx**, and **Gunicorn**.

## 📌 Features
- 🌱 **Django Backend** (Python 3.12)
- 📊 **PostgreSQL Database**
- 🔥 **Gunicorn for Application Server**
- 🌍 **Nginx as Reverse Proxy**
- ✅ **Dockerized for Easy Deployment**

---

## 🛠️ **Installation & Setup**
### 1. **Clone the Repository**
```
git clone https://github.com/ambrosia2024/dashboard.git
cd dashboard
```

### 2. Rename .env.sample to .env
```
mv .env.sample .env
```

Then, update your .env file with your credentials:
```
DJANGO_SECRET_KEY=your_django_secret

POSTGRES_DB=ambrosia
POSTGRES_USER=amb_admin
POSTGRES_PASSWORD=password
POSTGRES_HOST=ambrosia_postgres
POSTGRES_PORT=5432
PGADMIN_DEFAULT_EMAIL=youremail@domain.com
PGADMIN_DEFAULT_PASSWORD=password
```

### 3. Run the Application
```
docker compose up -d
```

This will:
- 🐳 Pull required images
- 🏗️ Build the Django application
- 🔌 Set up the PostgreSQL database
- 🌍 Run the Nginx reverse proxy

## 🔥 Access the Application
### 🌐 Web App	http://localhost/

