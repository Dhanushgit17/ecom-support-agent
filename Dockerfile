FROM python:3.12-slim

WORKDIR /app

# Requirements first: this layer is cached unless requirements.txt changes,
# so editing code doesn't reinstall 110 packages on every build.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# chroma_db/ is gitignored, so the vector index isn't in the repo.
# Build it here so it's baked into the image and startup is fast.
RUN python rag.py

CMD ["bash", "start.sh"]