# 1. Use a lightweight Python base image
FROM python:3.12-slim

# 2. Install our lightning-fast package manager
RUN pip install uv

# 3. Set our working directory inside the container
WORKDIR /app

# 4. Copy ONLY the project config first (this makes Docker build way faster)
COPY pyproject.toml .

# 5. The Magic: Tell uv to read pyproject.toml and install everything globally in the container!
RUN uv pip install --system -r pyproject.toml

# 6. Copy the rest of your actual code (main.py, etc.)
COPY . .

# 7. Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]