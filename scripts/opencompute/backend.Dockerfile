# setup optional docker arg list
ARG PYTHON_RUNTIME=python:3.12-bullseye
ARG WORKDIR=/app

# use the right python runtime base image
FROM ${PYTHON_RUNTIME}

# move to a non root folder
WORKDIR ${WORKDIR}

# copy the requirements file and the app file
COPY requirements.txt .
COPY server.py .
COPY .env .

RUN apt update && \
    apt install -y python3-dev gcc g++ cargo && \
    ln -s /usr/include/locale.h /usr/include/xlocale.h

# pip install the requirements
RUN pip3 install --upgrade pip
RUN pip3 install wandb python-dotenv pandas uvicorn fastapi bittensor

# create non root user
RUN adduser opencompute

# use the user
USER opencompute
# run the backend app, limit to 0.0.0.0 and port 8316
ENTRYPOINT ["uvicorn", "server:app", "--reload", "--host", "0.0.0.0", "--port", "8316"]
