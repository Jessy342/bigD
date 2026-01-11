FROM node:20-slim AS frontend
WORKDIR /app
COPY ["Front End/package.json", "Front End/package-lock.json", "./Front End/"]
RUN cd "Front End" && npm ci
COPY ["Front End", "./Front End"]
RUN cd "Front End" && npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
COPY ["Back End/requirements.txt", "./Back End/requirements.txt"]
RUN pip install --no-cache-dir -r "Back End/requirements.txt"
COPY ["Back End", "./Back End"]
COPY --from=frontend /app/Front End/build ./Front End/build
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
WORKDIR /app/Back End
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
