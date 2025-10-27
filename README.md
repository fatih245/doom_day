# Voter ID Portal

Modern Django-based portal (Arabic-first) that lets voters authenticate with their voter number, upload identification images, and monitor the review status of their submissions. Built for deployment on a VPS and serving a custom subdomain.

## Features
- Voter number login with session-based authentication
- Two-image upload workflow (national ID + voter card) with automatic OCR validation
- Automatic orientation correction and smart cropping before OCR
- Administrative dashboard (مخصصة لرقم الناخب الإداري) لمراقبة حالة الرفع
- Responsive, modern UI that adapts to phones, tablets, and desktops
- CSV/Excel importer for bulk voter provisioning
- Arabic user interface and RTL styling
- Production-ready static asset handling via WhiteNoise and Gunicorn support

## Tech stack
- Python 3.11+
- Django 5.2
- SQLite for local development (swap for PostgreSQL/MySQL in production)
- Gunicorn application server + WhiteNoise for static files

## Local setup
1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run migrations and start the development server:
   ```bash
   python manage.py migrate
   python manage.py startserver
   ```
4. Visit http://127.0.0.1:8000/ to sign in with a voter number that exists in your database.
5. When you're done, stop the server:
   ```bash
   python manage.py stopserver
   ```
   (You can still use `runserver`/`Ctrl+C` manually if you prefer.)
6. Uploadات الوثائق تتطلب صورتين في آنٍ واحد: الهوية الوطنية وبطاقة الناخب. يتأكد النظام تلقائيًا من وضوح النص، من تطابق أرقام الهوية مع سنة الميلاد والرقم الوطني المسجل، ومن أن بطاقة الناخب تحتوي على رقم الناخب الصحيح. كما يتم تدوير الصور تلقائيًا إذا كانت مائلة وقصها حول النص قبل المعالجة. تخزن الصور في مجلد يحمل رقم الناخب.
7. الناخب الذي يطابق `ADMIN_VOTER_NUMBER` (افتراضيًا 17157528) يُعاد توجيهه إلى لوحة إدارة تعرض حالة بقية الناخبين.

## Managing voters
- Import voters from a CSV file with `voter_number`, `full_name`, and optional `email`:
  ```bash
  python manage.py import_voters path/to/voters.csv
  ```
  Use `--dry-run` to validate without persisting and `--deactivate-missing` to disable voters omitted from the CSV.
- Import directly from an Excel workbook (مثل الملف "شميرام كركوك"):
  ```bash
  python manage.py import_voters_excel "path/to/شميرام كركوك.xlsx"
  ```
  Add `--dry-run` to preview without saving; use `--sheet <name>` to target a specific worksheet.
- Create staff accounts for administrators:
  ```bash
  python manage.py createsuperuser
  ```
  The Django admin (`/admin/`) lets staff review and update ID document status/notes.

## Running tests
```bash
python manage.py test
```

## Environment variables
Configure these variables before deploying:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Unique, unpredictable key for session signing |
| `DJANGO_DEBUG` | Set to `0` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of domains/IPs |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated `https://` origins for CSRF protection when HTTPS is enabled |
| `DJANGO_SECURE_SSL_REDIRECT` | Force HTTPS redirects (defaults to `1` عندما يكون DEBUG معطلًا) |
| `DJANGO_HSTS_SECONDS` | مدة تفعيل HSTS بالثواني (الافتراضي لعام كامل) |
| `ADMIN_VOTER_NUMBER` | رقم الناخب المخوّل لعرض لوحة الإدارة |

## Automatic document checks (OCR)
- يعتمد النظام على مكتبة EasyOCR (لغات عربية/إنجليزية) لتحليل النص في الصور.
- الهوية الوطنية: يتحقق من إمكانية قراءة الرقم، ويستخرج أول أربعة أرقام للتحقق من سنة الميلاد. إذا لم تكن سنة الميلاد محفوظة مسبقًا، يتم حفظها تلقائيًا عند نجاح الاستخراج.
- بطاقة الناخب: يتحقق من احتواء الصورة على رقم الناخب المسجل في قاعدة البيانات.
- تخزن الملفات داخل `media/id_uploads/<رقم_الناخب>/` مع أسماء فريدة تشتمل على نوع الوثيقة.

## Deployment on a VPS
Example outline for Ubuntu 22.04 (adjust paths and usernames as needed):

1. **Provision server & subdomain**
   - Point your subdomain's A/AAAA DNS record (e.g. `portal.example.com`) to the VPS IP.
   - Update `DJANGO_ALLOWED_HOSTS="portal.example.com"` and `DJANGO_CSRF_TRUSTED_ORIGINS="https://portal.example.com"`.

2. **Install system packages**
   ```bash
   sudo apt update && sudo apt install python3-pip python3-venv nginx git
   ```

3. **Clone project & setup virtualenv**
   ```bash
   git clone https://your.repo/project_doom_day.git /srv/voter-portal
   cd /srv/voter-portal
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure application**
   ```bash
   export DJANGO_SECRET_KEY='your-prod-secret'
   export DJANGO_DEBUG=0
   export DJANGO_ALLOWED_HOSTS='portal.example.com'
   export DJANGO_CSRF_TRUSTED_ORIGINS='https://portal.example.com'
   python manage.py migrate
   python manage.py collectstatic --no-input
   python manage.py createsuperuser
   ```

5. **Gunicorn systemd service** (`/etc/systemd/system/voter-portal.service`):
   ```ini
   [Unit]
   Description=Gunicorn instance for Voter Portal
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/srv/voter-portal
   Environment="DJANGO_SECRET_KEY=your-prod-secret"
   Environment="DJANGO_DEBUG=0"
   Environment="DJANGO_ALLOWED_HOSTS=portal.example.com"
   Environment="DJANGO_CSRF_TRUSTED_ORIGINS=https://portal.example.com"
    Environment="ADMIN_VOTER_NUMBER=17157528"
    Environment="DJANGO_SECURE_SSL_REDIRECT=1"
    Environment="DJANGO_HSTS_SECONDS=31536000"
   ExecStart=/srv/voter-portal/.venv/bin/gunicorn voter_portal.wsgi:application \
       --workers 5 \
       --bind unix:/run/voter-portal.sock
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```
   Then enable and start (اضبط عدد الـ workers بناءً على عدد أنوية المعالج: قاعدة جيدة `workers = 2 * CPU + 1`):
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now voter-portal
   ```

6. **Nginx reverse proxy** (`/etc/nginx/sites-available/voter-portal`):
   ```nginx
   server {
       listen 80;
       server_name portal.example.com;

       location = /favicon.ico { access_log off; log_not_found off; }
       location /static/ {
           alias /srv/voter-portal/staticfiles/;
       }
       location /media/ {
           alias /srv/voter-portal/media/;
       }

       location / {
           include proxy_params;
           proxy_pass http://unix:/run/voter-portal.sock;
       }
   }
   ```
   Enable the site and reload Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/voter-portal /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

7. **TLS (Let's Encrypt)**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d portal.example.com
   ```
   Certbot adds the TLS server block automatically; confirm renewal with `sudo systemctl status certbot.timer`.

8. **Media files backup**
   - Persist `/srv/voter-portal/media/` (ID uploads) by mounting external storage or scheduling nightly backups.

With these steps the site will respond at your subdomain, serve static files efficiently, and route requests to Gunicorn/Django.

## Next steps
- Replace SQLite with PostgreSQL for concurrency at scale.
- Add staff review workflows (approve/reject actions) directly in the dashboard if needed.
- Integrate background jobs or notifications for status changes.
