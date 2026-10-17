# A/B bench image: one image for system A and system B.
# Claude Code and Codex CLI at the versions installed on the host; kuNNA test deps.
# The subagent-pool skill is NOT baked in: run.py mounts a read-only checkout and install.py runs at start.
#   docker build --network host -t kunna-bench:1 competition/   (bridge build networking had no DNS here)
FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv git ca-certificates coreutils procps \
 && rm -rf /var/lib/apt/lists/*

# Global CLIs, pinned to the host versions (claude 2.1.302, codex 0.160.0)
RUN npm install -g @anthropic-ai/claude-code@2.1.302 @openai/codex@0.160.0 jest@29 jest-environment-jsdom@29 jsdom@24 \
 && npm cache clean --force

# kuNNA test deps: frontend suite is Jest (jsdom); backend/requirements.txt subset the hidden tests import, plus pytest and httpx for TestClient
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install \
      fastapi==0.104.1 \
      pydantic==2.5.0 \
      requests==2.31.0 \
      psutil==5.9.6 \
      httpx==0.27.2 \
      pytest==8.3.3
ENV PATH=/opt/venv/bin:$PATH \
    NODE_PATH=/usr/local/lib/node_modules

# Non-root user (uid 1000 matches the host user; run.py also passes --user explicitly)
RUN userdel -r node \
 && useradd -m -u 1000 -s /bin/bash bench \
 && mkdir -p /work /bench && chown bench:bench /work /bench
USER bench
WORKDIR /work
