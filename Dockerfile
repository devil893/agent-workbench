FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY workbench ./workbench
RUN pip install --no-cache-dir . && useradd --create-home app && mkdir /app/data && chown app /app/data
USER app
EXPOSE 8000
CMD ["uvicorn", "workbench.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
