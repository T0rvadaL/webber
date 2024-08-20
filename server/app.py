import hashlib

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def simulate_load():
    data = b"Hey there! I am writing this string because... wouldn't you like to know weather boiiiii?."
    for _ in range(10000):
        hashlib.sha256(data).digest()
    return data
