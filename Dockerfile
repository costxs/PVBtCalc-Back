# Python 3.13: scipy 1.18 / matplotlib 3.11 (usados nos calculos validados) nao tem build para 3.11.
FROM python:3.13.15-slim

# No display in the container: force the non-interactive backend
ENV MPLBACKEND=Agg \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Pre-warm the matplotlib font cache at build time so the first export after a
# cold start does not pay for cache construction.
RUN python -c "import matplotlib.pyplot as plt, io; f = plt.figure(); f.add_subplot().plot([1, 2, 3]); f.savefig(io.BytesIO(), format='png')"

COPY . .

EXPOSE 8000

# --proxy-headers: atras do proxy do Coolify, respeita X-Forwarded-Proto/For
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
