FROM python:3.12-slim

# HF Spaces runs the container as a non-root user with uid 1000
RUN useradd -m -u 1000 user

USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

# Requirements first: this layer is cached unless requirements.txt changes,
# so editing code doesn't reinstall 110 packages on every build.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# chroma_db/ is gitignored, so the vector index isn't in the repo.
# Build it here so it's baked into the image and startup is fast.
RUN python rag.py

EXPOSE 7860

CMD ["bash", "start.sh"]