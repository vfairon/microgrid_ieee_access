# Use an official Ubuntu base image
FROM ubuntu:22.04

# Set environment variables for non-interactive installations
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    python3.6 \
    python3-pip \
    wget \
    git \
    openssh-client \
    openssh-server \
    sshpass \
    iproute2 \
    iputils-ping \
    && apt-get clean \
    && mkdir -p /run/sshd \
    && yes '1' | passwd root \
    && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Install gcc-9 and g++-9
RUN apt-get update && apt-get install -y \
    gcc-9 \
    g++-9 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-9 90 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-9 90


# Create a symlink to use 'python3' as 'python' (since python3.6 is the default)
RUN ln -s /usr/bin/python3.6 /usr/bin/python

# Install pybind11
RUN pip3 install pybind11

# Install pandapower (for the pandapower_outstation.py alternative to PowerWorld DS)
RUN pip3 install pandapower
RUN pip3 install numba

# Install C++14 compiler (gcc/g++)
RUN apt-get install -y gcc g++ 

# Set the default C++ standard to C++14
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-9 90 && \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-9 90

# Verify installations
RUN g++ --version && cmake --version && python3 --version && pip3 show pybind11

# Clone and build pydnp3
RUN git clone --recursive http://github.com/Kisensum/pydnp3 && \
    cd pydnp3 && \
    python3 setup.py install


# No WORKDIR here on purpose: `docker cp <src> <container>:relname` resolves a
# relative destination against WORKDIR, but `docker exec <container> <cmd>`
# always starts at / regardless of WORKDIR -- that mismatch is exactly what
# broke CORE's DefaultRoute service (it writes/chmods files by relative name).
# Leaving the default WORKDIR (/) keeps both operations agreeing on the same
# directory. Scripts below are still placed at an explicit /workspace path;
# just `cd /workspace` (or use the absolute path) when running them by hand.

# Copy the master script and the pandapower outstation into the workspace
COPY pydnp3_master.py /workspace/pydnp3_master.py
COPY pandapower_grid.py /workspace/pandapower_grid.py
COPY pandapower_outstation.py /workspace/pandapower_outstation.py

# Expose ports if necessary (for server use, if any)
EXPOSE 8080

# Command to keep the container running (replace with your desired command if necessary)
CMD ["/bin/bash"]
