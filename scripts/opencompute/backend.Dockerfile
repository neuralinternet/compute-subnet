FROM python:3.12-bullseye

# move to a non root folder
WORKDIR /app

# copy the requirements file and the app file
COPY requirements.txt .
COPY server.py .

RUN apt update && \
    apt install -y python3-dev gcc g++ cargo && \
    ln -s /usr/include/locale.h /usr/include/xlocale.h

# pip install the requirements
RUN pip3 install --upgrade pip
RUN pip3 install wandb pandas uvicorn fastapi bittensor

# create non root user
RUN adduser opencompute

# use the user
USER opencompute
# run the backend app, limit to 0.0.0.0 and port 8316
ENTRYPOINT ["uvicorn", "server:app", "--reload", "--host", "0.0.0.0", "--port", "8316"]
