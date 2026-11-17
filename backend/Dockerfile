FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend ./

ARG INSTALL_EXTRAS=
RUN if [ -n "$INSTALL_EXTRAS" ]; then \
        pip install --no-cache-dir ".[${INSTALL_EXTRAS}]"; \
    else \
        pip install --no-cache-dir .; \
    fi

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /app
RUN chown -R appuser:appuser /home/appuser/.cache

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
