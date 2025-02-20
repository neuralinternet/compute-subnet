# setup optional docker arg list
ARG PYTHON_RUNTIME=python:3.13-slim
ARG WORKDIR=/app

# use the right python runtime base image
FROM ${PYTHON_RUNTIME}

# move to a non root folder
WORKDIR ${WORKDIR}

# copy app files
COPY icon.ico .
COPY main.py .

# pip install the requirements
RUN pip3 install streamlit

# create non root user
RUN adduser streamliter

# expose the port
EXPOSE 8501

# add docker health check on streamlit app
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# use the user
USER streamliter
# run the streamlit app, limit to 0.0.0.0 and port 8501
ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
