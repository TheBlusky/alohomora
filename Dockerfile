FROM python:latest
RUN mkdir /alohomora
WORKDIR /alohomora
ADD . /alohomora
RUN pip install -r requirements.txt
VOLUME /alohomora/allow.conf
EXPOSE 8080
CMD python alohomora.py
