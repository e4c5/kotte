FROM postgres:16

# Install build essentials and dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-16 \
    libreadline-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build Apache AGE
RUN cd /tmp && \
    git clone https://github.com/apache/age.git && \
    cd age && \
    make && \
    make install

# Add startup script to load extension
COPY init-db.sql /docker-entrypoint-initdb.d/

EXPOSE 5432
