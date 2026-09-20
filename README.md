# SIEMPro

SIEMPro is a lightweight event registration and coordination system designed for college events. It helps administrators create events and competitions, allows participants to register, and supports volunteer coordination through a shared dashboard.

## Features

- Event creation and listing
- Competition setup with coordinator details and capacity limits
- Participant registration with duplicate and capacity checks
- Volunteer application management with role restriction checks
- Dashboard summary for counts and recent activity

## Tech Stack

- Python
- FastAPI
- SQLite
- Jinja2 templates
- HTML, CSS, JavaScript

## Run the project

1. Open the project folder.
2. Create a virtual environment if needed.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the server:

   ```bash
   python app.py
   ```

5. Open the browser at:

   ```text
   http://127.0.0.1:8000
   ```

## Deploy the app publicly

This project is already configured for simple hosting on Render or similar services.

### Option 1: Render

1. Push the project to GitHub.
2. Go to https://dashboard.render.com/
3. Click New > Web Service.
4. Connect the GitHub repository.
5. Use these settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
6. Click Create Web Service.
7. Render will give you a live public URL such as:
   `https://siempro.onrender.com`

### Option 2: Docker

```bash
docker build -t siempro .
docker run -p 8000:8000 siempro
```

Then open:

```text
http://localhost:8000
```

## Notes

The project stores data in a local SQLite database named `siempro.db` in the same directory as the app. For a production public deployment, consider using a persistent external database if long-term shared data is needed.
