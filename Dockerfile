FROM public.ecr.aws/lambda/python:3.12


ARG secret_manager
ARG region
# Copy requirements.txt
#COPY requirements.txt ${LAMBDA_TASK_ROOT}


# Example for Debian-based images
#RUN apt-get update && apt-get install -y build-essential libpq-dev
# Install the specified packages
#RUN yum install --ignore-engines

USER root
RUN echo $PATH
WORKDIR /app

#RUN apt-get update
#RUN python3.12 -m pip install -r requirements.txt
RUN python3.12 -m pip install boto3
RUN python3.12 -m  pip install langchain-community
RUN python3.12 -m pip install langchain_aws
RUN python3.12 -m pip install langgraph
RUN python3.12 -m pip install typing_extensions
RUN python3.12 -m pip install jsons
RUN python3.12 -m pip install urllib3
RUN python3.12 -m pip install requests
RUN python3.12 -m pip install streamlit
RUN python3.12 -m pip install snowflake-connector-python
RUN python3.12 -m pip install sqlparse
RUN python3.12 -m pip install sqlparse
RUN python3.12 -m pip install plotly

# Copy function code
#COPY lambda.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
#CMD [ "lambda.lambda_handler" ]

EXPOSE 8501
COPY . .


ENV region=$region
ENV APIGatewayURL=$APIGatewayURL

#ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false", "--client.toolbarMode=minimal"]
ENTRYPOINT ["streamlit", "run", "app.py"]

