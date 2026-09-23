FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY career_bot ./career_bot
ENTRYPOINT ["python", "-m", "career_bot"]
CMD ["run"]
