FROM node:20-slim AS node-base

# Install snarkjs globally
RUN npm install -g snarkjs

FROM python:3.12-slim

# Copy snarkjs from node stage
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
RUN ln -s /usr/local/lib/node_modules/snarkjs/cli.js /usr/local/bin/snarkjs && \
    chmod +x /usr/local/bin/snarkjs

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY . .

# Circuit artifacts (pre-compiled — run compile_circuits.sh first)
# COPY keys/ ./keys/

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
