# ---------- Frontend build ----------
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /frontend

COPY ["Front End/package.json", "./"]
COPY ["Front End/package-lock.json", "./"]
RUN npm install

COPY ["Front End/", "./"]
RUN npm run build

# ---------- Backend ----------
FROM python:3.11-slim
WORKDIR /app

COPY ["Back End/requirements.txt", "./requirements.txt"]
RUN pip install --no-cache-dir -r requirements.txt

COPY ["Back End/", "./"]

# Copy built frontend (Vite = dist)
COPY --from=frontend-build ["/frontend/build", "/app/static"]


ENV PORT=10000
EXPOSE 10000

CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
