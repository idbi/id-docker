# Build/CI image for Node.js projects that also need a JVM.
#
# Alpine-based and pinned to Node 22 so artifacts produced here are binary
# compatible with the `node-runtime` image: same C library (musl) and same Node
# major. Installing dependencies on a glibc image and running them on the
# Alpine runtime silently degrades or breaks native modules — `sharp` falls
# back to its slow WASM build, node-gyp addons fail to load outright.
#
# This image carries NO application code: mount your project in, or COPY it in
# a downstream build stage.

FROM node:22-alpine

# The Debian `node` image ships all of these; Alpine ships none of them, and
# dropping any one breaks builds that work today:
#   bash             - this image's default CMD, and CI scripts assuming bash
#   git              - npm dependencies referenced by git URL, CI checkouts
#   curl, openssl,
#   ca-certificates  - HTTPS fetches from build scripts
#   rsync            - file synchronization / deployment steps
#   openjdk17-jre    - the JVM half of this image's purpose
#   python3 make g++ - node-gyp's toolchain. Needed far more often on musl than
#                      on glibc, because fewer packages publish musl prebuilds;
#                      without it, any compile-from-source dependency fails
#                      with "gyp ERR! find Python".
RUN apk add --no-cache \
        bash \
        git \
        curl \
        openssl \
        ca-certificates \
        rsync \
        openjdk17-jre \
        python3 \
        make \
        g++ \
    && java -version \
    && node -v \
    && npm -v

# Set Docker working directory
WORKDIR /app

# Optionally: copy sources and install dependencies here, if needed
# COPY package*.json ./
# RUN npm install

# Default command is a bash shell for development or further commands
CMD ["bash"]
