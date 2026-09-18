FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    metagpt \
    fastapi \
    uvicorn[standard] \
    pandas \
    numpy \
    scikit-learn \
    matplotlib \
    seaborn

COPY server.py .

EXPOSE 8100

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8100"]
